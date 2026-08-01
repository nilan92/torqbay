from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 30


settings = Settings()
