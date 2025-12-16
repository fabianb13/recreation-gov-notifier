import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
from pywebpush import webpush, WebPushException
from config import settings
from typing import List
import json


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
                                      available_sites: List[str], dates: str):
        """Send availability notification email"""
        subject = f"Campsite Available: {facility_name}"
        
        sites_list = "\n".join([f"<li>{site}</li>" for site in available_sites])
        
        body = f"""
        <html>
        <body>
            <h2>Good news! Campsites are now available!</h2>
            <p><strong>Campground:</strong> {facility_name}</p>
            <p><strong>Dates:</strong> {dates}</p>
            <p><strong>Available Sites:</strong></p>
            <ul>
                {sites_list}
            </ul>
            <p>Visit <a href="https://www.recreation.gov">Recreation.gov</a> to make your reservation.</p>
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
                                      available_sites: List[str], dates: str):
        """Send availability notification SMS"""
        sites_str = ", ".join(available_sites[:3])  # Limit to 3 sites for SMS
        if len(available_sites) > 3:
            sites_str += f" and {len(available_sites) - 3} more"
        
        message = f"Campsites available at {facility_name} for {dates}! Sites: {sites_str}. Book at recreation.gov"
        
        return self.send_sms(to_number, message)


class WebPushService:
    def __init__(self):
        self.vapid_private_key = settings.VAPID_PRIVATE_KEY
        self.vapid_public_key = settings.VAPID_PUBLIC_KEY
        try:
            self.vapid_claims = json.loads(settings.VAPID_CLAIMS)
        except:
            self.vapid_claims = {"sub": "mailto:noreply@example.com"}
        self.enabled = bool(self.vapid_private_key and self.vapid_public_key)
        
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
                vapid_private_key=self.vapid_private_key,
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
                                      available_sites: List[str], dates: str):
        """Send availability notification via web push"""
        title = f"🏕️ Campsites Available!"
        
        sites_str = ", ".join(available_sites[:3])
        if len(available_sites) > 3:
            sites_str += f" and {len(available_sites) - 3} more"
        
        body = f"{facility_name} has {len(available_sites)} site(s) available for {dates}. Sites: {sites_str}"
        
        return self.send_push_notification(
            subscription_info=subscription_info,
            title=title,
            body=body,
            url="https://www.recreation.gov"
        )


email_service = EmailService()
sms_service = SMSService()
web_push_service = WebPushService()
