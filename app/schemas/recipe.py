import unicodedata
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Difficulty = Literal["facil", "media", "dificil"]
MealType = Literal["desayuno", "almuerzo", "cena", "postre", "snack"]

_DIFFICULTY_ALIASES = {
    "facil": "facil",
    "easy": "facil",
    "baja": "facil",
    "sencilla": "facil",
    "media": "media",
    "medio": "media",
    "intermedia": "media",
    "intermedio": "media",
    "moderada": "media",
    "medium": "media",
    "dificil": "dificil",
    "alta": "dificil",
    "avanzada": "dificil",
    "hard": "dificil",
    "difficult": "dificil",
}


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


# ---------- Contrato JSON que debe devolver el LLM ----------


class LLMRecipeIngredient(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    cantidad: str = Field(min_length=1, max_length=60)

    @field_validator("cantidad", mode="before")
    @classmethod
    def coerce_cantidad(cls, v):
        # Algunos modelos devuelven números en lugar de texto ("2" vs 2).
        return str(v) if isinstance(v, (int, float)) else v


class LLMRecipe(BaseModel):
    """Receta estructurada tal como la debe devolver el LLM."""

    nombre: str = Field(min_length=1, max_length=200)
    ingredientes: list[LLMRecipeIngredient] = Field(min_length=1, max_length=40)
    pasos: list[str] = Field(min_length=1, max_length=30)
    tiempo_estimado_min: int = Field(ge=1, le=1440)
    dificultad: Difficulty

    @field_validator("tiempo_estimado_min", mode="before")
    @classmethod
    def coerce_tiempo(cls, v):
        # Acepta "30", "30 min", "30 minutos".
        if isinstance(v, str):
            digits = "".join(ch for ch in v if ch.isdigit())
            if digits:
                return int(digits)
        return v

    @field_validator("dificultad", mode="before")
    @classmethod
    def normalize_dificultad(cls, v):
        if isinstance(v, str):
            key = _strip_accents(v.strip().lower())
            return _DIFFICULTY_ALIASES.get(key, key)
        return v

    @field_validator("pasos")
    @classmethod
    def clean_pasos(cls, v: list[str]) -> list[str]:
        cleaned = [p.strip() for p in v if p and p.strip()]
        if not cleaned:
            raise ValueError("La receta debe tener al menos un paso")
        return cleaned


# ---------- API ----------


class RecipeGenerateRequest(BaseModel):
    """Parámetros acotados para generar la receta (no es un chat libre)."""

    meal_type: MealType | None = Field(default=None, description="Tipo de comida deseado")
    servings: int = Field(default=2, ge=1, le=12, description="Número de porciones")
    ingredient_ids: list[int] | None = Field(
        default=None,
        description="Subconjunto del inventario a usar. Si se omite se usa todo el inventario.",
    )


class RecipeIngredientOut(BaseModel):
    nombre: str
    cantidad: str


class RecipeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    ingredients: list[RecipeIngredientOut]
    steps: list[str]
    prep_time_minutes: int
    difficulty: Difficulty
    servings: int | None
    llm_model: str | None
    created_at: datetime
    rating: int | None = None


class RatingIn(BaseModel):
    score: int = Field(ge=1, le=5, description="Calificación de 1 a 5 estrellas")
    comment: str | None = Field(default=None, max_length=500)


class RatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipe_id: int
    score: int
    comment: str | None
    updated_at: datetime
