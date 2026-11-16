"""Generación del prompt que se envía al LLM."""
from types import SimpleNamespace

import pytest

from app.services.llm_service import SYSTEM_PROMPT, build_prompt


def item(name, quantity=None, unit=None):
    return SimpleNamespace(name=name, quantity=quantity, unit=unit)


def test_prompt_incluye_inventario_con_cantidades():
    messages = build_prompt([item("tomate", 3, "unidades"), item("arroz", 0.5, "kg"), item("sal")])
    assert [m["role"] for m in messages] == ["system", "user"]
    user = messages[1]["content"]
    assert "- tomate: 3 unidades" in user
    assert "- arroz: 0.5 kg" in user
    assert "- sal (cantidad no especificada)" in user


def test_prompt_incluye_porciones_y_tipo_de_comida():
    user = build_prompt([item("huevo", 4)], meal_type="desayuno", servings=3)[1]["content"]
    assert "Porciones: 3" in user
    assert "Tipo de comida: desayuno" in user


def test_prompt_sin_tipo_de_comida_no_lo_menciona():
    user = build_prompt([item("huevo")])[1]["content"]
    assert "Tipo de comida" not in user


def test_system_prompt_exige_json_con_campos_obligatorios():
    for campo in ("nombre", "ingredientes", "pasos", "tiempo_estimado_min", "dificultad"):
        assert f'"{campo}"' in SYSTEM_PROMPT
    assert "JSON" in SYSTEM_PROMPT


def test_prompt_con_inventario_vacio_falla():
    with pytest.raises(ValueError):
        build_prompt([])
