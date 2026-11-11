"""Reporte mensual de compliance: transferencias posteadas en un mes calendario, en hora local."""

import re
from datetime import datetime, timezone
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from riel.base import Base
from riel.config import MONEDA, ZONA_HORARIA
from riel.libro import BaseDep

router = APIRouter()

PATH_REPORTE = "/v1/compliance/reporte-mensual"
FORMATO_MES = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")


def mes_actual() -> str:
    return datetime.now(ZoneInfo(ZONA_HORARIA)).strftime("%Y-%m")


def rango_del_mes(anio: int, mes: int) -> tuple[datetime, datetime]:
    """Del primer día del mes a las 00:00 hora local al primer día del mes siguiente."""
    zona = ZoneInfo(ZONA_HORARIA)
    desde = datetime(anio, mes, 1, tzinfo=zona)
    hasta = datetime(anio + mes // 12, mes % 12 + 1, 1, tzinfo=zona)
    return desde, hasta


def _utc(momento: datetime) -> str:
    """Mismo formato que `creada` en la base, para comparar como texto."""
    return momento.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _en_dia_habil(creada: str) -> bool:
    # Los fines de semana se consolidan el lunes y no entran en este corte.
    momento = datetime.fromisoformat(creada.replace("Z", "+00:00"))
    return momento.astimezone(ZoneInfo(ZONA_HORARIA)).weekday() < 5


def reporte_mensual(base: Base, anio: int, mes: int) -> dict:
    desde, hasta = rango_del_mes(anio, mes)
    filas = base.consultar(
        "SELECT monto, creada FROM transferencias"
        " WHERE estado = 'posteada' AND creada >= ? AND creada < ?",
        (_utc(desde), _utc(hasta)),
    )
    incluidas = [fila for fila in filas if _en_dia_habil(fila["creada"])]
    return {
        "mes": f"{anio:04d}-{mes:02d}",
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "moneda": MONEDA,
        "cantidad": len(incluidas),
        "total": sum(fila["monto"] for fila in incluidas),
    }


@router.get(PATH_REPORTE)
def get_reporte_mensual(base: BaseDep, mes: Annotated[str | None, Query()] = None) -> JSONResponse:
    coincidencia = FORMATO_MES.fullmatch(mes if mes is not None else mes_actual())
    if coincidencia is None:
        return JSONResponse({"error": "mes_invalido"}, status_code=422)
    anio, numero = int(coincidencia[1]), int(coincidencia[2])
    return JSONResponse(reporte_mensual(base, anio, numero))
