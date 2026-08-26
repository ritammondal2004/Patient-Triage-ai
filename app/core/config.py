"""Application settings, loaded from environment / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
     

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PatientTriage.ai"
    environment: str = "development"
    debug: bool = True

    # SQLite by default so the prototype runs with no local Postgres.
    database_url: str = "sqlite:///./patienttriage.db"
    sql_echo: bool = False

    # Single shared key is enough for a prototype; real deployment needs proper auth.
    api_key: str = "dev-local-key"
    require_api_key: bool = False

    # Engine defaults
    safety_mode: str = "conservative"

    # Default ED capacity — used to seed the demo hospital and the simulation.
    default_hospital_name: str = "Demo General Hospital"
    default_doctors: int = 4
    default_beds: int = 12
    default_daily_visits: int = 300

    # DPDP Act 2023 (India) is the assumed jurisdiction.
    jurisdiction: str = "India DPDP Act 2023"
    retention_days: int = 365
    consent_notice_version: str = "v1.0-prototype" 

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()