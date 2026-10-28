"""API de fraude: decide si una transferencia se retiene y por qué."""

import os
from dataclasses import asdict, dataclass

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel, StrictInt

from riel.config import UMBRAL_MONTO_ALTO
from riel.interno import cliente_interno
from riel.listas import PATH_OBSERVADAS

router = APIRouter()

MONTO_ALTO = "monto_alto"
API_SIN_REFERENCIA = "api_sin_referencia"
DESTINO_OBSERVADO = "destino_observado"
LISTAS_NO_DISPONIBLE = "listas_no_disponible"


class SolicitudFraude(BaseModel):
    origen: str
    destino: str
    monto: StrictInt
    canal: str
    referencia: str | None = None


@dataclass(frozen=True)
class Evaluacion:
    decision: str
    motivos: list[str]


def sin_referencia(referencia: str | None) -> bool:
    return referencia is None or not referencia.strip()


def evaluar(solicitud: SolicitudFraude, cuentas_observadas: frozenset[str] | None) -> Evaluacion:
    """Aplica las reglas. `cuentas_observadas` es None si la API de listas no está disponible."""
    motivos = []
    if solicitud.monto >= UMBRAL_MONTO_ALTO:
        motivos.append(MONTO_ALTO)
    if solicitud.canal == "api" and sin_referencia(solicitud.referencia):
        motivos.append(API_SIN_REFERENCIA)
    if cuentas_observadas is None:
        motivos.append(LISTAS_NO_DISPONIBLE)
    elif solicitud.destino in cuentas_observadas:
        motivos.append(DESTINO_OBSERVADO)
    return Evaluacion(decision="retenida" if motivos else "aprobada", motivos=motivos)


def token_saliente() -> str:
    return os.environ.get("LISTAS_API_TOKEN", "")


async def consultar_listas(request: Request) -> tuple[frozenset[str] | None, int | None]:
    """Llama por HTTP a la API de listas. Devuelve (observadas o None, status HTTP)."""
    try:
        async with cliente_interno(request) as http:
            respuesta = await http.get(
                PATH_OBSERVADAS, headers={"Authorization": f"Bearer {token_saliente()}"}
            )
    except httpx.HTTPError:
        return None, None
    if respuesta.status_code != 200:
        return None, respuesta.status_code
    return frozenset(respuesta.json()["cuentas"]), respuesta.status_code


@router.post("/v1/fraude/evaluar", tags=["interna"])
async def post_evaluar(solicitud: SolicitudFraude, request: Request) -> dict:
    observadas, status_listas = await consultar_listas(request)
    return {
        **asdict(evaluar(solicitud, observadas)),
        "listas": {"metodo": "GET", "path": PATH_OBSERVADAS, "status": status_listas},
    }
