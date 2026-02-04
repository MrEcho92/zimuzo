import os
from typing import List

from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_prefix: str = "/api/v1"
    debug: bool = True
    backend_cors_origins: List[AnyUrl] = []
    project_name: str = "Zimuzo Backend"
    postgres_server: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "zimuzo_db"
    env: str = "dev"
    domain: str = "localhost"
    db_host: str = "db"
    database_url: str = ""
    redis_url: str = ""
    celery_broker_url: str = ""
    celery_result_backend: str = ""
    resend_api_key: str = ""
    resend_webhook_secret: str = ""
    anthropic_api_key: str = ""

    @property
    def get_database_url(self) -> str:
        return os.getenv(
            "DATABASE_URL",
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}@{self.postgres_server}:{self.postgres_port}/{self.postgres_db}",
        )

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
