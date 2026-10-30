from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    amqp_url: str = "amqp://guest:guest@localhost:5672/"
    postgres_url: str = "postgresql+psycopg2://booking:booking@localhost:5432/booking_db"
    payment_url: str = "http://localhost:8004"
    catalog_url: str = "http://localhost:8002"
    service_token: str = "service-secret"
    jwt_secret: str = "game-servers-jwt-secret-key-32-bytes"
    http_timeout: float = 3.0
    min_hours: int = 1
    finish_check_seconds: int = 15

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
