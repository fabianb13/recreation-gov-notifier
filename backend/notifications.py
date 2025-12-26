import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
from pywebpush import webpush, WebPushException
from config import settings
from typing import List, Optional
import json
from datetime import datetime, timedelta
import base64
import tempfile
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


def format_available_dates(dates: List[str], max_dates: int = 10) -> str:
    """Format available dates, grouping sequential dates together.
    
    Args:
        dates: List of date strings in ISO format (YYYY-MM-DDTHH:MM:SSZ)
        max_dates: Maximum number of dates/groups to include
        
    Returns:
        Formatted string like "June 15-18, June 20, July 1-5"
    """
    if not dates:
        return "No specific dates"
    
    # Parse and sort dates
    parsed_dates = []
    for date_str in dates:
        try:
            # Handle ISO format with or without milliseconds
            if '.' in date_str:
                dt = datetime.strptime(date_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
            else:
                dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
            parsed_dates.append(dt)
        except:
            continue
    
    if not parsed_dates:
        return "No specific dates"
    
    parsed_dates.sort()
    
    # Limit to first max_dates individual dates
    if len(parsed_dates) > max_dates:
        parsed_dates = parsed_dates[:max_dates]
    
    # Group sequential dates
    groups = []
    current_group = [parsed_dates[0]]
    
    for i in range(1, len(parsed_dates)):
        # Check if this date is consecutive to the previous one
        if (parsed_dates[i] - current_group[-1]).days == 1:
            current_group.append(parsed_dates[i])
        else:
            groups.append(current_group)
            current_group = [parsed_dates[i]]
    
    groups.append(current_group)
    
    # Format each group
    formatted = []
    for group in groups:
        if len(group) == 1:
            # Single date
            formatted.append(group[0].strftime("%b %d"))
        else:
            # Range of dates
            start = group[0]
            end = group[-1]
            if start.month == end.month:
                # Same month: "June 15-18"
                formatted.append(f"{start.strftime('%b %d')}-{end.strftime('%d')}")
            else:
                # Different months: "June 30-July 2"
                formatted.append(f"{start.strftime('%b %d')}-{end.strftime('%b %d')}")
    
    result = ", ".join(formatted)
    
    # Add indicator if there are more dates
    if len(dates) > max_dates:
        result += f" (+{len(dates) - max_dates} more)"
    
    return result


class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.username = settings.SMTP_USERNAME
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.EMAIL_FROM
    
    def send_email(self, to_email: str, subject: str, body: str, html: bool = True):
        """Send an email notification"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            if html:
                html_part = MIMEText(body, 'html')
                msg.attach(html_part)
            else:
                text_part = MIMEText(body, 'plain')
                msg.attach(text_part)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            print(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            print(f"Error sending email to {to_email}: {e}")
            return False
    
    def send_availability_notification(self, to_email: str, facility_name: str, 
                                      available_sites: List[str], dates: str, facility_id: str = None,
                                      available_dates: Optional[List[str]] = None):
        """Send availability notification email"""
        subject = f"Campsite Available: {facility_name}"
        
        sites_list = "\n".join([f"<li>{site}</li>" for site in available_sites])
        
        # Build campground URL if facility_id is provided
        campground_url = f"https://www.recreation.gov/camping/campgrounds/{facility_id}" if facility_id else "https://www.recreation.gov"
        
        # Format available dates
        formatted_dates = format_available_dates(available_dates or [], max_dates=10) if available_dates else None
        dates_section = f"<p><strong>Available Dates:</strong> {formatted_dates}</p>" if formatted_dates else ""
        
        body = f"""
        <html>
        <body>
            <h2>Good news! Campsites are now available!</h2>
            <p><strong>Campground:</strong> {facility_name}</p>
            <p><strong>Search Period:</strong> {dates}</p>
            {dates_section}
            <p><strong>Available Sites:</strong></p>
            <ul>
                {sites_list}
            </ul>
            <p><a href="{campground_url}" style="display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; margin-top: 10px;">Book Now on Recreation.gov</a></p>
            <hr>
            <p style="color: gray; font-size: 12px;">
                This is an automated notification from your Recreation.gov Campsite Notifier.
            </p>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, body, html=True)


class SMSService:
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_PHONE_NUMBER
        self.client = Client(self.account_sid, self.auth_token)
    
    def send_sms(self, to_number: str, message: str):
        """Send an SMS notification"""
        try:
            message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            print(f"SMS sent successfully to {to_number}: {message.sid}")
            return True
        except Exception as e:
            print(f"Error sending SMS to {to_number}: {e}")
            return False
    
    def send_availability_notification(self, to_number: str, facility_name: str, 
                                      available_sites: List[str], dates: str, facility_id: str = None,
                                      available_dates: Optional[List[str]] = None):
        """Send availability notification SMS"""
        sites_str = ", ".join(available_sites[:3])  # Limit to 3 sites for SMS
        if len(available_sites) > 3:
            sites_str += f" and {len(available_sites) - 3} more"
        
        # Format available dates (limit to 5 for SMS)
        formatted_dates = format_available_dates(available_dates or [], max_dates=5) if available_dates else ""
        dates_part = f" Dates: {formatted_dates}." if formatted_dates else "."
        
        # Include direct campground URL if available
        url = f"recreation.gov/camping/campgrounds/{facility_id}" if facility_id else "recreation.gov"
        message = f"Campsites at {facility_name}!{dates_part} Sites: {sites_str}. {url}"
        
        return self.send_sms(to_number, message)


class WebPushService:
    def __init__(self):
        self.vapid_private_key_raw = settings.VAPID_PRIVATE_KEY
        self.vapid_public_key = settings.VAPID_PUBLIC_KEY
        try:
            self.vapid_claims = json.loads(settings.VAPID_CLAIMS)
        except:
            self.vapid_claims = {"sub": "mailto:noreply@example.com"}
        self.enabled = bool(self.vapid_private_key_raw and self.vapid_public_key)
        
        # Convert base64 key to PEM file for pywebpush
        self.vapid_private_key_path = None
        if self.vapid_private_key_raw:
            try:
                # Add padding if needed
                key_b64 = self.vapid_private_key_raw
                padding = 4 - len(key_b64) % 4
                if padding != 4:
                    key_b64 += '=' * padding
                
                # Decode the base64 key to DER bytes
                key_bytes = base64.urlsafe_b64decode(key_b64)
                
                # Load the private key from DER format
                from cryptography.hazmat.primitives.serialization import load_der_private_key
                private_key_obj = load_der_private_key(key_bytes, password=None, backend=default_backend())
                
                # Convert to PEM format and write to temp file
                pem_data = private_key_obj.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                
                # Write to a file that persists for the lifetime of the application
                fd, self.vapid_private_key_path = tempfile.mkstemp(suffix='.pem', text=False)
                with os.fdopen(fd, 'wb') as f:
                    f.write(pem_data)
                
                print(f"VAPID private key loaded and saved to {self.vapid_private_key_path}")
                
            except Exception as e:
                print(f"Error loading VAPID private key: {e}")
                self.enabled = False
        
        if not self.enabled:
            print("Warning: Web Push notifications disabled - VAPID keys not configured")
    
    def send_push_notification(self, subscription_info: dict, title: str, body: str, 
                              url: str = None, icon: str = None):
        """Send a web push notification"""
        if not self.enabled:
            print("Web Push notifications are disabled")
            return False
        
        try:
            payload = {
                "title": title,
                "body": body,
                "icon": icon or "/logo192.png",
                "badge": "/logo192.png",
                "vibrate": [200, 100, 200],
                "data": {
                    "url": url or "https://www.recreation.gov"
                }
            }
            
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key_path,
                vapid_claims=self.vapid_claims
            )
            
            print(f"Web push notification sent successfully")
            return True
        except WebPushException as e:
            print(f"Error sending web push notification: {e}")
            if e.response and e.response.status_code == 410:
                # Subscription expired or invalid, should be removed
                print("Subscription expired - should be removed from database")
                return "expired"
            return False
        except Exception as e:
            print(f"Unexpected error sending web push notification: {e}")
            return False
    
    def send_availability_notification(self, subscription_info: dict, facility_name: str, 
                                      available_sites: List[str], dates: str, facility_id: str = None,
                                      available_dates: Optional[List[str]] = None):
        """Send availability notification via web push"""
        title = f"🏕️ Campsites Available!"
        
        sites_str = ", ".join(available_sites[:3])
        if len(available_sites) > 3:
            sites_str += f" and {len(available_sites) - 3} more"
        
        # Format available dates
        formatted_dates = format_available_dates(available_dates or [], max_dates=7) if available_dates else ""
        dates_info = f" Available: {formatted_dates}." if formatted_dates else ""
        
        body = f"{facility_name} has {len(available_sites)} site(s).{dates_info} Sites: {sites_str}"
        
        # Use direct campground URL if available
        campground_url = f"https://www.recreation.gov/camping/campgrounds/{facility_id}" if facility_id else "https://www.recreation.gov"
        
        return self.send_push_notification(
            subscription_info=subscription_info,
            title=title,
            body=body,
            url=campground_url
        )


email_service = EmailService()
sms_service = SMSService()
web_push_service = WebPushService()
