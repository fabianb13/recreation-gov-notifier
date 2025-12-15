"""
Quick test to add a notification and monitor scheduler activity
"""
import requests
import time

BASE_URL = "http://localhost:8000"

# First, register and get token
email = f"scheduler_test_{int(time.time())}@example.com"
response = requests.post(
    f"{BASE_URL}/api/auth/register",
    json={"email": email, "password": "testpass123", "phone_number": "+15551234567"}
)

if response.status_code != 200:
    print("Registration failed")
    exit(1)

token = response.json()["access_token"]
print(f"✅ Registered user: {email}")

# Add a notification
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(
    f"{BASE_URL}/api/notifications",
    headers=headers,
    json={
        "facility_id": "232447",
        "facility_name": "Test Campground",
        "start_date": "2026-07-01",
        "end_date": "2026-07-07",
        "notify_email": True,
        "notify_sms": False
    }
)

if response.status_code != 200:
    print(f"Failed to add notification: {response.text}")
    exit(1)

notification = response.json()
print(f"✅ Added notification: {notification['id']}")
print(f"   Facility: {notification['facility_name']}")
print(f"   Dates: {notification['start_date']} to {notification['end_date']}")
print(f"\n⏳ Waiting for scheduler to run (3 minutes)...")
print(f"   Current scrape interval is set to 180 seconds")
print(f"\n   Monitoring backend logs for scheduler activity...")
