from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    amqp_url: str = "amqp://guest:guest@localhost:5672/"
    postgres_url: str = "postgresql+psycopg2://notification:notification@localhost:5432/notification_db"
    service_token: str = "service-secret"
    jwt_secret: str = "game-servers-jwt-secret-key-32-bytes"
    http_timeout: float = 3.0

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
