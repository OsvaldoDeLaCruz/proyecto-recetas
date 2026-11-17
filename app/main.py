"""Punto de entrada de la aplicación FastAPI."""
import random
import time
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import models  # noqa: F401  (registra las tablas)
from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, ingredients, recipes

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_tables(attempts: int = 5) -> None:
    """Crea las tablas si no existen (usuarios, ingredientes, recetas, calificaciones).

    Con varios workers de Uvicorn todos intentan crearlas a la vez; si uno pierde la
    carrera ("table already exists") se reintenta y la segunda vez ya no hay nada que crear.
    """
    for attempt in range(1, attempts + 1):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except SQLAlchemyError:
            if attempt == attempts:
                raise
            time.sleep(random.uniform(0.5, 1.5) * attempt)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Generador de recetas: registra los ingredientes que tienes en casa y obtén "
        "recetas estructuradas generadas por un LLM. Autenticación con JWT."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Política de contenido estricta para la interfaz: solo recursos propios, sin scripts inline.
APP_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)
# Swagger/ReDoc cargan sus archivos desde cdn.jsdelivr.net y usan un script inline.
DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https://fastapi.tiangolo.com "
    "https://cdn.redoc.ly; worker-src 'self' blob:; connect-src 'self'; object-src 'none'; "
    "frame-ancestors 'none'"
)
_DOCS_PATHS = ("/docs", "/redoc")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Cabeceras de seguridad en todas las respuestas (HSTS lo añade Caddy sobre HTTPS)."""
    response = await call_next(request)
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    path = request.url.path
    headers.setdefault(
        "Content-Security-Policy", DOCS_CSP if path.startswith(_DOCS_PATHS) else APP_CSP
    )
    if path.startswith("/api/"):
        headers.setdefault("Cache-Control", "no-store")  # no guardar datos privados en caché
    return response


app.include_router(auth.router)
app.include_router(ingredients.router)
app.include_router(recipes.router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / "favicon.ico")


@app.get("/health", tags=["Sistema"])
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"app_name": settings.app_name})
