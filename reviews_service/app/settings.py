from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    amqp_url: str = "amqp://guest:guest@localhost:5672/"
    users_url: str = "http://localhost:8001"
    service_token: str = "service-secret"
    jwt_secret: str = "game-servers-jwt-secret-key-32-bytes"
    http_timeout: float = 3.0

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
