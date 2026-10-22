"""Contratos tipados de importación y respaldos; ADMIN real y CSRF en escrituras."""
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field, SecretStr, StrictBool, StrictInt

from app.api.catalog import Input, Reason
from app.api.identity import token
from app.domain.catalog import Record

router = APIRouter()
CSVText = Annotated[str, Field(max_length=1048576)]


class CsvInput(Input):
    content: CSVText


class CsvConfirm(CsvInput):
    source_hash: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    idempotency_key: UUID
    reason: Reason


class PreviewRow(BaseModel):
    row: int
    name: str
    code: str | None
    price_cents: int
    initial_stock: int
    minimum_stock: int


class RowError(BaseModel):
    row: int
    message: str


class Preview(BaseModel):
    source_hash: str
    rows: list[PreviewRow]
    errors: list[RowError]


class Imported(BaseModel):
    product_ids: list[int]
    replayed: bool


class BackupSettings(Input):
    enabled: StrictBool
    interval_hours: Annotated[StrictInt, Field(ge=1, le=168)]
    retention: Annotated[StrictInt, Field(ge=1, le=30)]


class SettingsOut(BaseModel):
    enabled: int
    interval_hours: int
    retention: int
    last_attempt: int
    last_success: int
    last_error: str | None


class BackupOut(BaseModel):
    id: str
    kind: str
    created_at_utc: str
    schema_revision: str = Field(validation_alias="schema")
    size_bytes: int


class BackupStatus(BaseModel):
    settings: SettingsOut
    backups: list[BackupOut]
    shutdown_available: bool


class Upload(Input):
    content_base64: Annotated[str, Field(max_length=44826624)]


class Restore(Input):
    backup_id: UUID
    password: SecretStr = Field(min_length=12, max_length=128)
    confirmation: Literal['RESTAURAR']


class Restored(BaseModel):
    restored: bool
    previous_backup_id: str


@router.post('/imports/products/preview', response_model=Preview)
def preview(body: CsvInput, request: Request) -> Record:
    return request.app.state.imports.preview(token(request, csrf=True), body.content)


@router.post('/imports/products/confirm', response_model=Imported)
def confirm(body: CsvConfirm, request: Request) -> Record:
    return request.app.state.imports.confirm(token(request, csrf=True), body.content, str(body.idempotency_key), body.source_hash, body.reason)


@router.get('/backups', response_model=BackupStatus)
def backups(request: Request) -> Record:
    return {**request.app.state.maintenance.status(token(request)),
            'shutdown_available': request.app.state.request_shutdown is not None}


@router.post('/backups', response_model=BackupOut)
def backup(request: Request) -> Record:
    return request.app.state.maintenance.create(token(request, csrf=True))


@router.put('/backups/settings', response_model=SettingsOut)
def settings(body: BackupSettings, request: Request) -> Record:
    return request.app.state.maintenance.configure(token(request, csrf=True), **body.model_dump())


@router.post('/backups/upload', response_model=BackupOut)
def upload(body: Upload, request: Request) -> Record:
    return request.app.state.maintenance.upload(token(request, csrf=True), body.content_base64)


@router.get('/backups/{backup_id}/download')
def download(backup_id: UUID, request: Request) -> Response:
    content = request.app.state.maintenance.download(token(request), str(backup_id))
    return Response(content, media_type='application/octet-stream', headers={'Content-Disposition': f'attachment; filename="pos-{backup_id}.posbackup"'})


@router.post('/backups/restore', response_model=Restored)
def restore(body: Restore, request: Request) -> Record:
    return request.app.state.maintenance.restore(token(request, csrf=True), str(body.backup_id), body.password.get_secret_value())


@router.post('/runtime/shutdown')
def shutdown(request: Request) -> dict[str, bool]:
    from app.domain.identity import IdentityError
    request.app.state.maintenance.store.admin(token(request, csrf=True))
    callback = request.app.state.request_shutdown
    if callback is None:
        raise IdentityError(409, 'El cierre se realiza desde la terminal de desarrollo')
    callback()
    return {'stopping': True}
