"""API de fraude: decide si una transferencia se retiene y por qué."""

from dataclasses import asdict, dataclass

from fastapi import APIRouter
from pydantic import BaseModel, StrictInt

from riel.config import UMBRAL_MONTO_ALTO

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


@router.post("/v1/fraude/evaluar", tags=["interna"])
def post_evaluar(solicitud: SolicitudFraude) -> dict:
    return asdict(evaluar(solicitud, cuentas_observadas=frozenset()))
