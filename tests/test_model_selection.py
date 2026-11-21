"""Selección automática del modelo LLM (OPENROUTER_MODEL=auto) con respaldo entre modelos."""
import json
from types import SimpleNamespace

import httpx
import pytest

from app.config import Settings
from app.services.llm_service import (
    FALLBACK_FREE_MODELS,
    LLMService,
    LLMUnavailableError,
    select_free_models,
)
from tests.conftest import SAMPLE_RECIPE

INVENTORY = [SimpleNamespace(name="arroz", quantity=2, unit="tazas")]

CATALOG = [
    # De pago: nunca se debe elegir
    {"id": "openai/gpt-x", "pricing": {"prompt": "0.000002", "completion": "0.000008"},
     "architecture": {"output_modalities": ["text"]}, "supported_parameters": ["response_format"]},
    # Gratis pero solo genera imágenes: se descarta
    {"id": "acme/imagen:free", "pricing": {"prompt": "0", "completion": "0"},
     "architecture": {"output_modalities": ["image"]}},
    # Gratis, texto, sin modo JSON
    {"id": "acme/texto-simple:free", "pricing": {"prompt": "0", "completion": "0"},
     "architecture": {"output_modalities": ["text"]}, "supported_parameters": ["temperature"]},
    # Gratis, texto, con modo JSON (deben ir primero)
    {"id": "acme/json-a:free", "pricing": {"prompt": "0", "completion": "0"},
     "architecture": {"output_modalities": ["text"]}, "supported_parameters": ["response_format"]},
    {"id": "acme/json-b:free", "pricing": {"prompt": "0", "completion": "0"},
     "architecture": {"output_modalities": ["text"]}, "supported_parameters": ["structured_outputs"]},
]


def completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


class FakeOpenRouter:
    """Simula OpenRouter: /models devuelve el catálogo y /chat/completions responde por modelo."""

    def __init__(self, responses: dict[str, httpx.Response], catalog=CATALOG, catalog_status=200):
        self.responses = responses
        self.catalog = catalog
        self.catalog_status = catalog_status
        self.models_called: list[str] = []
        self.json_mode: dict[str, bool] = {}
        self.catalog_requests = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            self.catalog_requests += 1
            return httpx.Response(self.catalog_status, json={"data": self.catalog})
        body = json.loads(request.content)
        model = body["model"]
        self.models_called.append(model)
        self.json_mode[model] = "response_format" in body
        return self.responses.get(model, httpx.Response(404, json={"error": "model not found"}))


def service(fake: FakeOpenRouter, model: str = "auto") -> LLMService:
    settings = Settings(openrouter_api_key="sk-or-test", openrouter_model=model, llm_max_retries=2)
    return LLMService(settings=settings, client=httpx.Client(transport=httpx.MockTransport(fake)))


def test_filtra_solo_modelos_gratuitos_de_texto_con_json_primero():
    models, json_models = select_free_models(CATALOG)
    assert models == ["acme/json-a:free", "acme/json-b:free", "acme/texto-simple:free"]
    assert json_models == {"acme/json-a:free", "acme/json-b:free"}


def test_auto_usa_el_primer_modelo_disponible_y_activa_modo_json():
    fake = FakeOpenRouter({"acme/json-a:free": completion(json.dumps(SAMPLE_RECIPE))})
    llm = service(fake)
    recipe = llm.generate_recipe(INVENTORY)
    assert recipe.nombre == "Arroz con pollo"
    assert fake.models_called == ["acme/json-a:free"]
    assert fake.json_mode["acme/json-a:free"] is True
    assert llm.model == "acme/json-a:free"  # se guarda en la receta como llm_model


def test_auto_salta_modelos_caidos_o_saturados():
    fake = FakeOpenRouter({
        "acme/json-a:free": httpx.Response(429, json={"error": "rate limited"}),
        "acme/json-b:free": httpx.Response(200, json={"error": {"message": "provider down"}}),
        "acme/texto-simple:free": completion(json.dumps(SAMPLE_RECIPE)),
    })
    llm = service(fake)
    llm.generate_recipe(INVENTORY)
    assert fake.models_called == ["acme/json-a:free", "acme/json-b:free", "acme/texto-simple:free"]
    assert llm.model == "acme/texto-simple:free"


def test_json_invalido_reintenta_y_luego_cambia_de_modelo():
    fake = FakeOpenRouter({
        "acme/json-a:free": completion("no es json"),
        "acme/json-b:free": completion(json.dumps(SAMPLE_RECIPE)),
    })
    service(fake).generate_recipe(INVENTORY)
    # 2 intentos con el primer modelo (LLM_MAX_RETRIES=2) y luego el segundo
    assert fake.models_called == ["acme/json-a:free", "acme/json-a:free", "acme/json-b:free"]


def test_recuerda_el_modelo_que_funciono_y_usa_cache_del_catalogo():
    fake = FakeOpenRouter({
        "acme/json-a:free": httpx.Response(404),
        "acme/json-b:free": completion(json.dumps(SAMPLE_RECIPE)),
    })
    service(fake).generate_recipe(INVENTORY)
    fake.models_called.clear()
    service(fake).generate_recipe(INVENTORY)  # nueva petición (nuevo servicio)
    assert fake.models_called == ["acme/json-b:free"]  # va directo al que funcionó
    assert fake.catalog_requests == 1  # el catálogo se consultó una sola vez


def test_si_el_catalogo_falla_usa_la_lista_de_respaldo():
    first = FALLBACK_FREE_MODELS[0]
    fake = FakeOpenRouter({first: completion(json.dumps(SAMPLE_RECIPE))}, catalog_status=503)
    llm = service(fake)
    llm.generate_recipe(INVENTORY)
    assert llm.model == first


def test_si_ningun_modelo_responde_lanza_error_controlado():
    fake = FakeOpenRouter({})  # todos devuelven 404
    with pytest.raises(LLMUnavailableError):
        service(fake).generate_recipe(INVENTORY)
    assert len(fake.models_called) == 3  # probó los 3 gratuitos y se rindió


def test_lista_fija_de_modelos_respeta_el_orden_y_no_consulta_catalogo():
    fake = FakeOpenRouter({"x/b:free": completion(json.dumps(SAMPLE_RECIPE))})
    llm = service(fake, model="x/a:free, x/b:free")
    llm.generate_recipe(INVENTORY)
    assert fake.models_called == ["x/a:free", "x/b:free"]
    assert fake.catalog_requests == 0
