"""API de listas: cuentas observadas. Exige Authorization: Bearer <LISTAS_API_TOKEN>."""

import os
import secrets

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

router = APIRouter()

PATH_OBSERVADAS = "/v1/listas/observadas"
CUENTAS_OBSERVADAS = ("DEMO-9001",)


def token_esperado() -> str:
    return os.environ.get("LISTAS_API_TOKEN", "")


def autorizado(authorization: str | None) -> bool:
    esperado = token_esperado()
    if not esperado or not authorization:
        return False
    esquema, _, token = authorization.partition(" ")
    return esquema.lower() == "bearer" and secrets.compare_digest(token.strip(), esperado)


@router.get(PATH_OBSERVADAS, tags=["interna"])
def get_observadas(authorization: str | None = Header(default=None)) -> JSONResponse:
    if not autorizado(authorization):
        return JSONResponse(
            {"error": "no_autorizado"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return JSONResponse({"cuentas": list(CUENTAS_OBSERVADAS)})
