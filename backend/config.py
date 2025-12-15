from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Twilio Configuration
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_PHONE_NUMBER: str

    # Email Configuration
    SMTP_SERVER: str
    SMTP_PORT: int
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    EMAIL_FROM: str

    # Recreation.gov API Configuration
    RECREATION_GOV_API_KEY: str

    # MongoDB Configuration
    MONGODB_URI: str
    MONGODB_DB_NAME: str

    # Application Settings
    DEFAULT_SCRAPE_INTERVAL: int = 300
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
