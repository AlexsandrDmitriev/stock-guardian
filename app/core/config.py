from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://stock:stock@localhost:5432/stock"
    redis_url: str = "redis://localhost:6379/0"
    broker_url: str = "redis://localhost:6379/1"
    result_backend: str = "redis://localhost:6379/2"
    broker_api_url: str = "https://api.broker.example.com/v1/quotes"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()