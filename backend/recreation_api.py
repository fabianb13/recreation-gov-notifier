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
        """Format datetime object to Recreation.gov API format for request parameters"""
        # Output format: YYYY-MM-DDTHH:MM:SS.000Z (with milliseconds for API request)
        return date_obj.strftime("%Y-%m-%dT00:00:00.000Z")
    
    def format_date_for_comparison(self, date_obj: datetime) -> str:
        """Format datetime object for comparing with API response data"""
        # Output format: YYYY-MM-DDTHH:MM:SSZ (without milliseconds to match API response)
        return date_obj.strftime("%Y-%m-%dT00:00:00Z")
    
    def format_date_for_response(self, date_str: str) -> str:
        """Format date string to match API response format"""
        # Convert YYYY-MM-DD to YYYY-MM-DDTHH:MM:SSZ
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            return self.format_date_for_comparison(date_obj)
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
        
        Note: Recreation.gov API only supports dates up to 2 years in the future.
        Dates beyond this limit will be capped automatically.
        """
        try:
            # Parse input dates
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            # Recreation.gov API only supports dates up to 2 years from today
            today = datetime.now()
            max_api_date = today + timedelta(days=730)  # 2 years = 730 days
            
            # Cap the end date to the API limit
            original_end_dt = end_dt
            if end_dt > max_api_date:
                print(f"Warning: End date {end_date} is beyond API limit (2 years). Capping to {max_api_date.strftime('%Y-%m-%d')}")
                end_dt = max_api_date
            
            # Don't query API if start date is already beyond the limit
            if start_dt > max_api_date:
                print(f"Warning: Start date {start_date} is beyond API limit (2 years). No data available.")
                return {
                    "facility_id": facility_id,
                    "count": 0,
                    "campsites": {},
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True,
                    "capped_date": True,
                    "beyond_api_limit": True
                }
            
            # Get first of month for start date
            start_of_month = datetime(start_dt.year, start_dt.month, 1)
            
            # Get all months we need to query (within API limit)
            months = list(rrule.rrule(rrule.MONTHLY, dtstart=start_of_month, until=end_dt))
            
            print(f"Checking availability for facility {facility_id} from {start_date} to {end_dt.strftime('%Y-%m-%d')}")
            if original_end_dt != end_dt:
                print(f"  (Original end date {original_end_dt.strftime('%Y-%m-%d')} capped due to API limit)")
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
            
            result = {
                "facility_id": facility_id,
                "count": total_count,
                "campsites": all_campsites_data,
                "timestamp": datetime.utcnow().isoformat(),
                "success": True
            }
            
            # Add metadata if date was capped
            if original_end_dt != end_dt:
                result["capped_date"] = True
                result["requested_end_date"] = original_end_dt.strftime("%Y-%m-%d")
                result["actual_end_date"] = end_dt.strftime("%Y-%m-%d")
            
            return result
                
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
    
    def get_campsite_availability_for_dates(self, campsites_data: Dict, start_date: str, end_date: str, min_nights: int = 1) -> Dict:
        """
        Parse availability data for specific date range
        A campsite is considered available if at least min_nights consecutive nights are available
        Returns dict of campsite_id -> availability status
        
        Args:
            campsites_data: Dictionary of campsite data from API
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format  
            min_nights: Minimum number of consecutive nights required (default: 1)
            
        Note: Only dates within the API's 2-year window will have actual availability data.
        Dates beyond 2 years are assumed unavailable.
        """
        available_campsites = {}
        
        # Generate list of dates in the range (formatted for comparison with API response)
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        num_days = (end_dt - start_dt).days
        
        # Calculate API limit (2 years from today)
        today = datetime.now()
        max_api_date = today + timedelta(days=730)
        
        # Create ordered list of dates to check (excluding end_date since it's the checkout day)
        # Format as YYYY-MM-DDTHH:MM:SSZ to match API response format (no milliseconds)
        date_range = []
        for i in range(num_days):
            check_date = start_dt + timedelta(days=i)
            date_range.append(self.format_date_for_comparison(check_date))
        
        if not date_range or min_nights < 1:
            return available_campsites
        
        for campsite_id, campsite_info in campsites_data.items():
            availabilities = campsite_info.get("availabilities", {})
            
            # Find consecutive available nights
            consecutive_nights = 0
            max_consecutive = 0
            consecutive_sequences = []
            current_sequence = []
            
            for check_date in date_range:
                # Check if this date is beyond the API limit
                check_dt = datetime.strptime(check_date, "%Y-%m-%dT%H:%M:%SZ")
                is_beyond_api_limit = check_dt > max_api_date
                
                # Dates beyond API limit are assumed unavailable
                if is_beyond_api_limit:
                    status = "Not Available"
                else:
                    status = availabilities.get(check_date, "Not Available")
                
                if status == "Available":
                    consecutive_nights += 1
                    current_sequence.append(check_date)
                    max_consecutive = max(max_consecutive, consecutive_nights)
                else:
                    if len(current_sequence) >= min_nights:
                        consecutive_sequences.append(current_sequence[:])
                    current_sequence = []
                    consecutive_nights = 0
            
            # Check final sequence
            if len(current_sequence) >= min_nights:
                consecutive_sequences.append(current_sequence[:])
            
            # Campsite is available if we found at least one sequence of min_nights or more
            if max_consecutive >= min_nights and consecutive_sequences:
                # Use the longest sequence for the response
                longest_sequence = max(consecutive_sequences, key=len)
                available_campsites[campsite_id] = {
                    "name": campsite_info.get("campsite_name", f"Site {campsite_id}"),
                    "type": campsite_info.get("campsite_type", "Standard"),
                    "has_availability": True,
                    "available_dates": longest_sequence,
                    "consecutive_nights": len(longest_sequence),
                    "all_available_sequences": consecutive_sequences,
                    "availabilities": {k: v for k, v in availabilities.items() if k in date_range}
                }
        
        return available_campsites


recreation_api = RecreationGovAPI()
