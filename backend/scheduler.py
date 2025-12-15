from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from database import get_database
from recreation_api import recreation_api
from notifications import email_service, sms_service
from config import settings
import asyncio


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
            
            for request in requests:
                await self.check_notification_request(request)
            
            print("Completed availability check cycle")
        except Exception as e:
            print(f"Error in check_all_notifications: {e}")
    
    async def check_notification_request(self, request: dict):
        """Check a single notification request for availability"""
        db = get_database()
        facility_id = request["facility_id"]
        
        try:
            # Get current availability
            availability_data = recreation_api.check_availability(
                facility_id,
                request["start_date"],
                request["end_date"]
            )
            
            if not availability_data.get("success", False):
                print(f"Failed to check availability for facility {facility_id}: {availability_data.get('error')}")
                return
            
            campsites_data = availability_data.get("campsites", {})
            total_sites = availability_data.get("count", 0)
            
            # Parse availability for date range
            available_sites = recreation_api.get_campsite_availability_for_dates(
                campsites_data,
                request["start_date"],
                request["end_date"]
            )
            
            # Filter to only sites with availability
            newly_available = [
                site_info["name"] for site_id, site_info in available_sites.items()
                if site_info.get("has_availability", False)
            ]
            
            # Store availability snapshot
            await db.availability_history.insert_one({
                "facility_id": facility_id,
                "timestamp": datetime.utcnow(),
                "available_count": len(newly_available),
                "total_sites": total_sites,
                "available_sites": newly_available,
                "full_data": available_sites
            })
            
            print(f"Checked facility {facility_id}: {len(newly_available)} sites available out of {total_sites} total")
            
            # Check if we should send notification
            should_notify = False
            
            # Get the last availability check
            last_check = await db.availability_history.find_one(
                {"facility_id": facility_id},
                sort=[("timestamp", -1)],
                skip=1  # Skip the one we just inserted
            )
            
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
                            dates
                        )
                    
                    # Send SMS notification
                    if request.get("notify_sms", False) and user.get("phone_number"):
                        sms_service.send_availability_notification(
                            user["phone_number"],
                            request["facility_name"],
                            newly_available,
                            dates
                        )
                    
                    # Update last notified timestamp
                    await db.notification_requests.update_one(
                        {"_id": request["_id"]},
                        {"$set": {"last_notified": datetime.utcnow()}}
                    )
            
            # Update last checked timestamp
            await db.notification_requests.update_one(
                {"_id": request["_id"]},
                {"$set": {"last_checked": datetime.utcnow()}}
            )
            
        except Exception as e:
            print(f"Error checking notification request {request.get('_id')}: {e}")
    
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
