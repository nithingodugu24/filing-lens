from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/filinglens.db"
    storage_dir: Path = Path("data/documents")
    embedding_provider: str = "local"
    embedding_model: str = "hash-v1"
    embedding_dimensions: int = Field(default=256, ge=32, le=2000)
    answer_provider: str = "extractive"
    answer_model: str = ""
    provider_api_key: str = ""
    provider_base_url: str = "https://api.openai.com/v1"
    provider_timeout: float = 30
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    max_upload_mb: int = 20
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
