from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

client = None
db = None


async def connect_to_mongo():
    global client, db
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    print(f"Connected to MongoDB: {settings.MONGODB_DB_NAME}")
    
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.notification_requests.create_index([("user_id", 1), ("facility_id", 1)])
    await db.availability_history.create_index([("facility_id", 1), ("timestamp", -1)])
    await db.availability_history.create_index([("notification_request_id", 1), ("timestamp", -1)])
    
    # full_data is no longer stored; drop it from older records
    result = await db.availability_history.update_many(
        {"full_data": {"$exists": True}},
        {"$unset": {"full_data": ""}}
    )
    if result.modified_count:
        print(f"🧹 Removed full_data from {result.modified_count} availability history records")


async def close_mongo_connection():
    global client
    if client:
        client.close()
        print("Closed MongoDB connection")


def get_database():
    return db
