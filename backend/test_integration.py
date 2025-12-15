"""
Manual Integration Tests for Recreation.gov Notifier
Run this script to test the complete application flow
"""

import requests
import time
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def test_1_register_user():
    """Test user registration"""
    print_header("TEST 1: User Registration")
    
    email = f"test_{int(time.time())}@example.com"
    password = "testpass123"
    phone = "+15551234567"
    
    response = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "email": email,
            "password": password,
            "phone_number": phone
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print("✅ Registration successful!")
        return token, email
    else:
        print("❌ Registration failed!")
        return None, None

def test_2_login_user(email, password="testpass123"):
    """Test user login"""
    print_header("TEST 2: User Login")
    
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": email,
            "password": password
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Login successful!")
        return response.json()["access_token"]
    else:
        print("❌ Login failed!")
        return None

def test_3_get_user_info(token):
    """Test getting current user info"""
    print_header("TEST 3: Get User Info")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Get user info successful!")
        return True
    else:
        print("❌ Get user info failed!")
        return False

def test_4_add_campsite_notification(token):
    """Test adding a campsite notification request"""
    print_header("TEST 4: Add Campsite Notification")
    
    # Using Upper Pines Campground in Yosemite (popular campground)
    facility_id = "232447"
    
    # Set dates for summer (high demand period)
    start_date = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=67)).strftime("%Y-%m-%d")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{BASE_URL}/api/notifications",
        headers=headers,
        json={
            "facility_id": facility_id,
            "facility_name": "Upper Pines Campground - Yosemite",
            "start_date": start_date,
            "end_date": end_date,
            "notify_email": True,
            "notify_sms": False
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Add campsite notification successful!")
        return response.json()["id"]
    else:
        print("❌ Add campsite notification failed!")
        print(f"Error: {response.text}")
        return None

def test_5_get_notifications(token):
    """Test getting all notification requests"""
    print_header("TEST 5: Get All Notifications")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        notifications = response.json()
        print(f"✅ Get notifications successful! Found {len(notifications)} notification(s)")
        return notifications
    else:
        print("❌ Get notifications failed!")
        return []

def test_6_update_notification(token, notification_id):
    """Test updating notification preferences"""
    print_header("TEST 6: Update Notification Preferences")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.put(
        f"{BASE_URL}/api/notifications/{notification_id}",
        headers=headers,
        json={
            "notify_sms": True
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Update notification successful!")
        return True
    else:
        print("❌ Update notification failed!")
        return False

def test_7_get_settings(token):
    """Test getting application settings"""
    print_header("TEST 7: Get Settings")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/settings", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Get settings successful!")
        return response.json()
    else:
        print("❌ Get settings failed!")
        return None

def test_8_update_settings(token):
    """Test updating application settings"""
    print_header("TEST 8: Update Settings (Scrape Interval)")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.put(
        f"{BASE_URL}/api/settings",
        headers=headers,
        json={
            "scrape_interval": 180  # 3 minutes
        }
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Update settings successful!")
        return True
    else:
        print("❌ Update settings failed!")
        return False

def test_9_get_analytics(token, facility_id):
    """Test getting facility analytics"""
    print_header("TEST 9: Get Facility Analytics")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/analytics/{facility_id}", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        print(f"✅ Get analytics successful! Found {len(data.get('weekly_stats', []))} weeks of data")
        return True
    else:
        print(f"❌ Get analytics failed!")
        print(f"Response: {response.text}")
        return False

def test_10_delete_notification(token, notification_id):
    """Test deleting a notification request"""
    print_header("TEST 10: Delete Notification")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.delete(f"{BASE_URL}/api/notifications/{notification_id}", headers=headers)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        print("✅ Delete notification successful!")
        return True
    else:
        print("❌ Delete notification failed!")
        return False

def main():
    print("\n" + "="*60)
    print("  RECREATION.GOV NOTIFIER - INTEGRATION TESTS")
    print("="*60)
    print("\nTesting backend at:", BASE_URL)
    print("Make sure Docker containers are running!")
    print("\nStarting tests...\n")
    time.sleep(2)
    
    # Run tests in sequence
    token, email = test_1_register_user()
    if not token:
        print("\n❌ Cannot continue without valid token")
        return
    
    time.sleep(1)
    test_3_get_user_info(token)
    
    time.sleep(1)
    notification_id = test_4_add_campsite_notification(token)
    
    time.sleep(1)
    notifications = test_5_get_notifications(token)
    
    if notification_id:
        time.sleep(1)
        test_6_update_notification(token, notification_id)
    
    time.sleep(1)
    test_7_get_settings(token)
    
    time.sleep(1)
    test_8_update_settings(token)
    
    if notification_id:
        time.sleep(1)
        # Try to get analytics (may not have data yet)
        test_9_get_analytics(token, "232447")
        
        time.sleep(1)
        test_10_delete_notification(token, notification_id)
    
    print_header("TEST SUMMARY")
    print("✅ All manual integration tests completed!")
    print("\nNext steps:")
    print("1. Open http://localhost:3000 in your browser")
    print("2. Register a new account in the UI")
    print("3. Add a campsite notification")
    print("4. Wait for the scheduler to run (default 5 minutes)")
    print("5. Check MongoDB for availability_history data")
    print("6. View analytics after some polling cycles")

if __name__ == "__main__":
    main()
