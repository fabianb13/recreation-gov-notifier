"""
Quick test of the corrected Recreation.gov API
"""
import requests
import time

BASE_URL = "http://localhost:8000"

# Register a user
print("=== Testing Recreation.gov API Fix ===\n")
email = f"api_test_{int(time.time())}@example.com"
response = requests.post(
    f"{BASE_URL}/api/auth/register",
    json={"email": email, "password": "testpass123", "phone_number": "+15551234567"}
)

if response.status_code != 200:
    print(f"Registration failed: {response.text}")
    exit(1)

token = response.json()["access_token"]
print(f"✅ Registered user: {email}\n")

# Add a notification for a popular campground
# Using Upper Pines in Yosemite - facility ID 232447
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(
    f"{BASE_URL}/api/notifications",
    headers=headers,
    json={
        "facility_id": "232447",
        "facility_name": "",  # Let it fetch automatically
        "start_date": "2024-08-01",  # Past date for testing
        "end_date": "2024-08-05",
        "notify_email": True,
        "notify_sms": False
    }
)

if response.status_code != 200:
    print(f"❌ Failed to add notification: {response.text}")
    exit(1)

notification = response.json()
print(f"✅ Added notification:")
print(f"   ID: {notification['id']}")
print(f"   Facility: {notification['facility_name']}")
print(f"   Dates: {notification['start_date']} to {notification['end_date']}")
print(f"\n⏳ Waiting 15 seconds for scheduler to pick it up...")

# Wait for the scheduler (note: may need to wait 5 minutes for actual run)
time.sleep(15)

# Check MongoDB directly via backend logs or wait for next cycle
print(f"\n📊 Check backend logs with: docker logs recreation-backend")
print(f"   Look for 'Checking availability for facility 232447'")
print(f"\n📝 To manually trigger check, wait for scheduler cycle (5 minutes)")
print(f"   Or check MongoDB: docker exec recreation-mongo mongosh recreation_notifier --eval \"db.availability_history.find().limit(1).pretty()\"")
