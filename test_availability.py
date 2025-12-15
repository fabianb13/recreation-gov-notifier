#!/usr/bin/env python3
import sys
sys.path.insert(0, 'backend')

from recreation_api import recreation_api
from datetime import datetime, timedelta
import json

# Test facility 234201
facility_id = "234201"
start_date = "2025-12-15"
end_date = "2025-12-20"  # Short range for testing

print(f"Testing facility {facility_id} from {start_date} to {end_date}")
print("=" * 80)

# Get raw availability data
print("\n1. Fetching raw availability data...")
availability_data = recreation_api.check_availability(facility_id, start_date, end_date)

if not availability_data.get("success"):
    print(f"ERROR: {availability_data.get('error')}")
    sys.exit(1)

campsites_data = availability_data.get("campsites", {})
print(f"   Found {len(campsites_data)} campsites")
print(f"   Total sites: {availability_data.get('count', 0)}")

# Show first campsite's availability as example
if campsites_data:
    first_id = list(campsites_data.keys())[0]
    first_site = campsites_data[first_id]
    print(f"\n   Example site: {first_site.get('campsite_name', first_id)}")
    print(f"   Availabilities: {first_site.get('availabilities', {})}")

# Test with min_nights=1
print("\n2. Testing with min_nights=1...")
available_1 = recreation_api.get_campsite_availability_for_dates(
    campsites_data, start_date, end_date, min_nights=1
)
print(f"   Available sites: {len(available_1)}")
if available_1:
    print(f"   Sites: {list(available_1.keys())[:5]}")  # Show first 5
    first_available_id = list(available_1.keys())[0]
    first_available = available_1[first_available_id]
    print(f"   Example: {first_available['name']}")
    print(f"   Consecutive nights: {first_available['consecutive_nights']}")
    print(f"   Available dates: {first_available['available_dates'][:3]}")  # Show first 3

# Test with min_nights=2
print("\n3. Testing with min_nights=2...")
available_2 = recreation_api.get_campsite_availability_for_dates(
    campsites_data, start_date, end_date, min_nights=2
)
print(f"   Available sites: {len(available_2)}")

# Test with min_nights=3
print("\n4. Testing with min_nights=3...")
available_3 = recreation_api.get_campsite_availability_for_dates(
    campsites_data, start_date, end_date, min_nights=3
)
print(f"   Available sites: {len(available_3)}")

print("\n" + "=" * 80)
print("SUMMARY:")
print(f"  Total campsites in facility: {availability_data.get('count', 0)}")
print(f"  Available with min_nights=1: {len(available_1)}")
print(f"  Available with min_nights=2: {len(available_2)}")
print(f"  Available with min_nights=3: {len(available_3)}")
