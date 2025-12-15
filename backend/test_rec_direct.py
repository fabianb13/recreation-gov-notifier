import requests
from datetime import datetime, timedelta

# Try with past dates in camping season
start = '2024-06-01T00:00:00Z'
end = '2024-06-05T00:00:00Z'
url = 'https://www.recreation.gov/api/camps/availability/campground/232447'
params = {'start_date': start, 'end_date': end}
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print(f'Testing Upper Pines (Yosemite): {url}')
print(f'Dates: {start} to {end}')
resp = requests.get(url, params=params, headers=headers, timeout=10)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.json()
    print(f'Count: {data.get("count", 0)}')
    print(f'Campsites keys: {len(data.get("campsites", {}))}')
    if data.get("campsites"):
        first_site_id = list(data["campsites"].keys())[0]
        first_site = data["campsites"][first_site_id]
        print(f'First site: {first_site_id}')
        print(f'Site name: {first_site.get("site", "N/A")}')
        print(f'Availabilities: {len(first_site.get("availabilities", {}))} dates')
else:
    print(f'Response: {resp.text}')
