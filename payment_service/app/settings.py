from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    amqp_url: str = "amqp://guest:guest@localhost:5672/"
    postgres_url: str = "postgresql+psycopg2://payment:payment@localhost:5432/payment_db"
    service_token: str = "service-secret"
    jwt_secret: str = "game-servers-jwt-secret-key-32-bytes"
    gateway_delay_seconds: float = 2.0  # имитация обращения к платёжному шлюзу
    gateway_limit: int = 100000         # сумма, выше которой шлюз отклоняет платёж

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
