from fastapi import FastAPI, Depends, HTTPException, status, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from bson import ObjectId
from typing import List, Optional

from database import connect_to_mongo, close_mongo_connection, get_database
from models import (
    UserCreate, UserLogin, UserResponse, Token,
    NotificationRequestCreate, NotificationRequestUpdate, NotificationRequestResponse,
    SettingsUpdate, SettingsResponse, FacilityAnalytics, WeeklyStats
)
from auth import create_user, authenticate_user, create_access_token, decode_access_token
from recreation_api import recreation_api, RecreationGovAPI
from scheduler import scheduler
from config import settings


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    scheduler.start()
    yield
    # Shutdown
    scheduler.stop()
    await close_mongo_connection()


app = FastAPI(title="Recreation.gov Notifier API", lifespan=lifespan)

# CORS middleware - allow all origins for local network access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development/local network access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    email = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    db = get_database()
    user = await db.users.find_one({"email": email})
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


# Health check
@app.get("/")
async def root():
    return {"message": "Recreation.gov Notifier API", "status": "running"}


# Authentication endpoints
@app.post("/api/auth/register", response_model=Token)
async def register(user: UserCreate):
    """Register a new user"""
    db_user = await create_user(user)
    
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/auth/login", response_model=Token)
async def login(user: UserLogin):
    """Login user"""
    db_user = await authenticate_user(user.email, user.password)
    
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    return UserResponse(
        id=str(current_user["_id"]),
        email=current_user["email"],
        phone_number=current_user.get("phone_number"),
        created_at=current_user["created_at"]
    )


# Notification request endpoints
@app.post("/api/notifications", response_model=NotificationRequestResponse)
async def create_notification_request(
    request: NotificationRequestCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new notification request"""
    db = get_database()
    
    # Parse facility ID from URL if needed
    facility_id = recreation_api.parse_facility_id_from_url(request.facility_id)
    
    if not facility_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid facility ID or URL"
        )
    
    # Get facility name if not provided
    if not request.facility_name:
        facility_name = recreation_api.get_facility_name(facility_id)
    else:
        facility_name = request.facility_name
    
    # Verify facility exists by attempting to get its info
    facility = recreation_api.get_facility(facility_id)
    if not facility:
        print(f"Warning: Could not verify facility {facility_id}, but proceeding with notification request")
        # Don't fail here - the facility might be valid but the info endpoint might have issues
    
    # Check if request already exists
    existing = await db.notification_requests.find_one({
        "user_id": current_user["_id"],
        "facility_id": facility_id
    })
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notification request already exists for this facility"
        )
    
    # Create notification request
    notification_dict = {
        "user_id": current_user["_id"],
        "facility_id": facility_id,
        "facility_name": facility_name,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "notify_email": request.notify_email,
        "notify_sms": request.notify_sms,
        "min_nights": request.min_nights,
        "created_at": datetime.utcnow(),
        "last_checked": None,
        "last_notified": None
    }
    
    result = await db.notification_requests.insert_one(notification_dict)
    notification_dict["_id"] = result.inserted_id
    
    return NotificationRequestResponse(
        id=str(notification_dict["_id"]),
        user_id=str(notification_dict["user_id"]),
        facility_id=notification_dict["facility_id"],
        facility_name=notification_dict["facility_name"],
        start_date=notification_dict["start_date"],
        end_date=notification_dict["end_date"],
        notify_email=notification_dict["notify_email"],
        notify_sms=notification_dict["notify_sms"],
        min_nights=notification_dict["min_nights"],
        created_at=notification_dict["created_at"],
        last_checked=notification_dict.get("last_checked"),
        last_notified=notification_dict.get("last_notified"),
        last_available_count=notification_dict.get("last_available_count")
    )


@app.get("/api/notifications", response_model=List[NotificationRequestResponse])
async def get_notification_requests(response: Response, current_user: dict = Depends(get_current_user)):
    """Get all notification requests for current user"""
    # Add cache-control headers to prevent stale data
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    db = get_database()
    
    requests = await db.notification_requests.find(
        {"user_id": current_user["_id"]}
    ).to_list(length=None)
    
    # Get all unique facility IDs
    facility_ids = [req["facility_id"] for req in requests]
    
    # Fetch latest availability history for all facilities in a single aggregation query
    # This reduces N+1 query problem
    pipeline = [
        {"$match": {"facility_id": {"$in": facility_ids}}},
        {"$sort": {"facility_id": 1, "timestamp": -1}},
        {"$group": {
            "_id": "$facility_id",
            "latest_doc": {"$first": "$$ROOT"}
        }}
    ]
    
    history_cursor = db.availability_history.aggregate(pipeline)
    history_map = {}
    async for doc in history_cursor:
        history_map[doc["_id"]] = doc["latest_doc"]
    
    # Build response list
    result_list = []
    for req in requests:
        available_sites = None
        available_dates = None
        
        latest_history = history_map.get(req["facility_id"])
        if latest_history and latest_history.get("full_data"):
            # Extract available dates from all sites in full_data
            all_available_dates = []
            for site_id, site_data in latest_history["full_data"].items():
                if site_data.get("available_dates"):
                    all_available_dates.extend(site_data["available_dates"])
            
            # Deduplicate and sort dates
            available_dates = sorted(list(set(all_available_dates)))
            available_sites = latest_history.get("available_sites", [])
        
        result_list.append(
            NotificationRequestResponse(
                id=str(req["_id"]),
                user_id=str(req["user_id"]),
                facility_id=req["facility_id"],
                facility_name=req["facility_name"],
                start_date=req["start_date"],
                end_date=req["end_date"],
                notify_email=req["notify_email"],
                notify_sms=req["notify_sms"],
                min_nights=req.get("min_nights", 1),
                created_at=req["created_at"],
                last_checked=req.get("last_checked"),
                last_notified=req.get("last_notified"),
                last_available_count=req.get("last_available_count"),
                available_sites=available_sites,
                available_dates=available_dates
            )
        )
    
    return result_list


@app.put("/api/notifications/{notification_id}", response_model=NotificationRequestResponse)
async def update_notification_request(
    notification_id: str,
    update: NotificationRequestUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update notification preferences"""
    db = get_database()
    
    # Verify ownership
    notification = await db.notification_requests.find_one({
        "_id": ObjectId(notification_id),
        "user_id": current_user["_id"]
    })
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification request not found"
        )
    
    # Build update dict
    update_dict = {}
    if update.notify_email is not None:
        update_dict["notify_email"] = update.notify_email
    if update.notify_sms is not None:
        update_dict["notify_sms"] = update.notify_sms
    if update.start_date is not None:
        update_dict["start_date"] = update.start_date
    if update.end_date is not None:
        update_dict["end_date"] = update.end_date
    if update.min_nights is not None:
        update_dict["min_nights"] = update.min_nights
    
    if update_dict:
        await db.notification_requests.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": update_dict}
        )
    
    # Get updated notification
    updated = await db.notification_requests.find_one({"_id": ObjectId(notification_id)})
    
    return NotificationRequestResponse(
        id=str(updated["_id"]),
        user_id=str(updated["user_id"]),
        facility_id=updated["facility_id"],
        facility_name=updated["facility_name"],
        start_date=updated["start_date"],
        end_date=updated["end_date"],
        notify_email=updated["notify_email"],
        notify_sms=updated["notify_sms"],
        min_nights=updated.get("min_nights", 1),
        created_at=updated["created_at"],
        last_checked=updated.get("last_checked"),
        last_notified=updated.get("last_notified"),
        last_available_count=updated.get("last_available_count")
    )


@app.delete("/api/notifications/{notification_id}")
async def delete_notification_request(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a notification request"""
    db = get_database()
    
    result = await db.notification_requests.delete_one({
        "_id": ObjectId(notification_id),
        "user_id": current_user["_id"]
    })
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification request not found"
        )
    
    return {"message": "Notification request deleted"}


# Test endpoint to verify API connectivity
@app.get("/api/test-recreation-api/{facility_id}")
async def test_recreation_api(facility_id: str, start_date: str, end_date: str):
    """Test Recreation.gov API with a specific facility"""
    rec_api = RecreationGovAPI()
    result = rec_api.check_availability(facility_id, start_date, end_date)
    return result


# Settings endpoints
@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings(current_user: dict = Depends(get_current_user)):
    """Get current settings"""
    return SettingsResponse(scrape_interval=scheduler.scrape_interval)


@app.put("/api/settings", response_model=SettingsResponse)
async def update_settings(
    settings_update: SettingsUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update settings (admin only for now)"""
    if settings_update.scrape_interval is not None:
        scheduler.update_interval(settings_update.scrape_interval)
    
    return SettingsResponse(scrape_interval=scheduler.scrape_interval)


# Analytics endpoints
@app.get("/api/analytics/{facility_id}", response_model=FacilityAnalytics)
async def get_facility_analytics(
    facility_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get availability analytics for a facility"""
    db = get_database()
    
    # Get facility name
    notification = await db.notification_requests.find_one({
        "user_id": current_user["_id"],
        "facility_id": facility_id
    })
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No notification request found for this facility"
        )
    
    # Get availability history
    history = await db.availability_history.find(
        {"facility_id": facility_id}
    ).sort("timestamp", 1).to_list(length=None)
    
    # Calculate weekly statistics
    weekly_changes = {}
    previous_available_count = 0
    
    for record in history:
        timestamp = record["timestamp"]
        week_number = timestamp.isocalendar()[1]
        year = timestamp.year
        key = (year, week_number)
        
        current_available_count = record.get("available_count", 0)
        
        # Count when availability increased (reserved → available)
        if current_available_count > previous_available_count:
            if key not in weekly_changes:
                weekly_changes[key] = 0
            weekly_changes[key] += 1
        
        previous_available_count = current_available_count
    
    # Convert to list format
    weekly_stats = [
        WeeklyStats(year=year, week_number=week, availability_changes=count)
        for (year, week), count in sorted(weekly_changes.items())
    ]
    
    return FacilityAnalytics(
        facility_id=facility_id,
        facility_name=notification["facility_name"],
        weekly_stats=weekly_stats
    )


# Push Subscription endpoints
@app.get("/api/push/vapid-public-key")
async def get_vapid_public_key():
    """Get the VAPID public key for push notifications"""
    from config import settings
    return {"publicKey": settings.VAPID_PUBLIC_KEY}


@app.post("/api/push/subscribe")
async def subscribe_to_push(
    subscription: dict,
    current_user: dict = Depends(get_current_user)
):
    """Subscribe to push notifications"""
    db = get_database()
    
    # Check if subscription already exists
    existing = await db.push_subscriptions.find_one({
        "user_id": current_user["_id"],
        "endpoint": subscription["endpoint"]
    })
    
    if existing:
        return {"message": "Subscription already exists", "id": str(existing["_id"])}
    
    # Create new subscription
    subscription_doc = {
        "user_id": current_user["_id"],
        "endpoint": subscription["endpoint"],
        "keys": subscription["keys"],
        "created_at": datetime.utcnow()
    }
    
    result = await db.push_subscriptions.insert_one(subscription_doc)
    
    return {
        "message": "Subscribed to push notifications",
        "id": str(result.inserted_id)
    }


@app.delete("/api/push/unsubscribe")
async def unsubscribe_from_push(
    endpoint: str,
    current_user: dict = Depends(get_current_user)
):
    """Unsubscribe from push notifications"""
    db = get_database()
    
    result = await db.push_subscriptions.delete_one({
        "user_id": current_user["_id"],
        "endpoint": endpoint
    })
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )
    
    return {"message": "Unsubscribed from push notifications"}


@app.get("/api/push/subscriptions")
async def get_push_subscriptions(current_user: dict = Depends(get_current_user)):
    """Get all push subscriptions for the current user"""
    db = get_database()
    
    subscriptions = await db.push_subscriptions.find({
        "user_id": current_user["_id"]
    }).to_list(length=None)
    
    return {
        "subscriptions": [
            {
                "id": str(sub["_id"]),
                "endpoint": sub["endpoint"],
                "created_at": sub["created_at"]
            }
            for sub in subscriptions
        ]
    }


@app.post("/api/push/test")
async def test_push_notification(current_user: dict = Depends(get_current_user)):
    """Send a test push notification"""
    from notifications import web_push_service
    
    if not web_push_service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Web push notifications are not configured"
        )
    
    db = get_database()
    
    # Get user's push subscriptions
    subscriptions = await db.push_subscriptions.find({
        "user_id": current_user["_id"]
    }).to_list(length=None)
    
    if not subscriptions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No push subscriptions found. Please enable push notifications first."
        )
    
    # Send test notification to all subscriptions
    sent_count = 0
    expired_subscriptions = []
    
    for sub in subscriptions:
        subscription_info = {
            "endpoint": sub["endpoint"],
            "keys": sub["keys"]
        }
        
        result = web_push_service.send_push_notification(
            subscription_info=subscription_info,
            title="🏕️ Test Notification",
            body="Your push notifications are working! You'll receive alerts when campsites become available.",
            url="https://basecamp.highz.net"
        )
        
        if result == "expired":
            expired_subscriptions.append(sub["_id"])
        elif result:
            sent_count += 1
    
    # Remove expired subscriptions
    if expired_subscriptions:
        await db.push_subscriptions.delete_many({
            "_id": {"$in": expired_subscriptions}
        })
    
    if sent_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send push notification"
        )
    
    return {
        "message": f"Test notification sent to {sent_count} device(s)",
        "expired_removed": len(expired_subscriptions)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
