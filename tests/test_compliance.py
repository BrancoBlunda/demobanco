from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from riel import config
from tests.test_pagos import transferir

PATH = "/v1/compliance/reporte-mensual"


def insertar(cliente, transferencia_id, creada, monto=1_000, estado="posteada"):
    with cliente.app.state.base.transaccion() as conexion:
        conexion.execute(
            "INSERT INTO transferencias (id, origen, destino, monto, canal, estado, creada)"
            " VALUES (?, 'DEMO-1001', 'DEMO-2001', ?, 'home_banking', ?, ?)",
            (transferencia_id, monto, estado, creada),
        )


def reporte(cliente, mes):
    respuesta = cliente.get(PATH, params={"mes": mes})
    assert respuesta.status_code == 200
    return respuesta.json()


def test_solo_suman_las_posteadas_y_el_reintento_no_duplica(cliente):
    transferir(cliente, clave_idempotencia="c-1")
    transferir(cliente, clave_idempotencia="c-1")
    transferir(cliente, monto=900_000, clave_idempotencia="c-2")
    transferir(cliente, canal="api", referencia="", clave_idempotencia="c-3")
    transferir(cliente, destino="DEMO-1001", clave_idempotencia="c-4")
    respuesta = cliente.get(PATH)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["mes"] == datetime.now(ZoneInfo(config.ZONA_HORARIA)).strftime("%Y-%m")
    assert cuerpo["moneda"] == "ARS"
    assert cuerpo["cantidad"] == 1
    assert cuerpo["total"] == 80_000


@pytest.mark.parametrize("estado", ["procesando", "retenida", "rechazada"])
def test_pendientes_retenidas_y_rechazadas_no_entran(cliente, estado):
    insertar(cliente, "TRF-A", "2026-11-10T15:00:00.000Z", estado=estado)
    assert reporte(cliente, "2026-11")["total"] == 0


def test_corta_el_mes_en_hora_de_argentina(cliente):
    insertar(cliente, "TRF-OCT", "2026-11-01T02:59:59.999Z", monto=1)
    insertar(cliente, "TRF-NOV-1", "2026-11-01T03:00:00.000Z", monto=10)
    insertar(cliente, "TRF-NOV-2", "2026-12-01T02:59:59.999Z", monto=100)
    insertar(cliente, "TRF-DIC", "2026-12-01T03:00:00.000Z", monto=1_000)
    assert reporte(cliente, "2026-10")["total"] == 1
    noviembre = reporte(cliente, "2026-11")
    assert (noviembre["cantidad"], noviembre["total"]) == (2, 110)
    assert noviembre["desde"] == "2026-11-01T00:00:00-03:00"
    assert noviembre["hasta"] == "2026-12-01T00:00:00-03:00"
    assert reporte(cliente, "2026-12")["total"] == 1_000


def test_entran_todos_los_dias_de_lunes_a_domingo(cliente):
    for dia in range(9, 16):
        insertar(cliente, f"TRF-{dia}", f"2026-11-{dia:02d}T15:00:00.000Z")
    assert reporte(cliente, "2026-11")["cantidad"] == 7


def test_diciembre_pasa_a_enero_del_anio_siguiente(cliente):
    insertar(cliente, "TRF-FIN", "2027-01-01T02:00:00.000Z", monto=5)
    assert reporte(cliente, "2026-12")["total"] == 5
    assert reporte(cliente, "2026-12")["hasta"] == "2027-01-01T00:00:00-03:00"


def test_mes_sin_posteadas_da_cero(cliente):
    assert reporte(cliente, "2020-02") | {"desde": None, "hasta": None} == {
        "mes": "2020-02",
        "desde": None,
        "hasta": None,
        "moneda": "ARS",
        "cantidad": 0,
        "total": 0,
    }


@pytest.mark.parametrize("mes", ["2026-13", "2026-00", "2026-1", "noviembre", "", "2026-11-01"])
def test_mes_invalido_responde_422(cliente, mes):
    respuesta = cliente.get(PATH, params={"mes": mes})
    assert respuesta.status_code == 422
    assert respuesta.json() == {"error": "mes_invalido"}
