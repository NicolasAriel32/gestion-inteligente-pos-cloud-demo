"""Explicit opt-in entrypoint for a disposable remote demo, never used by python -m app."""

import os
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from alembic import command
from app.application.identity import digest
from app.infrastructure.database import build_engine, get_db_path
from app.infrastructure.identity import IdentityStore
from app.infrastructure.schema import verify_schema
from app.main import create_app


def configuration() -> tuple[str, str, str]:
    if os.environ.get("POS_CLOUD_DEMO") != "1":
        raise ValueError("La demo remota requiere POS_CLOUD_DEMO=1")
    origin = os.environ.get("POS_PUBLIC_ORIGIN", "").rstrip("/")
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
        or parsed.path or parsed.query or parsed.fragment or parsed.port not in (None, 443)
        or "*" in origin or parsed.netloc != parsed.hostname
    ):
        raise ValueError("POS_PUBLIC_ORIGIN debe ser un origen HTTPS exacto sin ruta")
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")
    if not host.endswith(".onrender.com") or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for c in host):
        raise ValueError("RENDER_EXTERNAL_HOSTNAME debe identificar el servicio Render")
    secret = os.environ.get("POS_DEMO_SETUP_TOKEN", "")
    if not 32 <= len(secret) <= 128:
        raise ValueError("Configurar POS_DEMO_SETUP_TOKEN de 32 a 128 caracteres, sin publicarlo")
    if not os.environ.get("LOCALAPPDATA"):
        raise ValueError("LOCALAPPDATA debe apuntar a la carpeta aislada de esta demo")
    return origin, host, secret


def prepare_database(secret: str) -> Path:
    path = get_db_path()
    # Only a new isolated demo database can be provisioned automatically.
    # Existing/old/incomplete databases are verified and rejected, never repaired.
    if not path.exists():
        backend = Path(__file__).resolve().parents[1]
        config = Config(str(backend / "alembic.ini"))
        config.set_main_option("script_location", str(backend / "alembic"))
        command.upgrade(config, "head")
    engine = build_engine(path)
    try:
        verify_schema(engine)
        with IdentityStore(engine).transaction(write=True) as tx:
            if not tx.initialized():
                tx.prepare_setup(digest(secret), int(time.time()) + 1800)
    finally:
        engine.dispose()
    return path


def create_demo_app() -> FastAPI:
    origin, host, secret = configuration()
    path = prepare_database(secret)
    app = create_app(
        path, allowed_origins=frozenset({origin}),
        allowed_hosts=(host,), secure_cookies=True,
    )
    # Bound the cost of public Argon2/setup requests. Global per-process limit is
    # intentionally conservative for a single-user demo and ignores spoofable IP headers.
    auth_attempts: deque[float] = deque()

    @app.middleware("http")
    async def demo_limits(request: Request, call_next):
        if request.method == "POST" and request.url.path in {"/api/auth/login", "/api/auth/setup"}:
            now = time.monotonic()
            while auth_attempts and auth_attempts[0] <= now - 60:
                auth_attempts.popleft()
            if len(auth_attempts) >= 20:
                return JSONResponse(
                    {"detail": "Demasiados intentos. Esperá un minuto y volvé a intentar."},
                    status_code=429, headers={"Retry-After": "60", "Cache-Control": "no-store"},
                )
            auth_attempts.append(now)
        return await call_next(request)

    return app


def main() -> None:
    import uvicorn

    # The separate entrypoint requires explicit remote-demo configuration before listening.
    configuration()
    uvicorn.run(
        "app.cloud_demo:create_demo_app", factory=True, host="0.0.0.0",
        port=int(os.environ.get("PORT", "10000")), workers=1, proxy_headers=False,
    )


if __name__ == "__main__":
    main()
