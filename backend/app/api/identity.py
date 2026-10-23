"""Contratos HTTP, validación y adaptación de los casos de uso de identidad."""

import hmac
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.application.identity import IdentityService, csrf_token
from app.domain.identity import IdentityError, User

router = APIRouter()
COOKIE = "pos_session"


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.lower()


class Setup(Credentials):
    setup_token: SecretStr = Field(min_length=32, max_length=128)


class Deactivation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: Literal[False]


class PublicUser(BaseModel):
    id: int
    username: str
    role: Literal["ADMIN", "EMPLOYEE"]
    is_active: bool


class SessionResponse(BaseModel):
    user: PublicUser
    csrf_token: str


def service(request: Request) -> IdentityService:
    return request.app.state.identity


def token(request: Request, csrf: bool = False) -> str:
    value = request.cookies.get(COOKIE, "")
    if csrf and not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), csrf_token(value)):
        raise IdentityError(403, "Token CSRF inválido")
    return value


def public(user: User) -> PublicUser:
    return PublicUser(**asdict(user))


@router.get("/auth/setup")
def setup_status(request: Request) -> dict[str, bool]:
    return {"initialized": service(request).initialized()}


@router.post("/auth/setup", status_code=201, response_model=PublicUser)
def setup(body: Setup, request: Request) -> PublicUser:
    return public(
        service(request).setup(
            body.username, body.password.get_secret_value(), body.setup_token.get_secret_value()
        )
    )


@router.post("/auth/login", response_model=SessionResponse)
def login(body: Credentials, request: Request, response: Response) -> SessionResponse:
    user, value = service(request).login(
        body.username, body.password.get_secret_value(), token(request)
    )
    response.set_cookie(
        COOKIE,
        value,
        max_age=IdentityService.session_seconds,
        httponly=True,
        samesite="strict",
        secure=request.app.state.secure_cookies,
        path="/api",
    )
    return SessionResponse(user=public(user), csrf_token=csrf_token(value))


@router.get("/auth/me", response_model=SessionResponse)
def me(request: Request) -> SessionResponse:
    value = token(request)
    return SessionResponse(user=public(service(request).me(value)), csrf_token=csrf_token(value))


@router.post("/auth/logout", status_code=204)
def logout(request: Request) -> Response:
    service(request).logout(token(request, csrf=True))
    response = Response(status_code=204)
    response.delete_cookie(
        COOKIE, path="/api", httponly=True, samesite="strict",
        secure=request.app.state.secure_cookies,
    )
    return response


@router.get("/employees", response_model=list[PublicUser])
def employees(request: Request) -> list[PublicUser]:
    return [public(user) for user in service(request).employees(token(request))]


@router.post("/employees", status_code=201, response_model=PublicUser)
def create_employee(body: Credentials, request: Request) -> PublicUser:
    return public(
        service(request).create_employee(
            token(request, csrf=True), body.username, body.password.get_secret_value()
        )
    )


@router.patch("/employees/{employee_id}", response_model=PublicUser)
def deactivate(employee_id: int, body: Deactivation, request: Request) -> PublicUser:
    return public(service(request).deactivate(token(request, csrf=True), employee_id))
