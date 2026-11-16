"""Configuración de la aplicación leída desde variables de entorno (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Recetas IA"

    # Base de datos. En Docker apunta al servicio MySQL; en local puede usarse SQLite.
    database_url: str = "sqlite:///./recetas.db"

    # JWT
    jwt_secret_key: str = "cambia-esta-clave-en-el-env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # LLM (OpenRouter, API compatible con OpenAI)
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
