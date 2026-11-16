"""Parseo de la respuesta del LLM y servicio LLM con transporte HTTP simulado."""
import json
from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings
from app.services.llm_service import (
    LLMResponseError,
    LLMService,
    LLMUnavailableError,
    parse_recipe_response,
)
from tests.conftest import SAMPLE_RECIPE


def test_parseo_json_valido():
    recipe = parse_recipe_response(json.dumps(SAMPLE_RECIPE))
    assert recipe.nombre == "Arroz con pollo"
    assert recipe.ingredientes[1].nombre == "pollo"
    assert recipe.ingredientes[1].cantidad == "500 g"
    assert len(recipe.pasos) == 3
    assert recipe.tiempo_estimado_min == 45
    assert recipe.dificultad == "media"


def test_parseo_tolera_markdown_y_texto_extra():
    content = "Aquí tienes tu receta:\n```json\n" + json.dumps(SAMPLE_RECIPE) + "\n```\n¡Buen provecho!"
    assert parse_recipe_response(content).nombre == "Arroz con pollo"


def test_parseo_normaliza_dificultad_tiempo_y_cantidades():
    data = dict(SAMPLE_RECIPE, dificultad="Fácil", tiempo_estimado_min="30 minutos")
    data["ingredientes"] = [{"nombre": "huevo", "cantidad": 2}]
    recipe = parse_recipe_response(json.dumps(data))
    assert recipe.dificultad == "facil"
    assert recipe.tiempo_estimado_min == 30
    assert recipe.ingredientes[0].cantidad == "2"


def test_parseo_desenvuelve_objeto_receta():
    recipe = parse_recipe_response(json.dumps({"receta": SAMPLE_RECIPE}))
    assert recipe.nombre == "Arroz con pollo"


@pytest.mark.parametrize(
    "content",
    [
        "",
        "Lo siento, no puedo ayudar con eso.",
        "{nombre: 'sin comillas'}",
        json.dumps({k: v for k, v in SAMPLE_RECIPE.items() if k != "pasos"}),
        json.dumps(dict(SAMPLE_RECIPE, dificultad="imposible")),
        json.dumps(dict(SAMPLE_RECIPE, ingredientes=[])),
    ],
)
def test_parseo_respuestas_invalidas(content):
    with pytest.raises(LLMResponseError):
        parse_recipe_response(content)


def _service(handler, **overrides):
    settings = Settings(
        openrouter_api_key="sk-test", openrouter_model="test/model", llm_max_retries=2, **overrides
    )
    return LLMService(settings=settings, client=httpx.Client(transport=httpx.MockTransport(handler)))


def _completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


INVENTORY = [SimpleNamespace(name="arroz", quantity=2, unit="tazas")]


def test_servicio_envia_prompt_y_devuelve_receta():
    captured = {}

    def handler(request: httpx.Request):
        captured["auth"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return _completion(json.dumps(SAMPLE_RECIPE))

    recipe = _service(handler).generate_recipe(INVENTORY, servings=4)
    assert recipe.nombre == "Arroz con pollo"
    assert captured["auth"] == "Bearer sk-test"
    assert captured["body"]["model"] == "test/model"
    assert "- arroz: 2 tazas" in captured["body"]["messages"][1]["content"]


def test_servicio_reintenta_si_el_json_es_invalido():
    responses = iter([_completion("no es json"), _completion(json.dumps(SAMPLE_RECIPE))])
    recipe = _service(lambda request: next(responses)).generate_recipe(INVENTORY)
    assert recipe.dificultad == "media"


def test_servicio_error_http_del_proveedor():
    with pytest.raises(LLMUnavailableError):
        _service(lambda request: httpx.Response(500, text="boom")).generate_recipe(INVENTORY)


def test_servicio_sin_api_key():
    service = LLMService(settings=Settings(openrouter_api_key=""))
    with pytest.raises(LLMUnavailableError):
        service.generate_recipe(INVENTORY)
