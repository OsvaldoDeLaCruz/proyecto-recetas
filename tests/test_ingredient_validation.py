"""Validación de ingredientes (esquemas Pydantic)."""
import pytest
from pydantic import ValidationError

from app.schemas.ingredient import IngredientCreate, IngredientUpdate


def test_ingrediente_valido_se_normaliza():
    ing = IngredientCreate(name="  Tomate   Chonto ", quantity=3, unit=" Unidades ")
    assert ing.name == "tomate chonto"
    assert ing.unit == "unidades"
    assert ing.quantity == 3


def test_ingrediente_acepta_tildes_y_enie():
    assert IngredientCreate(name="Ñame").name == "ñame"
    assert IngredientCreate(name="Limón").name == "limón"


@pytest.mark.parametrize("name", ["", "   ", "123", "<script>", "tomate; DROP TABLE"])
def test_ingrediente_nombre_invalido(name):
    with pytest.raises(ValidationError):
        IngredientCreate(name=name)


@pytest.mark.parametrize("quantity", [0, -1, 1_000_000])
def test_ingrediente_cantidad_fuera_de_rango(quantity):
    with pytest.raises(ValidationError):
        IngredientCreate(name="arroz", quantity=quantity)


def test_ingrediente_nombre_demasiado_largo():
    with pytest.raises(ValidationError):
        IngredientCreate(name="a" * 101)


def test_actualizacion_parcial_valida_nombre():
    assert IngredientUpdate(quantity=2).model_dump(exclude_unset=True) == {"quantity": 2}
    with pytest.raises(ValidationError):
        IngredientUpdate(name="!!!")
