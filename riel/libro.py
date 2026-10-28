"""API del libro: cuentas y asientos de doble partida, idempotentes por clave."""

from dataclasses import asdict, dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictInt

from riel.base import Base

router = APIRouter()


class AsientoEntrada(BaseModel):
    clave_idempotencia: str = Field(min_length=1)
    origen: str = Field(min_length=1)
    destino: str = Field(min_length=1)
    monto: StrictInt = Field(gt=0)


@dataclass(frozen=True)
class Asiento:
    asiento_id: int
    clave_idempotencia: str
    origen: str
    destino: str
    monto: int
    saldo_origen: int
    saldo_destino: int
    reintento: bool


class ErrorLibro(Exception):
    status = 400
    codigo = "error_libro"


class CuentaInexistente(ErrorLibro):
    status = 404
    codigo = "cuenta_inexistente"


class SaldoInsuficiente(ErrorLibro):
    status = 409
    codigo = "saldo_insuficiente"


def obtener_base(request: Request) -> Base:
    return request.app.state.base


BaseDep = Annotated[Base, Depends(obtener_base)]


def _asiento_desde_fila(fila, reintento: bool) -> Asiento:
    return Asiento(
        asiento_id=fila["id"],
        clave_idempotencia=fila["clave_idempotencia"],
        origen=fila["origen"],
        destino=fila["destino"],
        monto=fila["monto"],
        saldo_origen=fila["saldo_origen"],
        saldo_destino=fila["saldo_destino"],
        reintento=reintento,
    )


def registrar_asiento(base: Base, clave: str, origen: str, destino: str, monto: int) -> Asiento:
    """Debita el origen y acredita el destino una sola vez por clave_idempotencia."""
    with base.transaccion() as conexion:
        previo = conexion.execute(
            "SELECT * FROM asientos WHERE clave_idempotencia = ?", (clave,)
        ).fetchone()
        if previo is not None:
            return _asiento_desde_fila(previo, reintento=True)

        saldos = {
            fila["id"]: fila["saldo"]
            for fila in conexion.execute(
                "SELECT id, saldo FROM cuentas WHERE id IN (?, ?)", (origen, destino)
            )
        }
        if origen not in saldos or destino not in saldos:
            raise CuentaInexistente()
        if saldos[origen] < monto:
            raise SaldoInsuficiente()

        saldo_origen = saldos[origen] - monto
        saldo_destino = saldos[destino] + monto
        conexion.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (saldo_origen, origen))
        conexion.execute("UPDATE cuentas SET saldo = ? WHERE id = ?", (saldo_destino, destino))
        cursor = conexion.execute(
            "INSERT INTO asientos (clave_idempotencia, origen, destino, monto, saldo_origen,"
            " saldo_destino) VALUES (?, ?, ?, ?, ?, ?)",
            (clave, origen, destino, monto, saldo_origen, saldo_destino),
        )
        fila = conexion.execute(
            "SELECT * FROM asientos WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return _asiento_desde_fila(fila, reintento=False)


def listar_cuentas(base: Base) -> list[dict]:
    filas = base.consultar("SELECT id, titular, saldo FROM cuentas ORDER BY id")
    return [dict(fila) for fila in filas]


@router.get("/v1/cuentas")
def get_cuentas(base: BaseDep) -> dict:
    return {"cuentas": listar_cuentas(base)}


@router.post("/v1/libro/asientos", tags=["interna"])
def post_asiento(entrada: AsientoEntrada, base: BaseDep) -> JSONResponse:
    try:
        asiento = registrar_asiento(
            base, entrada.clave_idempotencia, entrada.origen, entrada.destino, entrada.monto
        )
    except ErrorLibro as error:
        return JSONResponse({"error": error.codigo}, status_code=error.status)
    return JSONResponse(asdict(asiento), status_code=200 if asiento.reintento else 201)
