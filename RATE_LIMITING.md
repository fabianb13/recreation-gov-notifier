# Recreation.gov API Rate Limiting - Implementation

## Overview
The Recreation.gov API has a rate limit of **50 requests per minute**. This implementation includes comprehensive rate limiting, retry logic, and error handling to ensure reliable operation.

## Implemented Features

### 1. ✅ Rate Limiting (Client-Side)
- **Enforced Interval**: 1.3 seconds between requests (50 req/min = 1.2s + 0.1s buffer)
- **Request Tracking**: Monitors request count and timing
- Automatically waits between requests to stay under the limit

### 2. ✅ Retry Logic with Exponential Backoff
- **Max Retries**: 3 attempts per request
- **Initial Delay**: 2 seconds
- **Exponential Growth**: Each retry doubles the wait time (2s → 4s → 8s)
- **Jitter**: Random 0-1 second added to avoid thundering herd problem

### 3. ✅ HTTP 429 (Rate Limit) Handling
- Automatically detects 429 responses
- Reads `Retry-After` header when provided by the API
- Falls back to exponential backoff if no header present
- Skips the request after max retries to continue with other data

### 4. ✅ Improved User-Agent
- Changed from browser UA to: `RecreationGovNotifier/1.0 (Campsite Availability Monitoring Service)`
- More transparent and follows API best practices
- Includes Accept-Encoding header for compression

### 5. ✅ Server Error (5xx) Handling
- Automatic retry for temporary server errors
- Exponential backoff between retries
- Graceful degradation if server continues to fail

### 6. ✅ Timeout Handling
- 15-second timeout for availability requests
- 10-second timeout for facility info requests
- Automatic retry on timeout with backoff

### 7. ✅ Request Exception Handling
- Network errors are caught and retried
- Connection errors trigger exponential backoff
- Detailed logging of all errors

## How It Works

### Request Flow
```
1. Check rate limit → Wait if needed
2. Make HTTP request
3. If 429/5xx/timeout → Retry with backoff
4. If success → Return response
5. If max retries → Log error and continue
```

### Rate Limiting Example
```
Request #1: Immediate
Request #2: Wait 1.3s
Request #3: Wait 1.3s
...
Total: ~46 requests/minute (safe margin)
```

### Exponential Backoff Example
```
Attempt 1: Request fails → Wait 2s + 0.5s jitter
Attempt 2: Request fails → Wait 4s + 0.3s jitter
Attempt 3: Request fails → Wait 8s + 0.7s jitter
Attempt 4: Give up, log error
```

### Retry-After Header Example
```
Response: 429 Too Many Requests
Retry-After: 60

Action: Wait 60 seconds, then retry
```

## Benefits

### ✅ Prevents 429 Errors
- Client-side throttling keeps you under the limit
- Even if you query multiple months, rate limiting prevents overload

### ✅ Handles Temporary Failures
- Server glitches don't break your monitoring
- Network blips are automatically retried
- API rate limit bursts are handled gracefully

### ✅ Efficient Resource Usage
- Only waits when necessary
- Jitter prevents synchronized retries across instances
- Continues processing other data when one request fails

### ✅ Better Debugging
- Detailed logs show:
  - Request count
  - Wait times
  - Retry attempts
  - Error reasons

## Scheduler Impact

### Before Rate Limiting
```
Query 12 months → 12 requests in ~5 seconds → Potential 429 errors
```

### After Rate Limiting
```
Query 12 months → 12 requests in ~16 seconds → No 429 errors
Total: Still completes in under 20 seconds per notification
```

### Multiple Notifications
If you have 5 notification requests:
- **Before**: Could hit rate limit with parallel requests
- **After**: Sequential processing with rate limiting ensures stability
- **Impact**: Each check cycle may take 1-2 minutes longer, but no failures

## Configuration

All rate limiting is configured in `RecreationGovAPI` class:

```python
MIN_REQUEST_INTERVAL = 1.3  # seconds between requests
MAX_RETRIES = 3             # retry attempts
INITIAL_RETRY_DELAY = 2     # seconds before first retry
```

## Monitoring

Check logs for rate limiting activity:
```bash
docker logs recreation-backend | grep -i "rate"
```

You'll see messages like:
- `Rate limiting: waiting 0.85 seconds before next request`
- `Rate limited (429). Retry-After header: 60 seconds`
- `Rate limited (429). Using exponential backoff: 4 seconds`

## Best Practices

1. **Don't disable rate limiting** - It protects your service
2. **Monitor request counts** - Watch logs during peak usage
3. **Space out checks** - Default 300s interval is good
4. **Limit date ranges** - Shorter ranges = fewer API calls
5. **Be patient** - Retries may add time but ensure reliability

## Troubleshooting

### Still Getting 429 Errors
- Check if multiple instances are running
- Verify scheduler interval isn't too aggressive
- Review logs for actual request rate

### Slow Response Times
- This is expected with rate limiting
- Each month query adds 1.3s minimum
- Consider reducing number of monitored sites or date ranges

### Requests Timing Out
- Network issue, not rate limiting
- Check internet connection
- Recreation.gov might be slow/down

## Summary

The implementation now:
- ✅ Respects Recreation.gov's 50 req/min limit
- ✅ Handles rate limit errors gracefully
- ✅ Retries failed requests intelligently
- ✅ Uses proper User-Agent identification
- ✅ Provides detailed logging
- ✅ Continues working even during API issues

Your campsite monitoring service is now production-ready and API-friendly! 🏕️
