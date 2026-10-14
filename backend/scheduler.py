from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from database import get_database
from recreation_api import recreation_api
from notifications import email_service, sms_service, web_push_service
from config import settings
from proxy_manager import proxy_manager, REVERIFY_INTERVAL_SECONDS
import asyncio
from concurrent.futures import ThreadPoolExecutor
import functools


# Thread pool for running synchronous operations without blocking the event loop
executor = ThreadPoolExecutor(max_workers=8)


class AvailabilityScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.scrape_interval = settings.DEFAULT_SCRAPE_INTERVAL
    
    async def check_all_notifications(self):
        """Check all active notification requests for availability changes"""
        db = get_database()
        
        try:
            # Get all active notification requests
            requests = await db.notification_requests.find().to_list(length=None)
            
            print(f"Checking {len(requests)} notification requests...")
            
            by_facility = {}
            for request in requests:
                by_facility.setdefault(request["facility_id"], []).append(request)
            
            await asyncio.gather(*(
                self.check_facility(facility_id, facility_requests)
                for facility_id, facility_requests in by_facility.items()
            ))
            
            print("Completed availability check cycle")
        except Exception as e:
            print(f"Error in check_all_notifications: {e}")
    
    async def check_facility(self, facility_id: str, requests: list):
        """Fetch a campground once covering every saved search's dates, then evaluate each search"""
        # ISO date strings sort chronologically
        start_date = min(r["start_date"] for r in requests)
        end_date = max(r["end_date"] for r in requests)
        
        try:
            loop = asyncio.get_event_loop()
            availability_data = await loop.run_in_executor(
                executor,
                functools.partial(recreation_api.check_availability, facility_id, start_date, end_date)
            )
        except Exception as e:
            print(f"Error fetching facility {facility_id}: {e}")
            return
        
        if not availability_data.get("success", False):
            print(f"Failed to check availability for facility {facility_id}: {availability_data.get('error')}")
            return
        
        for request in requests:
            await self.check_notification_request(request, availability_data)
    
    async def check_notification_request(self, request: dict, availability_data: dict):
        """Evaluate a single notification request against fetched availability data"""
        db = get_database()
        facility_id = request["facility_id"]
        
        try:
            loop = asyncio.get_event_loop()
            campsites_data = availability_data.get("campsites", {})
            total_sites = availability_data.get("count", 0)
            
            # Parse availability for date range (also run in executor as it may be CPU intensive)
            min_nights = request.get("min_nights", 1)
            available_sites = await loop.run_in_executor(
                executor,
                functools.partial(
                    recreation_api.get_campsite_availability_for_dates,
                    campsites_data,
                    request["start_date"],
                    request["end_date"],
                    min_nights=min_nights
                )
            )
            
            # Filter to only sites with availability
            newly_available = [
                site_info["name"] for site_id, site_info in available_sites.items()
                if site_info.get("has_availability", False)
            ]
            
            # Store availability snapshot
            last_check = await db.availability_history.find_one(
                {"notification_request_id": request["_id"]},
                sort=[("timestamp", -1)]
            )
            
            await db.availability_history.insert_one({
                "notification_request_id": request["_id"],
                "facility_id": facility_id,
                "timestamp": datetime.utcnow(),
                "available_count": len(newly_available),
                "total_sites": total_sites,
                "available_sites": newly_available
            })
            
            print(f"Checked facility {facility_id}: {len(newly_available)} sites available out of {total_sites} total")
            
            # Check if we should send notification
            should_notify = False
            
            if last_check:
                # Check if availability increased (sites became available)
                last_available_count = last_check.get("available_count", 0)
                current_available_count = len(newly_available)
                
                if current_available_count > last_available_count and newly_available:
                    should_notify = True
            elif newly_available:
                # First check and sites are available
                should_notify = True
            
            # Send notifications if needed
            all_available_dates = []
            for site_info in available_sites.values():
                if site_info.get("has_availability", False) and site_info.get("available_dates"):
                    all_available_dates.extend(site_info["available_dates"])
            unique_dates = sorted(set(all_available_dates))
            
            if should_notify:
                user = await db.users.find_one({"_id": request["user_id"]})
                
                if user and newly_available:
                    dates = f"{request['start_date']} to {request['end_date']}"
                    
                    # Send email notification
                    if request.get("notify_email", True):
                        email_service.send_availability_notification(
                            user["email"],
                            request["facility_name"],
                            newly_available,
                            dates,
                            request["facility_id"],
                            unique_dates
                        )
                    
                    # Send SMS notification
                    if request.get("notify_sms", False) and user.get("phone_number"):
                        sms_service.send_availability_notification(
                            user["phone_number"],
                            request["facility_name"],
                            newly_available,
                            dates,
                            request["facility_id"],
                            unique_dates
                        )
                    
                    # Send web push notification
                    if request.get("notify_push", True) and web_push_service.enabled:
                        # Get all push subscriptions for the user
                        push_subscriptions = await db.push_subscriptions.find({
                            "user_id": user["_id"]
                        }).to_list(length=None)
                        
                        expired_subscriptions = []
                        
                        for sub in push_subscriptions:
                            subscription_info = {
                                "endpoint": sub["endpoint"],
                                "keys": sub["keys"]
                            }
                            
                            result = web_push_service.send_availability_notification(
                                subscription_info=subscription_info,
                                facility_name=request["facility_name"],
                                available_sites=newly_available,
                                dates=dates,
                                facility_id=request["facility_id"],
                                available_dates=unique_dates
                            )
                            
                            # Track expired subscriptions for removal
                            if result == "expired":
                                expired_subscriptions.append(sub["_id"])
                        
                        # Remove expired subscriptions
                        if expired_subscriptions:
                            await db.push_subscriptions.delete_many({
                                "_id": {"$in": expired_subscriptions}
                            })
                            print(f"Removed {len(expired_subscriptions)} expired push subscriptions")
                    
                    # Update last notified timestamp
                    await db.notification_requests.update_one(
                        {"_id": request["_id"]},
                        {"$set": {"last_notified": datetime.utcnow()}}
                    )
            
            # Update last checked timestamp and availability count
            await db.notification_requests.update_one(
                {"_id": request["_id"]},
                {"$set": {
                    "last_checked": datetime.utcnow(),
                    "last_available_count": len(newly_available),
                    "available_sites": newly_available,
                    "available_dates": unique_dates
                }}
            )
            
        except Exception as e:
            print(f"Error checking notification request {request.get('_id')}: {e}")
    
    async def reverify_proxies(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, proxy_manager.reverify_benched)
    
    def start(self):
        """Start the scheduler"""
        if not self.is_running:
            self.scheduler.add_job(
                self.check_all_notifications,
                'interval',
                seconds=self.scrape_interval,
                id='availability_check',
                replace_existing=True
            )
            self.scheduler.add_job(
                self.reverify_proxies,
                'interval',
                seconds=REVERIFY_INTERVAL_SECONDS,
                id='proxy_reverify',
                replace_existing=True
            )
            self.scheduler.start()
            self.is_running = True
            print(f"Scheduler started with interval: {self.scrape_interval} seconds")
    
    def stop(self):
        """Stop the scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            print("Scheduler stopped")
    
    def update_interval(self, new_interval: int):
        """Update the scrape interval"""
        self.scrape_interval = new_interval
        
        if self.is_running:
            # Reschedule the job with new interval
            self.scheduler.reschedule_job(
                'availability_check',
                trigger='interval',
                seconds=new_interval
            )
            print(f"Scheduler interval updated to {new_interval} seconds")


# Global scheduler instance
scheduler = AvailabilityScheduler()
