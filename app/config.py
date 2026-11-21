"""Configuración de la aplicación leída desde variables de entorno (.env)."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET_HINT = (
    "JWT_SECRET_KEY debe tener al menos 32 caracteres aleatorios. Genera una con: "
    'python -c "import secrets; print(secrets.token_hex(32))"'
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Recetas IA"

    # Base de datos. En Docker apunta al servicio MySQL; en local puede usarse SQLite.
    database_url: str = "sqlite:///./recetas.db"

    # JWT (obligatoria: la app no arranca con una clave débil o de ejemplo)
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Límites anti-abuso
    rate_limit_login_per_minute: int = 10  # intentos de login por IP
    rate_limit_register_per_hour: int = 10  # registros por IP
    rate_limit_generate_per_minute: int = 5  # generaciones con IA por usuario
    max_ingredients_per_user: int = 100

    # LLM (OpenRouter, API compatible con OpenAI)
    openrouter_api_key: str = ""
    # "auto": elige solo el primer modelo gratuito disponible en OpenRouter (recomendado).
    # También acepta un modelo fijo o una lista en orden: "modelo-a:free,modelo-b:free".
    openrouter_model: str = "auto"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_timeout_seconds: float = 45.0  # por modelo
    llm_max_retries: int = 2  # reintentos con el mismo modelo si el JSON es inválido
    llm_max_models_per_request: int = 4  # cuántos modelos probar antes de rendirse

    @field_validator("jwt_secret_key")
    @classmethod
    def secret_must_be_strong(cls, v: str) -> str:
        if len(v) < 32 or v.lower().startswith("cambia"):
            raise ValueError(_INSECURE_SECRET_HINT)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
