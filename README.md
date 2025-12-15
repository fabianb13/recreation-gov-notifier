# Recreation.gov Campsite Availability Notifier

A full-stack application that monitors Recreation.gov for campsite availability and sends notifications when sites become available.

## Features

- 🏕️ **Campsite Monitoring**: Track multiple campgrounds by URL or facility ID
- 📧 **Email Notifications**: Get notified via email when sites become available
- 📱 **SMS Notifications**: Receive text message alerts via Twilio
- 📊 **Historical Analytics**: View availability trends by week of year
- ⚙️ **Configurable Polling**: Adjust check frequency from the UI
- 🔐 **User Authentication**: Secure accounts with JWT-based auth
- 🐳 **Docker Deployment**: Easy deployment with Docker Compose

## Architecture

- **Backend**: Python FastAPI with MongoDB
- **Frontend**: React with Recharts for visualizations
- **Database**: MongoDB for storing users, notifications, and analytics
- **Notifications**: Twilio (SMS) and SMTP (Email)
- **Scheduler**: APScheduler for automated polling

## Prerequisites

- Docker and Docker Compose
- Recreation.gov API key (in `.env`)
- Twilio account (for SMS notifications)
- Gmail account or SMTP server (for email notifications)

## Quick Start with Docker

1. **Clone the repository and configure environment**:
   ```bash
   # .env file is already configured with your credentials
   ```

2. **Build and start all services**:
   ```bash
   docker-compose up --build
   ```

3. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Manual Setup (Development)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # On Windows
# source venv/bin/activate  # On Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Start MongoDB (if not using Docker)
# Make sure MongoDB is running on localhost:27017

# Run the backend
python main.py
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

The frontend will be available at http://localhost:3000 and will proxy API requests to http://localhost:8000.

## Usage Guide

### 1. Register an Account

- Navigate to http://localhost:3000
- Click "Register" and create an account
- Optionally add your phone number for SMS notifications

### 2. Add a Campsite

- Go to the Dashboard
- Enter a Recreation.gov campground URL (e.g., `https://www.recreation.gov/camping/campgrounds/232447`)
- Or just enter the facility ID (e.g., `232447`)
- Select your desired date range
- Choose notification preferences (Email/SMS)
- Click "Add Notification Request"

### 3. Monitor Notifications

- The system will automatically check for availability at the configured interval
- When sites become available, you'll receive notifications via your selected methods
- View "Last Checked" and "Last Notified" timestamps on the dashboard

### 4. View Analytics

- Click "View Analytics" on any campsite
- See historical availability changes by week of the year
- Identify patterns in campsite availability

### 5. Configure Settings

- Go to Settings page
- Adjust the polling interval (60-3600 seconds)
- Shorter intervals = more responsive, but higher API usage

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /api/auth/me` - Get current user info

### Notifications
- `GET /api/notifications` - Get all notification requests
- `POST /api/notifications` - Create notification request
- `PUT /api/notifications/{id}` - Update notification preferences
- `DELETE /api/notifications/{id}` - Delete notification request

### Settings
- `GET /api/settings` - Get current settings
- `PUT /api/settings` - Update settings

### Analytics
- `GET /api/analytics/{facility_id}` - Get facility analytics

## Testing

### Backend Tests

```bash
cd backend
pytest test_auth.py -v
pytest test_recreation_api.py -v
pytest test_api.py -v
```

### Manual Testing

1. **Test Registration**:
   - Create a new account with valid email
   - Verify JWT token is stored
   - Check MongoDB for user document

2. **Test Campsite Addition**:
   - Add a valid Recreation.gov campground
   - Verify it appears in the notifications list
   - Check MongoDB `notification_requests` collection

3. **Test Polling**:
   - Wait for one polling cycle (default 5 minutes)
   - Check backend logs for "Checking X notification requests"
   - Verify `availability_history` collection is being populated

4. **Test Notifications**:
   - Add a popular campground with availability
   - Wait for polling cycle
   - Check email/SMS for notifications

5. **Test Analytics**:
   - After several polling cycles, click "View Analytics"
   - Verify chart displays with data
   - Check for weekly availability change counts

## Environment Variables

The `.env` file contains all configuration:

```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your.email@gmail.com

# Recreation.gov API
RECREATION_GOV_API_KEY=your_api_key

# MongoDB
MONGODB_URI=mongodb://mongo:27017
MONGODB_DB_NAME=recreation_notifier

# Application Settings
DEFAULT_SCRAPE_INTERVAL=300
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

## Database Schema

### Collections

#### users
```json
{
  "_id": ObjectId,
  "email": "user@example.com",
  "hashed_password": "...",
  "phone_number": "+1234567890",
  "created_at": ISODate
}
```

#### notification_requests
```json
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "facility_id": "232447",
  "facility_name": "Yosemite National Park",
  "start_date": "2024-07-01",
  "end_date": "2024-07-10",
  "notify_email": true,
  "notify_sms": false,
  "created_at": ISODate,
  "last_checked": ISODate,
  "last_notified": ISODate
}
```

#### availability_history
```json
{
  "_id": ObjectId,
  "facility_id": "232447",
  "timestamp": ISODate,
  "available_count": 5,
  "total_sites": 20,
  "available_sites": ["Site A", "Site B"],
  "full_data": {...}
}
```

## Troubleshooting

### Backend won't start
- Check MongoDB is running: `docker ps` or verify local MongoDB
- Verify all environment variables in `.env`
- Check port 8000 is not in use

### Frontend won't connect
- Verify backend is running on port 8000
- Check browser console for CORS errors
- Verify proxy setting in `package.json`

### No notifications received
- Check backend logs for errors
- Verify email/Twilio credentials are correct
- Test email settings with a simple send
- Ensure polling interval has passed
- Check that campsites have actual availability

### Analytics not showing
- Wait for multiple polling cycles to accumulate data
- Verify `availability_history` collection has documents
- Check that availability changes actually occurred

## Production Deployment

1. **Update environment variables**:
   - Change `JWT_SECRET_KEY` to a secure random string
   - Use production MongoDB (e.g., MongoDB Atlas)
   - Configure proper SMTP server

2. **Build production images**:
   ```bash
   docker-compose -f docker-compose.prod.yml up --build
   ```

3. **Set up reverse proxy** (nginx/Traefik) for HTTPS

4. **Monitor logs**:
   ```bash
   docker-compose logs -f backend
   ```

## License

MIT License

## Support

For issues or questions, please open a GitHub issue.
