"""Application settings, loaded from environment / .env."""

from functools import lru_cache
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file BEFORE creating Settings
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PatientTriage.ai"
    environment: str = "production"
    debug: bool = False

    # DATABASE_URL is loaded from .env file - NEVER hardcode credentials here
    
    database_url: str
    sql_echo: bool = False 

    # Single shared key is enough for a prototype; real deployment needs proper auth.
    api_key: str = "dev-local-key"
    require_api_key: bool = False

    # Engine defaults
    safety_mode: str = "conservative"


    default_hospital_name: str = "Demo General Hospital"
    default_doctors: int = 4
    default_beds: int = 12
    default_daily_visits: int = 300

  
    jurisdiction: str = "India DPDP Act 2023"
    retention_days: int = 365
    consent_notice_version: str = "v1.0-prototype" 

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()