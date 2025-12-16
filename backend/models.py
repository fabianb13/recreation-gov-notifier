from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return {"type": "string"}


# User Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    phone_number: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    phone_number: Optional[str] = None
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str


# Notification Request Models
class NotificationRequestCreate(BaseModel):
    facility_id: str
    facility_name: str
    start_date: str
    end_date: str
    notify_email: bool = True
    notify_sms: bool = False
    notify_push: bool = True
    min_nights: int = 1


class NotificationRequestUpdate(BaseModel):
    notify_email: Optional[bool] = None
    notify_sms: Optional[bool] = None
    notify_push: Optional[bool] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    min_nights: Optional[int] = None


class NotificationRequestResponse(BaseModel):
    id: str
    user_id: str
    facility_id: str
    facility_name: str
    start_date: str
    end_date: str
    notify_email: bool
    notify_sms: bool
    notify_push: bool = True
    min_nights: int = 1
    created_at: datetime
    last_checked: Optional[datetime] = None
    last_notified: Optional[datetime] = None
    last_available_count: Optional[int] = None
    available_sites: Optional[List[str]] = None
    available_dates: Optional[List[str]] = None


# Settings Models
class SettingsUpdate(BaseModel):
    scrape_interval: Optional[int] = Field(None, ge=60, le=3600)


class SettingsResponse(BaseModel):
    scrape_interval: int


# Analytics Models
class AvailabilityChange(BaseModel):
    facility_id: str
    campsite_id: str
    date: str
    timestamp: datetime
    previous_status: str
    current_status: str


class WeeklyStats(BaseModel):
    week_number: int
    year: int
    availability_changes: int


class FacilityAnalytics(BaseModel):
    facility_id: str
    facility_name: str
    weekly_stats: List[WeeklyStats]


# Push Notification Models
class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys


class PushSubscriptionResponse(BaseModel):
    id: str
    user_id: str
    endpoint: str
    keys: dict
    created_at: datetime
