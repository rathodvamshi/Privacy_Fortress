"""
Configuration management for Privacy Fortress
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # App
    APP_ENV: str = "development"
    APP_SECRET: str = "privacy-fortress-secret"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    # MongoDB
    MONGODB_URI: str = ""
    MONGODB_DB_NAME: str = "privacy_fortress"
    
    # Redis
    REDIS_URL: str = ""
    
    # Groq API
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    
    # Encryption
    ENCRYPTION_KEY: str = "privacy-fortress-secret-key-32b"
    
    # TTL (30 minutes default)
    VAULT_TTL_SECONDS: int = 1800
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 30
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"


settings = Settings()
