import requests
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from dateutil import rrule
from config import settings
import re
import time
import random
from proxy_manager import proxy_manager, ProxyInfo
from fake_useragent import UserAgent

STANDARD_HEADERS: Dict[str, str] = {
    "Accept": "application/json, text/plain, */*",
    # No "br": requests can't decode brotli without an extra package
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.9,la;q=0.8",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

API_REFERRERS: Dict[str, str] = {"Referer": "https://www.recreation.gov/"}

class RecreationGovAPI:
    BASE_URL = "https://www.recreation.gov"
    AVAILABILITY_ENDPOINT = "/api/camps/availability/campground/{}/month"
    CAMPGROUND_ENDPOINT = "/api/camps/campgrounds/{}"
    
    # Use SOCKS5 proxies with per-proxy rate limiting
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 5  # Increased from 2 to 5 seconds
    
    def __init__(self):
        self.request_count = 0
        self.user_agent = UserAgent(browsers=["chrome"])
    
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
    
    def _acquire_proxy_with_rate_limit(self) -> Optional[Tuple[ProxyInfo, Dict[str, str]]]:
        """Acquire proxy and rate limit token before making a request"""
        result = proxy_manager.acquire_with_proxy()
        if not result:
            print(f"❌ No proxies available")
            return None
        
        proxy, wait_time = result
        if wait_time > 0.1:
            print(f"Rate limiter: waited {wait_time:.2f}s for proxy {proxy.ip} (tokens: {proxy.rate_limiter.get_available_tokens():.1f})")
        
        self.request_count += 1
        return proxy, proxy.get_proxies_dict()
    
    def _make_request_with_retry(self, url: str, params: dict = None, timeout: int = 30) -> Optional[requests.Response]:
        """Make HTTP request with retry logic, exponential backoff, SOCKS5 proxy, and per-proxy rate limiting"""
        for attempt in range(self.MAX_RETRIES):
            try:
                # Acquire proxy and rate limit token (blocks until available)
                proxy_result = self._acquire_proxy_with_rate_limit()
                if not proxy_result:
                    print(f"❌ Failed to acquire proxy for request")
                    return None
                
                proxy, proxies_dict = proxy_result
                
                # Make the request through SOCKS5 proxy
                # BUILD THE HEADERS EXPECTED FROM THE API
                user_agent = {"User-Agent": self.user_agent.random}
                headers = STANDARD_HEADERS.copy()
                headers.update(user_agent)
                headers.update(API_REFERRERS)
                try:
                    response = requests.get(url, params=params, headers=headers, proxies=proxies_dict, timeout=timeout)
                except requests.exceptions.RequestException:
                    proxy_manager.report_failure(proxy)
                    raise
                proxy_manager.report_success(proxy)
                
                # Handle rate limiting (429)
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                            print(f"⚠️ Rate limited (429). Retry-After header: {wait_time} seconds")
                        except ValueError:
                            # Retry-After might be a date, use longer backoff
                            wait_time = self.INITIAL_RETRY_DELAY * (2 ** attempt)
                    else:
                        # No Retry-After header, use exponential backoff starting at 5s
                        wait_time = self.INITIAL_RETRY_DELAY * (2 ** attempt)
                        print(f"⚠️ Rate limited (429). Using exponential backoff: {wait_time} seconds")
                    
                    if attempt < self.MAX_RETRIES - 1:
                        # Add jitter and extra padding to avoid thundering herd
                        jitter = random.uniform(0, 2)
                        total_wait = wait_time + jitter
                        print(f"⏳ Waiting {total_wait:.2f} seconds before retry {attempt + 1}/{self.MAX_RETRIES}")
                        print(f"💡 Proxy {proxy.ip} rate limiter tokens: {proxy.rate_limiter.get_available_tokens():.1f}")
                        time.sleep(total_wait)
                        # Give rate limiter time to refill
                        time.sleep(2)
                        continue
                    else:
                        print(f"❌ Max retries reached for rate limited request")
                        return response
                
                # Handle server errors (5xx) with retry
                if 500 <= response.status_code < 600:
                    if attempt < self.MAX_RETRIES - 1:
                        wait_time = self.INITIAL_RETRY_DELAY * (2 ** attempt)
                        jitter = random.uniform(0, 1)
                        total_wait = wait_time + jitter
                        print(f"Server error {response.status_code}. Retrying in {total_wait:.2f} seconds (attempt {attempt + 1}/{self.MAX_RETRIES})")
                        time.sleep(total_wait)
                        continue
                    else:
                        print(f"Max retries reached for server error {response.status_code}")
                        return response
                
                # Success or client error (not retryable)
                return response
                
            except requests.exceptions.Timeout:
                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.INITIAL_RETRY_DELAY * (2 ** attempt)
                    print(f"Request timeout. Retrying in {wait_time} seconds (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Max retries reached for timeout")
                    raise
            
            except requests.exceptions.RequestException as e:
                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.INITIAL_RETRY_DELAY * (2 ** attempt)
                    print(f"Request error: {e}. Retrying in {wait_time} seconds (attempt {attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Max retries reached for request error")
                    raise
        
        return None
    
    def get_facility(self, facility_id: str) -> Optional[Dict]:
        """Get facility/campground information by ID"""
        try:
            url = self.BASE_URL + self.CAMPGROUND_ENDPOINT.format(facility_id)
            response = self._make_request_with_retry(url, timeout=10)
            if not response or response.status_code != 200:
                print(f"Error fetching facility {facility_id}: Status {response.status_code if response else 'No response'}")
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
            
            # Past dates can't be booked and the API rejects past months with 400
            today_date = datetime(today.year, today.month, today.day)
            if end_dt < today_date:
                print(f"⏭️ Skipping facility {facility_id}: date range {start_date} to {end_date} is entirely in the past")
                return {
                    "facility_id": facility_id,
                    "count": 0,
                    "campsites": {},
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True,
                    "date_range_expired": True
                }
            start_dt = max(start_dt, today_date)
            
            # Get first of month for start date
            start_of_month = datetime(start_dt.year, start_dt.month, 1)
            
            # Get all months we need to query (within API limit)
            months = list(rrule.rrule(rrule.MONTHLY, dtstart=start_of_month, until=end_dt))
            
            # Limit to 12 months per query to avoid excessive API calls
            MAX_MONTHS_PER_QUERY = 12
            if len(months) > MAX_MONTHS_PER_QUERY:
                print(f"⚠️ Date range spans {len(months)} months. Limiting to first {MAX_MONTHS_PER_QUERY} months to avoid rate limits.")
                months = months[:MAX_MONTHS_PER_QUERY]
                end_dt = months[-1]
            
            print(f"🔍 Checking availability for facility {facility_id} from {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}")
            if original_end_dt != end_dt:
                print(f"  (Original end date {original_end_dt.strftime('%Y-%m-%d')} capped due to API limit)")
            
            # Show proxy pool stats
            proxy_stats = proxy_manager.get_stats()
            if proxy_stats.get("initialized"):
                print(f"📅 Need to query {len(months)} month(s) - Using {proxy_stats['healthy_proxies']}/{proxy_stats['total_proxies']} healthy SOCKS5 proxies")
            else:
                print(f"📅 Need to query {len(months)} month(s) - Proxies not initialized")
            
            # Collect data from all months
            all_campsites_data = {}
            total_count = 0
            
            for idx, month_date in enumerate(months, 1):
                url = self.BASE_URL + self.AVAILABILITY_ENDPOINT.format(facility_id)
                params = {"start_date": self.format_date_for_request(month_date)}
                
                print(f"📆 Querying month {idx}/{len(months)}: {month_date.strftime('%Y-%m')} (total requests: #{self.request_count + 1})")
                
                response = self._make_request_with_retry(url, params=params, timeout=15)
                
                # A 4xx Response is falsy, so compare against None explicitly
                if response is None:
                    # None only happens when no healthy proxy is available; partial data could trigger false alerts
                    print(f"🛑 No healthy proxies available. Skipping facility {facility_id} until next cycle.")
                    return {
                        "facility_id": facility_id,
                        "count": 0,
                        "campsites": {},
                        "timestamp": datetime.utcnow().isoformat(),
                        "error": "No healthy proxies available",
                        "success": False
                    }
                
                if response.status_code == 429:
                    print(f"🛑 Rate limit exceeded even after retries. Skipping remaining months to avoid further rate limiting.")
                    print(f"💡 Processed {idx-1}/{len(months)} months successfully")
                    break
                
                if response.status_code != 200:
                    print(f"Error: Received status code {response.status_code} from {url}")
                    print(f"Response: {response.text[:500]}...")  # Truncate long responses
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
                print(f"❌ No data returned from API for facility {facility_id}")
                return {
                    "facility_id": facility_id,
                    "count": 0,
                    "campsites": {},
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": "No data returned from API",
                    "success": False
                }
            
            print(f"✅ Successfully retrieved data for {len(all_campsites_data)} campsites")
            
            # Show proxy pool stats after requests
            proxy_stats = proxy_manager.get_stats()
            if proxy_stats.get("initialized"):
                print(f"📊 Proxy pool status: {proxy_stats['total_requests']} total requests across {proxy_stats['total_proxies']} proxy/proxies")
            
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
        
        # Only dates from today through the API's 2-year window can have availability
        today = datetime.now()
        today_date = datetime(today.year, today.month, today.day)
        max_api_date = today + timedelta(days=730)
        start_dt = max(datetime.strptime(start_date, "%Y-%m-%d"), today_date)
        end_dt = min(datetime.strptime(end_date, "%Y-%m-%d"), max_api_date + timedelta(days=1))
        num_days = (end_dt - start_dt).days
        
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
