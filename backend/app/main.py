"""Aplicación local. Migrar explícitamente antes de iniciar; nunca crea tablas al importar."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.catalog import router as catalog_router
from app.api.identity import router
from app.api.operations import router as operations_router
from app.api.reporting import router as reporting_router
from app.api.sales import router as sales_router
from app.application.catalog import CatalogService
from app.application.identity import IdentityService
from app.application.importing import ImportService
from app.application.maintenance import MaintenanceService
from app.application.reporting import ReportingService
from app.application.sales import SalesService
from app.domain.identity import IdentityError
from app.infrastructure.backups import BackupFiles
from app.infrastructure.catalog import CatalogStore
from app.infrastructure.database import build_engine, get_db_path
from app.infrastructure.http_limits import BodyLimit
from app.infrastructure.identity import IdentityStore
from app.infrastructure.importing import ImportStore
from app.infrastructure.maintenance import MaintenanceStore
from app.infrastructure.maintenance_gate import MaintenanceGate
from app.infrastructure.passwords import ArgonPasswords
from app.infrastructure.reporting import ReportingStore
from app.infrastructure.sales import SalesStore
from app.infrastructure.schema import verify_schema

ORIGINS = frozenset(
    f"http://{host}:{port}" for host in ("127.0.0.1", "localhost") for port in (8765, 5173)
)


def create_app(db_path: Path | None = None, frontend_path: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        path = db_path or get_db_path()
        files = BackupFiles(path)
        if files.journal.exists():
            raise RuntimeError("Restauración interrumpida: ejecutar recuperación explícita con ADMIN antes de iniciar")
        engine = build_engine(path)
        application.state.gate = MaintenanceGate()
        application.state.files = files
        try:
            verify_schema(engine)
            passwords = ArgonPasswords()
            application.state.identity = IdentityService(
                IdentityStore(engine), passwords, passwords.dummy
            )
            application.state.catalog = CatalogService(
                CatalogStore(engine), lambda: application.state.identity.clock()
            )
            application.state.maintenance = MaintenanceService(MaintenanceStore(engine, files, lambda: application.state.identity.clock()))
            application.state.imports = ImportService(ImportStore(engine), lambda: application.state.identity.clock(), application.state.maintenance.store.generation)
            application.state.sales = SalesService(
                SalesStore(engine), lambda: application.state.identity.clock(), application.state.maintenance.store.generation
            )
            application.state.reporting = ReportingService(
                ReportingStore(engine), lambda: application.state.identity.clock()
            )
            async def scheduled_backups():
                while True:
                    await asyncio.sleep(30)
                    try:
                        async with application.state.gate.access():
                            if not files.journal.exists():
                                worker = asyncio.create_task(asyncio.to_thread(application.state.maintenance.store.automatic))
                                try:
                                    await asyncio.shield(worker)
                                except asyncio.CancelledError:
                                    await worker
                                    raise
                    except IdentityError:
                        pass
            scheduler = asyncio.create_task(scheduled_backups())
            try:
                yield
            finally:
                scheduler.cancel()
                with suppress(asyncio.CancelledError):
                    await scheduler
        finally:
            engine.dispose()

    application = FastAPI(title="Gestión Inteligente POS", version="0.5.1", lifespan=lifespan)

    application.state.request_shutdown = None
    application.state.instance_id = None

    @application.middleware("http")
    async def local_security(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        origin = request.headers.get("origin")
        if (origin is not None and origin not in ORIGINS) or (
            request.method not in {"GET", "HEAD"} and origin not in ORIGINS
        ):
            return JSONResponse({"detail": "Origen no permitido"}, status_code=403)
        if (
            request.method in {"POST", "PATCH", "PUT", "DELETE"}
            and request.headers.get("content-type", "").split(";")[0].strip() != "application/json"
        ):
            return JSONResponse({"detail": "Se requiere application/json"}, status_code=415)
        try:
            if request.url.path.startswith('/api/'):
                if request.app.state.files.journal.exists():
                    return JSONResponse({'detail': 'Restauración interrumpida; recuperación ADMIN requerida'}, status_code=503)
                async with request.app.state.gate.access(exclusive=request.url.path == '/api/backups/restore' and request.method == 'POST'):
                    response = await call_next(request)
            else:
                response = await call_next(request)
        except IdentityError as exc:
            return JSONResponse({'detail': str(exc)}, status_code=exc.status)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
        return response

    application.add_middleware(BodyLimit)
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

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

    @application.get('/api/runtime/ping')
    def runtime_ping() -> dict[str, str | None]:
        return {'instance': application.state.instance_id}

    if frontend_path is not None:
        application.mount('/assets', StaticFiles(directory=frontend_path / 'assets'), name='assets')
        application.mount('/licenses', StaticFiles(directory=frontend_path / 'licenses'), name='licenses')
        @application.get('/', include_in_schema=False)
        def frontend_index() -> FileResponse:
            return FileResponse(frontend_path / 'index.html')

    application.include_router(router, prefix="/api")
    application.include_router(catalog_router, prefix="/api")
    application.include_router(sales_router, prefix="/api")
    application.include_router(reporting_router, prefix="/api")
    application.include_router(operations_router, prefix="/api")
    return application


app = create_app()
