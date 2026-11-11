"""API de pagos: recibe la transferencia, la valida y la hace viajar por fraude y libro vía HTTP."""

import json
import sqlite3
import uuid
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from riel import bitacora
from riel.base import Base
from riel.interno import cliente_interno
from riel.libro import BaseDep
from riel.validacion import validar

router = APIRouter()

PATH_TRANSFERENCIAS = "/v1/pagos/transferencias"
PATH_FRAUDE = "/v1/fraude/evaluar"
PATH_ASIENTOS = "/v1/libro/asientos"
NODOS = ("origen", "api_pagos", "fraude", "libro", "destino")
STATUS_POR_ESTADO = {"posteada": 201, "retenida": 202, "rechazada": 422}
ULTIMAS = 20


def salto(
    nodo: str,
    estado: str,
    metodo: str,
    path: str,
    status: int | None = None,
    recorte: dict | None = None,
) -> dict:
    return {
        "nodo": nodo,
        "estado": estado,
        "metodo": metodo,
        "path": path,
        "status": status,
        "recorte": recorte,
    }


def omitido(nodo: str) -> dict:
    path = PATH_FRAUDE if nodo == "fraude" else PATH_ASIENTOS
    return salto(nodo, "omitido", "POST", path)


def _texto(valor: object) -> str | None:
    return valor if isinstance(valor, str) else None


def _entero(valor: object) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _recorte_solicitud(entrada: dict[str, Any]) -> dict:
    claves = ("origen", "destino", "monto", "canal", "referencia", "clave_idempotencia")
    return {clave: entrada.get(clave) for clave in claves if clave in entrada}


def _fila_a_dict(fila: sqlite3.Row) -> dict:
    return {
        "id": fila["id"],
        "estado": fila["estado"],
        "motivos": json.loads(fila["motivos"]),
        "origen": fila["origen"],
        "destino": fila["destino"],
        "monto": fila["monto"],
        "canal": fila["canal"],
        "referencia": fila["referencia"],
        "clave_idempotencia": fila["clave_idempotencia"],
        "creada": fila["creada"],
    }


def _buscar_por_clave(base: Base, clave: str) -> sqlite3.Row | None:
    filas = base.consultar("SELECT * FROM transferencias WHERE clave_idempotencia = ?", (clave,))
    return filas[0] if filas else None


def _respuesta(fila: sqlite3.Row, reintento: bool) -> JSONResponse:
    cuerpo = {
        **_fila_a_dict(fila),
        "reintento": reintento,
        "traza": f"{PATH_TRANSFERENCIAS}/{fila['id']}/traza",
    }
    status = 200 if reintento else STATUS_POR_ESTADO.get(fila["estado"], 200)
    return JSONResponse(cuerpo, status_code=status)


def _reintento(base: Base, fila: sqlite3.Row) -> JSONResponse:
    with base.transaccion() as conexion:
        bitacora.registrar(
            conexion,
            fila["id"],
            "reintento",
            fila["origen"],
            fila["destino"],
            fila["monto"],
            json.loads(fila["motivos"]),
        )
    return _respuesta(fila, reintento=True)


def _cerrar(
    base: Base,
    transferencia_id: str,
    estado: str,
    motivos: list[str],
    saltos: list[dict],
    entrada: dict[str, Any],
) -> sqlite3.Row:
    saltos[0]["status"] = STATUS_POR_ESTADO[estado]
    saltos[1]["status"] = STATUS_POR_ESTADO[estado]
    with base.transaccion() as conexion:
        conexion.execute(
            "UPDATE transferencias SET estado = ?, motivos = ?, traza = ? WHERE id = ?",
            (estado, json.dumps(motivos), json.dumps(saltos), transferencia_id),
        )
        bitacora.registrar(
            conexion,
            transferencia_id,
            estado,
            entrada.get("origen"),
            entrada.get("destino"),
            _entero(entrada.get("monto")),
            motivos,
        )
        return conexion.execute(
            "SELECT * FROM transferencias WHERE id = ?", (transferencia_id,)
        ).fetchone()


def _crear(base: Base, entrada: dict[str, Any], clave: str | None) -> str | sqlite3.Row:
    """Inserta la transferencia. Si la clave ya existe devuelve la fila previa (reintento)."""
    transferencia_id = f"TRF-{uuid.uuid4().hex[:10].upper()}"
    try:
        with base.transaccion() as conexion:
            conexion.execute(
                "INSERT INTO transferencias (id, clave_idempotencia, origen, destino, monto,"
                " canal, referencia, estado) VALUES (?, ?, ?, ?, ?, ?, ?, 'procesando')",
                (
                    transferencia_id,
                    clave,
                    _texto(entrada.get("origen")),
                    _texto(entrada.get("destino")),
                    _entero(entrada.get("monto")),
                    _texto(entrada.get("canal")),
                    _texto(entrada.get("referencia")),
                ),
            )
    except sqlite3.IntegrityError:
        previa = _buscar_por_clave(base, clave) if clave else None
        if previa is None:
            raise
        return previa
    return transferencia_id


async def _llamar(request: Request, path: str, cuerpo: dict) -> tuple[int | None, dict]:
    try:
        async with cliente_interno(request) as http:
            respuesta = await http.post(path, json=cuerpo)
    except httpx.HTTPError:
        return None, {"error": "sin_respuesta"}
    try:
        return respuesta.status_code, respuesta.json()
    except ValueError:
        return respuesta.status_code, {}


@router.post(PATH_TRANSFERENCIAS)
async def post_transferencia(
    request: Request, base: BaseDep, entrada: Annotated[dict[str, Any], Body()]
) -> JSONResponse:
    clave = entrada.get("clave_idempotencia")
    if not isinstance(clave, str) or not clave.strip():
        clave = None
    if clave:
        previa = _buscar_por_clave(base, clave)
        if previa is not None:
            return _reintento(base, previa)

    cuentas = {fila["id"] for fila in base.consultar("SELECT id FROM cuentas")}
    rechazos = validar(entrada, cuentas)
    creada = _crear(base, entrada, None if rechazos else clave)
    if isinstance(creada, sqlite3.Row):
        return _reintento(base, creada)
    transferencia_id = creada

    saltos = [
        salto("origen", "ok", "POST", PATH_TRANSFERENCIAS, recorte=_recorte_solicitud(entrada)),
        salto("api_pagos", "ok", "POST", PATH_TRANSFERENCIAS),
    ]

    def terminar(estado: str, motivos: list[str]) -> JSONResponse:
        saltos[1]["recorte"] = {"id": transferencia_id, "estado": estado, "motivos": motivos}
        saltos.extend(omitido(nodo) for nodo in NODOS[len(saltos) :])
        fila = _cerrar(base, transferencia_id, estado, motivos, saltos, entrada)
        return _respuesta(fila, reintento=False)

    if rechazos:
        saltos[1]["estado"] = "rechazada"
        return terminar("rechazada", rechazos)

    origen, destino, monto = entrada["origen"], entrada["destino"], entrada["monto"]
    status, evaluacion = await _llamar(
        request,
        PATH_FRAUDE,
        {
            "origen": origen,
            "destino": destino,
            "monto": monto,
            "canal": entrada["canal"],
            "referencia": entrada.get("referencia"),
        },
    )
    if status != 200:
        evaluacion = {"decision": "retenida", "motivos": ["fraude_no_disponible"]}
    retenida = evaluacion.get("decision") != "aprobada"
    saltos.append(
        salto(
            "fraude",
            "retenida" if retenida else "ok",
            "POST",
            PATH_FRAUDE,
            status,
            {"decision": evaluacion.get("decision"), "motivos": evaluacion.get("motivos", [])},
        )
    )
    if retenida:
        return terminar("retenida", list(evaluacion.get("motivos", [])))

    status, asiento = await _llamar(
        request,
        PATH_ASIENTOS,
        {
            "clave_idempotencia": clave or transferencia_id,
            "origen": origen,
            "destino": destino,
            "monto": monto,
        },
    )
    if status not in (200, 201):
        motivo = asiento.get("error") or "libro_no_disponible"
        saltos.append(salto("libro", "rechazada", "POST", PATH_ASIENTOS, status, asiento))
        return terminar("rechazada", [motivo])

    saltos.append(
        salto(
            "libro",
            "ok",
            "POST",
            PATH_ASIENTOS,
            status,
            {
                "asiento_id": asiento["asiento_id"],
                "cuenta": origen,
                "debito": monto,
                "saldo": asiento["saldo_origen"],
            },
        )
    )
    saltos.append(
        salto(
            "destino",
            "ok",
            "POST",
            PATH_ASIENTOS,
            status,
            {
                "asiento_id": asiento["asiento_id"],
                "cuenta": destino,
                "credito": monto,
                "saldo": asiento["saldo_destino"],
            },
        )
    )
    return terminar("posteada", [])


@router.get(PATH_TRANSFERENCIAS + "/{transferencia_id}/traza")
def get_traza(transferencia_id: str, base: BaseDep) -> JSONResponse:
    filas = base.consultar("SELECT * FROM transferencias WHERE id = ?", (transferencia_id,))
    if not filas:
        return JSONResponse({"error": "transferencia_inexistente"}, status_code=404)
    fila = filas[0]
    return JSONResponse(
        {
            "id": fila["id"],
            "estado": fila["estado"],
            "motivos": json.loads(fila["motivos"]),
            "saltos": json.loads(fila["traza"]),
        }
    )


@router.get("/v1/transferencias")
def get_transferencias(base: BaseDep) -> dict:
    filas = base.consultar(
        "SELECT * FROM transferencias WHERE estado != 'procesando' ORDER BY orden DESC LIMIT ?",
        (ULTIMAS,),
    )
    return {"transferencias": [_fila_a_dict(fila) for fila in filas]}
