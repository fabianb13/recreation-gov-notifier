from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext
from config import settings
from models import UserCreate
from database import get_database

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.InvalidTokenError:
        return None


async def create_user(user: UserCreate):
    db = get_database()
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        return None
    
    user_dict = {
        "email": user.email,
        "hashed_password": get_password_hash(user.password),
        "phone_number": user.phone_number,
        "created_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_dict)
    user_dict["_id"] = result.inserted_id
    return user_dict


async def authenticate_user(email: str, password: str):
    db = get_database()
    user = await db.users.find_one({"email": email})
    
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    
    return user


async def get_user_by_email(email: str):
    db = get_database()
    return await db.users.find_one({"email": email})
