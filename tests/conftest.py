"""Fixtures compartidas: BD SQLite en memoria y un LLM falso (sin llamadas de red)."""
import os

# Configuración de pruebas ANTES de importar la app.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "clave-solo-para-pruebas-0123456789abcdef"
os.environ["OPENROUTER_API_KEY"] = ""

import json  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.llm_service import (  # noqa: E402
    LLMResponseError,
    get_llm_service,
    parse_recipe_response,
)

SAMPLE_RECIPE = {
    "nombre": "Arroz con pollo",
    "ingredientes": [
        {"nombre": "arroz", "cantidad": "2 tazas"},
        {"nombre": "pollo", "cantidad": "500 g"},
        {"nombre": "tomate", "cantidad": "2 unidades"},
    ],
    "pasos": ["Dorar el pollo", "Agregar el tomate", "Cocinar el arroz con el pollo"],
    "tiempo_estimado_min": 45,
    "dificultad": "media",
}


class FakeLLMService:
    """Sustituye al LLM real: devuelve una receta fija y registra con qué se llamó."""

    model = "fake/test-model"

    def __init__(self, content: str | None = None, fail: bool = False):
        self.content = content or json.dumps(SAMPLE_RECIPE)
        self.fail = fail
        self.calls = []

    def generate_recipe(self, ingredients, meal_type=None, servings=2):
        self.calls.append(
            {"ingredients": [i.name for i in ingredients], "meal_type": meal_type, "servings": servings}
        )
        if self.fail:
            raise LLMResponseError("respuesta inválida")
        return parse_recipe_response(self.content)


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Cada prueba empieza con los contadores de límite de peticiones en cero."""
    from app.core.rate_limit import ALL_LIMITERS

    from app.services.llm_service import reset_model_cache

    for limiter in ALL_LIMITERS:
        limiter.reset()
    reset_model_cache()  # cada prueba empieza sin catálogo ni modelo preferido
    yield


@pytest.fixture()
def fake_llm():
    return FakeLLMService()


@pytest.fixture()
def client(fake_llm):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_service] = lambda: fake_llm
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def register_and_login(client, username="ana", password="secreta123"):
    r = client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def auth_headers(client):
    return register_and_login(client)
