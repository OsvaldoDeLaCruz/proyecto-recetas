import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Letras (incluye tildes y ñ), espacios y algunos signos comunes en nombres de alimentos.
_NAME_RE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 '\-.,()]*$")


def _normalize_name(v: str) -> str:
    v = " ".join(v.split()).lower()  # quita espacios repetidos y pasa a minúsculas
    if not v:
        raise ValueError("El nombre del ingrediente no puede estar vacío")
    if not _NAME_RE.match(v):
        raise ValueError(
            "El nombre debe empezar con una letra y solo contener letras, números, "
            "espacios o los signos ' - . , ( )"
        )
    return v


def _normalize_unit(v: str | None) -> str | None:
    if v is None:
        return None
    v = " ".join(v.split()).lower()
    return v or None


class IngredientBase(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["tomate"])
    quantity: float | None = Field(default=None, gt=0, le=100_000, examples=[3])
    unit: str | None = Field(default=None, max_length=30, examples=["unidades"])

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return _normalize_name(v)

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, v: str | None) -> str | None:
        return _normalize_unit(v)


class IngredientCreate(IngredientBase):
    pass


class IngredientUpdate(BaseModel):
    """Actualización parcial: solo se modifican los campos enviados."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    quantity: float | None = Field(default=None, gt=0, le=100_000)
    unit: str | None = Field(default=None, max_length=30)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str | None) -> str | None:
        return None if v is None else _normalize_name(v)

    @field_validator("unit")
    @classmethod
    def clean_unit(cls, v: str | None) -> str | None:
        return _normalize_unit(v)


class IngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: float | None
    unit: str | None
    created_at: datetime
