"""Limitador de peticiones en memoria (ventana deslizante).

Protege el login contra fuerza bruta y la generación con IA contra abuso de costos.
Cada worker de Uvicorn mantiene su propio contador; para varios servidores se
usaría Redis, pero para este despliegue (un VPS) es suficiente.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import get_settings

_MAX_KEYS = 10_000


class RateLimiter:
    def __init__(self, max_calls: int, period_seconds: float):
        self.max_calls = max_calls
        self.period = period_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        stale = [k for k, q in self._hits.items() if not q or now - q[-1] >= self.period]
        for key in stale:
            del self._hits[key]

    def hit(self, key: str) -> None:
        """Registra una petición; lanza HTTP 429 si se superó el límite."""
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > _MAX_KEYS:
                self._prune(now)
            q = self._hits[key]
            while q and now - q[0] >= self.period:
                q.popleft()
            if len(q) >= self.max_calls:
                retry_after = int(self.period - (now - q[0])) + 1
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Demasiadas solicitudes. Espera un momento e intenta de nuevo.",
                    headers={"Retry-After": str(retry_after)},
                )
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_ip(request: Request) -> str:
    # Detrás de Caddy, Uvicorn (--proxy-headers) ya coloca aquí la IP real del cliente.
    return request.client.host if request.client else "desconocido"


_settings = get_settings()
login_limiter = RateLimiter(_settings.rate_limit_login_per_minute, 60)
register_limiter = RateLimiter(_settings.rate_limit_register_per_hour, 3600)
generate_limiter = RateLimiter(_settings.rate_limit_generate_per_minute, 60)

ALL_LIMITERS = (login_limiter, register_limiter, generate_limiter)
