import requests
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from dateutil import rrule
from config import settings
import re


class RecreationGovAPI:
    BASE_URL = "https://www.recreation.gov"
    AVAILABILITY_ENDPOINT = "/api/camps/availability/campground/{}/month"
    CAMPGROUND_ENDPOINT = "/api/camps/campgrounds/{}"
    
    def __init__(self):
        # Recreation.gov public API doesn't require API key for availability checks
        # Use a realistic User-Agent to avoid being blocked
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
    
    def parse_facility_id_from_url(self, url: str) -> Optional[str]:
        """
        Parse facility ID from Recreation.gov URL
        Format: https://www.recreation.gov/camping/campgrounds/<facilityid>
        """
        patterns = [
            r'recreation\.gov/camping/campgrounds/(\d+)',
            r'recreation\.gov/camping/gateways/(\d+)',
            r'facilityId=(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # If no pattern matches, assume it's just the ID
        if url.isdigit():
            return url
        
        return None
    
    def format_date_for_request(self, date_obj: datetime) -> str:
        """Format datetime object to Recreation.gov API format with milliseconds"""
        # Output format: YYYY-MM-DDTHH:MM:SS.000Z (with milliseconds)
        return date_obj.strftime("%Y-%m-%dT00:00:00.000Z")
    
    def format_date_for_response(self, date_str: str) -> str:
        """Format date string to match API response format"""
        # Convert YYYY-MM-DD to YYYY-MM-DDTHH:MM:SS.000Z
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            return self.format_date_for_request(date_obj)
        except Exception:
            return date_str
    
    def get_facility(self, facility_id: str) -> Optional[Dict]:
        """Get facility/campground information by ID"""
        try:
            url = self.BASE_URL + self.CAMPGROUND_ENDPOINT.format(facility_id)
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                print(f"Error fetching facility {facility_id}: Status {response.status_code}")
                return None
            return response.json()
        except Exception as e:
            print(f"Error fetching facility {facility_id}: {e}")
            return None
    
    def get_facility_name(self, facility_id: str) -> str:
        """Get the name of a campground"""
        try:
            facility_data = self.get_facility(facility_id)
            if facility_data and "campground" in facility_data:
                return facility_data["campground"].get("facility_name", "Unknown Campground")
            return "Unknown Campground"
        except Exception as e:
            print(f"Error getting facility name for {facility_id}: {e}")
            return "Unknown Campground"
    
    def check_availability(self, facility_id: str, start_date: str, end_date: str) -> Dict:
        """
        Check availability using Recreation.gov's public availability API
        
        The API requires querying by month. If the date range spans multiple months,
        we need to make multiple requests (one per month).
        """
        try:
            # Parse input dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            # Get first of month for start date
            start_of_month = datetime(start_dt.year, start_dt.month, 1)
            
            # Get all months we need to query
            months = list(rrule.rrule(rrule.MONTHLY, dtstart=start_of_month, until=end_dt))
            
            print(f"Checking availability for facility {facility_id} from {start_date} to {end_date}")
            print(f"Need to query {len(months)} month(s)")
            
            # Collect data from all months
            all_campsites_data = {}
            total_count = 0
            
            for month_date in months:
                url = self.BASE_URL + self.AVAILABILITY_ENDPOINT.format(facility_id)
                params = {"start_date": self.format_date_for_request(month_date)}
                
                print(f"Querying month: {month_date.strftime('%Y-%m')}")
                
                response = requests.get(url, params=params, headers=self.headers, timeout=15)
                
                if response.status_code != 200:
                    print(f"Error: Received status code {response.status_code} from {url}")
                    print(f"Response: {response.text}")
                    continue
                
                month_data = response.json()
                month_campsites = month_data.get("campsites", {})
                
                # Merge campsites data
                for campsite_id, campsite_info in month_campsites.items():
                    if campsite_id not in all_campsites_data:
                        all_campsites_data[campsite_id] = campsite_info
                        # Ensure availabilities dict exists
                        if "availabilities" not in all_campsites_data[campsite_id]:
                            all_campsites_data[campsite_id]["availabilities"] = {}
                    else:
                        # Merge availability data
                        all_campsites_data[campsite_id]["availabilities"].update(
                            campsite_info.get("availabilities", {})
                        )
                
                # Use count from first successful response
                if total_count == 0:
                    total_count = month_data.get("count", 0)
            
            if not all_campsites_data:
                return {
                    "facility_id": facility_id,
                    "count": 0,
                    "campsites": {},
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": "No data returned from API",
                    "success": False
                }
            
            return {
                "facility_id": facility_id,
                "count": total_count,
                "campsites": all_campsites_data,
                "timestamp": datetime.utcnow().isoformat(),
                "success": True
            }
                
        except Exception as e:
            print(f"Error checking availability for facility {facility_id}: {e}")
            import traceback
            traceback.print_exc()
            return {
                "facility_id": facility_id,
                "count": 0,
                "campsites": {},
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "success": False
            }
    
    def get_campsite_availability_for_dates(self, campsites_data: Dict, start_date: str, end_date: str) -> Dict:
        """
        Parse availability data for specific date range
        A campsite is only considered available if ALL dates in the range are "Available"
        Returns dict of campsite_id -> availability status
        """
        available_campsites = {}
        
        # Generate set of dates in the range (formatted for comparison with API response)
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        num_days = (end_dt - start_dt).days
        
        # Create set of dates to check (excluding end_date since it's the checkout day)
        # Format as YYYY-MM-DDTHH:MM:SS.000Z to match API response format
        date_range = set()
        for i in range(num_days):
            check_date = start_dt + timedelta(days=i)
            date_range.add(self.format_date_for_request(check_date))
        
        if not date_range:
            return available_campsites
        
        for campsite_id, campsite_info in campsites_data.items():
            availabilities = campsite_info.get("availabilities", {})
            
            # Check if ALL dates in range are available
            # A site is only available if every single night is available
            has_full_availability = True
            available_nights = []
            
            for check_date in date_range:
                status = availabilities.get(check_date, "Not Available")
                if status == "Available":
                    available_nights.append(check_date)
                else:
                    has_full_availability = False
                    break
            
            # Only include if ALL nights are available
            if has_full_availability and len(available_nights) == len(date_range):
                available_campsites[campsite_id] = {
                    "name": campsite_info.get("campsite_name", f"Site {campsite_id}"),
                    "type": campsite_info.get("campsite_type", "Standard"),
                    "has_availability": True,
                    "available_dates": available_nights,
                    "availabilities": {k: v for k, v in availabilities.items() if k in date_range}
                }
        
        return available_campsites


recreation_api = RecreationGovAPI()
