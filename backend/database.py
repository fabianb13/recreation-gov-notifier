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


async def close_mongo_connection():
    global client
    if client:
        client.close()
        print("Closed MongoDB connection")


def get_database():
    return db
