"""Aplicación local. Migrar explícitamente antes de iniciar; nunca crea tablas al importar."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.catalog import router as catalog_router
from app.api.identity import router
from app.api.reporting import router as reporting_router
from app.api.sales import router as sales_router
from app.application.catalog import CatalogService
from app.application.identity import IdentityService
from app.application.reporting import ReportingService
from app.application.sales import SalesService
from app.domain.identity import IdentityError
from app.infrastructure.catalog import CatalogStore
from app.infrastructure.database import build_engine
from app.infrastructure.identity import IdentityStore
from app.infrastructure.passwords import ArgonPasswords
from app.infrastructure.reporting import ReportingStore
from app.infrastructure.sales import SalesStore
from app.infrastructure.schema import verify_schema

ORIGINS = frozenset(
    f"http://{host}:{port}" for host in ("127.0.0.1", "localhost") for port in (8765, 5173)
)


def create_app(
    db_path: Path | None = None,
    *,
    allowed_origins: frozenset[str] = ORIGINS,
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost"),
    secure_cookies: bool = False,
) -> FastAPI:
    # Explicit parameters for the separate cloud demo; local defaults remain loopback-only.
    if not allowed_origins or not allowed_hosts or any("*" in item for item in (*allowed_origins, *allowed_hosts)):
        raise ValueError("Se requieren orígenes y hosts explícitos")
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(db_path)
        try:
            verify_schema(engine)
            passwords = ArgonPasswords()
            application.state.identity = IdentityService(
                IdentityStore(engine), passwords, passwords.dummy
            )
            application.state.catalog = CatalogService(
                CatalogStore(engine), lambda: application.state.identity.clock()
            )
            application.state.sales = SalesService(
                SalesStore(engine), lambda: application.state.identity.clock()
            )
            application.state.reporting = ReportingService(
                ReportingStore(engine), lambda: application.state.identity.clock()
            )
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="Gestión Inteligente POS", version="0.5.1", lifespan=lifespan)
    application.state.secure_cookies = secure_cookies

    @application.middleware("http")
    async def local_security(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        origin = request.headers.get("origin")
        if (origin is not None and origin not in allowed_origins) or (
            request.method not in {"GET", "HEAD"} and origin not in allowed_origins
        ):
            return JSONResponse({"detail": "Origen no permitido"}, status_code=403)
        if (
            request.method in {"POST", "PATCH", "PUT", "DELETE"}
            and request.headers.get("content-type", "").split(";")[0].strip() != "application/json"
        ):
            return JSONResponse({"detail": "Se requiere application/json"}, status_code=415)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
        return response

    application.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))

    @application.exception_handler(IdentityError)
    async def identity_error(request: Request, exc: IdentityError) -> JSONResponse:
        return JSONResponse(
            {"detail": str(exc)}, status_code=exc.status, headers={"Cache-Control": "no-store"}
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic incluye input en sus errores por defecto: no reflejar contraseñas/tokens.
        return JSONResponse(
            {
                "detail": "Datos inválidos",
                "fields": [{"loc": error["loc"], "type": error["type"]} for error in exc.errors()],
            },
            status_code=422,
            headers={"Cache-Control": "no-store"},
        )

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(router, prefix="/api")
    application.include_router(catalog_router, prefix="/api")
    application.include_router(sales_router, prefix="/api")
    application.include_router(reporting_router, prefix="/api")
    return application


app = create_app()
