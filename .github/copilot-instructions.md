# Recreation.gov Campsite Notifier - AI Agent Instructions

## Architecture Overview

**Stack**: FastAPI (backend) + React (frontend) + MongoDB + Docker
- **Backend** (`backend/`): Python FastAPI with APScheduler for polling Recreation.gov API
- **Frontend** (`frontend/`): React SPA with Recharts, communicates via REST API
- **Database**: MongoDB with async motor driver (collections: users, notification_requests, availability_history, push_subscriptions)
- **Deployment**: Docker Compose (3 services: mongo, backend, frontend)

**Data Flow**: Scheduler polls Recreation.gov API → Stores availability_history → Compares with previous check → Sends notifications (email/SMS/push) if newly available → Updates last_checked/last_notified timestamps

## Critical Rate Limiting Pattern

**Recreation.gov API enforces 50 req/min**. We use a thread-safe token bucket (`backend/rate_limiter.py`):
- Conservative limit: 35 tokens/min (35 requests per minute)
- `rate_limiter.acquire_with_wait(tokens=1)` blocks until token available (~1.71s per request)
- Global singleton instance used in `recreation_api.py`
- Never bypass this - always call `_acquire_rate_limit_token()` before Recreation.gov API calls

**Retry Logic with Exponential Backoff** (`_make_request_with_retry` in `recreation_api.py`):
- MAX_RETRIES = 3, INITIAL_RETRY_DELAY = 5s
- Delay doubles each retry: 5s → 10s → 20s
- On 429 (rate limit): reads `Retry-After` header, adds extra 2s pause
- On timeout/5xx: retries with exponential backoff
- Logs all retries with emoji indicators (⚠️ for warnings, ❌ for failures)

**Multi-month queries**: Date ranges spanning months require separate API calls per month. Cap to 12 months max (`MAX_MONTHS_PER_QUERY`), cap end date to 2 years from today (API limit).

## Key Backend Patterns

### Async MongoDB Operations
All DB operations use async/await with motor:
```python
await db.collection_name.find_one({"field": value})
await db.collection_name.insert_one(document)
```

### Authentication Flow
- JWT tokens stored in localStorage (frontend)
- Backend uses `get_current_user()` dependency for protected endpoints
- CORS allows all origins (`allow_origins=["*"]`) for local network/mobile access

### Notification System
Three notification types (email/SMS/push) in `backend/notifications.py`:
- Each has `send_availability_notification(to, facility_name, available_sites, dates, facility_id, available_dates)`
- `available_dates` (ISO strings) formatted by `format_available_dates()` → groups sequential dates (e.g., "June 15-18, June 20")
- Email includes HTML with "Book Now" button linking to `https://www.recreation.gov/camping/campgrounds/{facility_id}`

### Scheduler Pattern (`backend/scheduler.py`)
- APScheduler runs `check_all_notifications()` every 300s (configurable)
- For each notification_request: calls `recreation_api.check_availability()` → stores in availability_history → compares with previous → sends notifications if newly available
- Push notifications: queries all user's push_subscriptions, sends to each, auto-removes expired (410 responses)

## Frontend Patterns

### Dynamic API URL for Mobile
```javascript
// frontend/src/api.js and pushNotifications.js
const getApiUrl = () => {
  const protocol = window.location.protocol;
  const hostname = window.location.hostname;
  return `${protocol}//${hostname}:8000`;
};
```
This ensures Android/mobile devices can access backend using IP instead of localhost.

### Service Worker for Push Notifications
- `public/service-worker.js` handles push events in background
- Requires HTTPS on mobile (HTTP works only on localhost)
- `isPushSupported()` checks for secure context: `window.isSecureContext || hostname === 'localhost'`

## Development Workflows

### Docker Commands
```bash
docker-compose up -d                    # Start all services
docker restart recreation-backend       # Restart after backend code changes
docker-compose restart frontend         # Restart after frontend changes
docker logs recreation-backend --tail 50  # View backend logs
docker exec recreation-mongo mongosh recreation_notifier --eval "db.notification_requests.find().pretty()"
```

### Backend Development
- Python 3.11+ required
- Auto-reload enabled in Docker (`--reload` flag)
- Test with `pytest test_*.py -v`
- Environment vars in `.env` (never commit with real credentials)

### Frontend Development
- React 18.2.0, runs on port 3000
- `DANGEROUSLY_DISABLE_HOST_CHECK=true` allows access via IP/hostname
- Environment var `HOST=0.0.0.0` binds to all interfaces for network access

## Database Indexes
Already created in `backend/database.py`:
- `users.email` (unique)
- `notification_requests.user_id + facility_id`
- `availability_history.facility_id + timestamp` (compound, descending on timestamp)

## Important File Dependencies

**Backend Core Flow**:
1. `main.py` → defines FastAPI app, CORS (allow all), endpoints
2. `scheduler.py` → imports `recreation_api`, `notifications`, uses `database.get_database()`
3. `recreation_api.py` → imports `rate_limiter`, must call `_acquire_rate_limit_token()` before requests
4. `notifications.py` → defines EmailService, SMSService, WebPushService with singleton instances

**Frontend Core Flow**:
1. `App.js` → React Router, AuthProvider wraps routes
2. `api.js` → Axios instance with auth interceptor, dynamic API URL
3. `Dashboard.js` → Main UI, calls `notificationsAPI.getAll()`, includes `PushNotificationToggle`
4. `pushNotifications.js` → Service worker registration, VAPID subscription, dynamic API URL

## Common Modifications

**Add new notification field**: 
1. Update `models.py` NotificationRequestResponse
2. Update `main.py` GET /api/notifications to fetch data
3. Update `Dashboard.js` to display field
4. Restart backend + frontend

**Change rate limit**: Edit `rate_limiter.py` global instance: `rate_limiter = TokenBucketRateLimiter(rate=35.0, capacity=35)`

**Add new API endpoint**: 
1. Add to `main.py` with `@app.get/post/put/delete`
2. Use `current_user: dict = Depends(get_current_user)` for auth
3. Add to `frontend/src/api.js` export object

## Known Edge Cases

1. **Push notifications on mobile**: Requires HTTPS (not HTTP). Show clear error: "Push notifications require HTTPS" via `getPushSupportInfo()`
2. **Date ranges > 2 years**: Recreation.gov API rejects. Cap in `recreation_api.py` with `max_api_date = today + timedelta(days=730)`
3. **Multiple consecutive nights**: `min_nights` parameter filters results in `get_campsite_availability_for_dates()` - only returns sites with ≥ min_nights consecutive available dates
4. **Stale dashboard data**: Cache-control headers added to `/api/notifications`: `Cache-Control: no-cache, no-store, must-revalidate`

## Testing Strategy

### Backend Tests
- **Unit Tests**: `test_auth.py`, `test_recreation_api.py` - test individual functions with mocks
- **Integration Tests**: `test_integration.py` - test full flow with real MongoDB
- **API Tests**: `test_api.py` - test FastAPI endpoints with TestClient
- **Direct API Tests**: `test_rec_direct.py` - test Recreation.gov API calls (respects rate limits)

**Pattern**: Use `pytest` with async support (`pytest-asyncio`). Mock external services (Twilio, SMTP) in unit tests.

**Run tests**:
```bash
cd backend
pytest test_auth.py -v              # Auth tests only
pytest test_recreation_api.py -v    # API client tests
pytest -v                            # All tests
```

### Frontend Testing
- Manual testing via browser DevTools
- Check React component rendering in browser console
- Test API calls with Network tab
- Verify service worker registration in Application tab

## Web Push Notifications Setup

**VAPID Keys** (Voluntary Application Server Identification):
1. Generate keys once: `python backend/generate_vapid_keys.py`
2. Add to `.env`:
   ```
   VAPID_PRIVATE_KEY=<private_key>
   VAPID_PUBLIC_KEY=<public_key>
   VAPID_CLAIMS={"sub":"mailto:your@email.com"}
   ```
3. Keys authenticate your server to push services (Google, Mozilla, Apple)
4. Never regenerate in production - invalidates all existing subscriptions

**Service Worker Lifecycle**:
- Registered on first visit: `navigator.serviceWorker.register('/service-worker.js')`
- Handles `push` events even when browser closed
- Subscription stored in MongoDB `push_subscriptions` collection
- Expired subscriptions (410 status) auto-removed by scheduler

## Error Handling Patterns

### Backend Conventions
```python
# Always wrap external API calls in try/except
try:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
except requests.exceptions.Timeout:
    print(f"⏱️ Request timed out: {url}")
    # Retry with exponential backoff
except requests.exceptions.RequestException as e:
    print(f"❌ Request failed: {e}")
    # Log and continue or retry
```

**Logging Patterns**:
- Use emoji for quick visual scanning: ✅ success, ⚠️ warning, ❌ error, 🔍 checking, 📊 stats
- Include context: facility_id, request counts, timestamps
- Print to stdout (captured by Docker logs)

### Frontend Error Handling
```javascript
try {
  await api.post('/endpoint', data);
  setSuccess('Operation completed');
} catch (err) {
  const message = err.response?.data?.detail || 'Operation failed';
  setError(message);
  console.error('Detailed error:', err);
}
```

**User-facing errors**: Always provide actionable messages (e.g., "Push notifications require HTTPS" not "Push failed")

## MongoDB Schema Evolution

**Backward Compatibility Pattern**:
1. **Adding optional fields**: Use `Optional[type] = None` in Pydantic models, set default in responses
   ```python
   # models.py
   notify_push: bool = True  # Default for documents missing this field
   ```

2. **Reading documents**: Handle missing fields gracefully
   ```python
   request.get("min_nights", 1)  # Default to 1 if not present
   ```

3. **Migration approach**: No formal migrations - code handles both old and new schemas
   - Old documents work without modification
   - New documents include all fields
   - Gradual transition as documents are updated

4. **Index updates**: Add indexes in `database.py` `connect_to_mongo()`:
   ```python
   await db.collection_name.create_index([("field1", 1), ("field2", -1)])
   ```

**When to restart**: Backend needs restart to apply model changes, but MongoDB documents don't need migration.

## Testing Recreation.gov API
Use `test_recreation_api.py` or `test_rec_direct.py` for direct API testing. Always respect rate limits even in tests.
