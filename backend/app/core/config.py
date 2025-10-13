import os
from typing import List

from dotenv import load_dotenv
from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    api_prefix: str = "/api/v1"
    debug: bool = True
    backend_cors_origins: List[AnyUrl] = []
    project_name: str = "Zimuzo Backend"
    postgres_server: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "user"
    postgres_password: str = "password"
    postgres_db: str = "database"

    @property
    def get_database_url(self) -> str:
        return os.getenv(
            "DATABASE_URL",
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}@{self.postgres_server}:{self.postgres_port}/{self.postgres_db}",
        )

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
