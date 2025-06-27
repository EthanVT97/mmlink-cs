from pydantic import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Viber Configuration
    viber_token: str = os.getenv("VIBER_TOKEN", "")
    viber_webhook_url: str = os.getenv("VIBER_WEBHOOK_URL", "")
    
    # Supabase Configuration
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")
    
    # Admin Configuration
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "secure_password")
    jwt_secret: str = os.getenv("JWT_SECRET", "your_jwt_secret")
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 24 * 60 * 60  # 24 hours in seconds
    
    # Application Configuration
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    port: int = int(os.getenv("PORT", "8000"))
    
    # Bot Configuration
    default_language: str = "my"  # Myanmar as default
    escalation_timeout: int = 300  # 5 minutes
    
    class Config:
        env_file = ".env"
        case_sensitive = False
