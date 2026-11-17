"""Pruebas de los endpoints de la API (con BD en memoria y LLM falso)."""
from tests.conftest import FakeLLMService, register_and_login


def test_health_y_favicon(client):
    assert client.get("/health").json() == {"status": "ok"}
    r = client.get("/favicon.ico")
    assert r.status_code == 200
    assert len(r.content) > 0


def test_registro_login_y_me(client):
    headers = register_and_login(client, "carlos")
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "carlos"
    assert "hashed_password" not in r.json()


def test_registro_duplicado_y_login_invalido(client):
    register_and_login(client, "ana")
    r = client.post(
        "/api/auth/register",
        json={"username": "ana", "email": "otra@example.com", "password": "secreta123"},
    )
    assert r.status_code == 409
    r = client.post("/api/auth/login", data={"username": "ana", "password": "incorrecta"})
    assert r.status_code == 401


def test_endpoints_protegidos_requieren_token(client):
    assert client.get("/api/ingredients").status_code == 401
    assert client.get("/api/recipes", headers={"Authorization": "Bearer token-falso"}).status_code == 401


def test_crud_ingredientes(client, auth_headers):
    r = client.post("/api/ingredients", json={"name": "Tomate", "quantity": 3, "unit": "unidades"}, headers=auth_headers)
    assert r.status_code == 201
    ing = r.json()
    assert ing["name"] == "tomate"

    # Duplicado
    r = client.post("/api/ingredients", json={"name": "tomate"}, headers=auth_headers)
    assert r.status_code == 409

    # Validación
    r = client.post("/api/ingredients", json={"name": "!!!"}, headers=auth_headers)
    assert r.status_code == 422

    r = client.patch(f"/api/ingredients/{ing['id']}", json={"quantity": 5}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["quantity"] == 5
    assert r.json()["name"] == "tomate"

    assert len(client.get("/api/ingredients", headers=auth_headers).json()) == 1
    assert client.delete(f"/api/ingredients/{ing['id']}", headers=auth_headers).status_code == 204
    assert client.get("/api/ingredients", headers=auth_headers).json() == []


def test_generar_receta_se_guarda_en_historial(client, auth_headers, fake_llm):
    client.post("/api/ingredients", json={"name": "arroz", "quantity": 2, "unit": "tazas"}, headers=auth_headers)
    client.post("/api/ingredients", json={"name": "pollo"}, headers=auth_headers)

    r = client.post("/api/recipes/generate", json={"meal_type": "almuerzo", "servings": 4}, headers=auth_headers)
    assert r.status_code == 201, r.text
    recipe = r.json()
    assert recipe["title"] == "Arroz con pollo"
    assert recipe["difficulty"] == "media"
    assert recipe["prep_time_minutes"] == 45
    assert recipe["servings"] == 4
    assert recipe["rating"] is None
    assert recipe["llm_model"] == "fake/test-model"
    # La fecha viaja con zona horaria UTC para que el navegador la muestre en hora local.
    assert recipe["created_at"].endswith(("Z", "+00:00"))

    # El servicio recibió el inventario del usuario
    assert fake_llm.calls == [{"ingredients": ["arroz", "pollo"], "meal_type": "almuerzo", "servings": 4}]

    history = client.get("/api/recipes", headers=auth_headers).json()
    assert [h["id"] for h in history] == [recipe["id"]]


def test_generar_con_inventario_vacio(client, auth_headers):
    r = client.post("/api/recipes/generate", json={}, headers=auth_headers)
    assert r.status_code == 400


def test_generar_con_respuesta_invalida_del_llm(client, auth_headers):
    from app.main import app
    from app.services.llm_service import get_llm_service

    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService(fail=True)
    client.post("/api/ingredients", json={"name": "arroz"}, headers=auth_headers)
    r = client.post("/api/recipes/generate", json={}, headers=auth_headers)
    assert r.status_code == 502
    assert client.get("/api/recipes", headers=auth_headers).json() == []


def test_calificar_y_eliminar_receta(client, auth_headers):
    client.post("/api/ingredients", json={"name": "arroz"}, headers=auth_headers)
    recipe_id = client.post("/api/recipes/generate", headers=auth_headers).json()["id"]

    assert client.put(f"/api/recipes/{recipe_id}/rating", json={"score": 6}, headers=auth_headers).status_code == 422
    assert client.put(f"/api/recipes/{recipe_id}/rating", json={"score": 0}, headers=auth_headers).status_code == 422

    r = client.put(f"/api/recipes/{recipe_id}/rating", json={"score": 4}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["score"] == 4
    # Recalificar actualiza en lugar de duplicar
    client.put(f"/api/recipes/{recipe_id}/rating", json={"score": 5}, headers=auth_headers)
    assert client.get(f"/api/recipes/{recipe_id}", headers=auth_headers).json()["rating"] == 5
    assert len(client.get("/api/recipes?min_rating=5", headers=auth_headers).json()) == 1

    assert client.delete(f"/api/recipes/{recipe_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/recipes/{recipe_id}", headers=auth_headers).status_code == 404


def test_usuarios_no_ven_datos_de_otros(client, auth_headers):
    ing = client.post("/api/ingredients", json={"name": "arroz"}, headers=auth_headers).json()
    recipe_id = client.post("/api/recipes/generate", headers=auth_headers).json()["id"]

    otro = register_and_login(client, "intruso")
    assert client.get("/api/ingredients", headers=otro).json() == []
    assert client.delete(f"/api/ingredients/{ing['id']}", headers=otro).status_code == 404
    assert client.get(f"/api/recipes/{recipe_id}", headers=otro).status_code == 404
    assert client.put(f"/api/recipes/{recipe_id}/rating", json={"score": 1}, headers=otro).status_code == 404
