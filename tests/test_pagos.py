import json

import httpx
import pytest

from riel import config
from tests.conftest import saldos

BASE = {
    "origen": "DEMO-1001",
    "destino": "DEMO-2001",
    "monto": 80_000,
    "canal": "home_banking",
    "referencia": "Factura 0001",
}


def transferir(cliente, **cambios):
    return cliente.post("/v1/pagos/transferencias", json={**BASE, **cambios})


def traza(cliente, transferencia_id):
    return cliente.get(f"/v1/pagos/transferencias/{transferencia_id}/traza").json()


def estados(cliente, transferencia_id):
    return [s["estado"] for s in traza(cliente, transferencia_id)["saltos"]]


def test_sin_motivos_se_postea_debitando_y_acreditando(cliente):
    respuesta = transferir(cliente, clave_idempotencia="k-1")
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "posteada"
    assert cuerpo["motivos"] == []
    assert cuerpo["reintento"] is False
    assert saldos(cliente)["DEMO-1001"] == 1_920_000
    assert saldos(cliente)["DEMO-2001"] == 480_000


@pytest.mark.parametrize(
    ("cambios", "motivos"),
    [
        ({"origen": "DEMO-1003", "destino": "DEMO-2002", "monto": 900_000}, ["monto_alto"]),
        ({"monto": config.UMBRAL_MONTO_ALTO}, ["monto_alto"]),
        ({"canal": "api", "referencia": ""}, ["api_sin_referencia"]),
        ({"canal": "api", "referencia": None}, ["api_sin_referencia"]),
        ({"origen": "DEMO-1002", "destino": "DEMO-9001", "monto": 30_000}, ["destino_observado"]),
    ],
)
def test_cualquier_motivo_retiene_sin_mover_saldos(cliente, cambios, motivos):
    antes = saldos(cliente)
    respuesta = transferir(cliente, **cambios)
    assert respuesta.status_code == 202
    assert respuesta.json()["estado"] == "retenida"
    assert respuesta.json()["motivos"] == motivos
    assert saldos(cliente) == antes


def test_listas_sin_token_retiene_por_listas_no_disponible(cliente, monkeypatch):
    monkeypatch.delenv("LISTAS_API_TOKEN")
    antes = saldos(cliente)
    respuesta = transferir(cliente)
    assert respuesta.json()["estado"] == "retenida"
    assert respuesta.json()["motivos"] == ["listas_no_disponible"]
    assert saldos(cliente) == antes


def test_fraude_no_disponible_retiene_sin_mover_saldos(cliente):
    asgi = httpx.ASGITransport(app=cliente.app)

    async def fraude_caido(request):
        if request.method == "POST" and request.url.path == "/v1/fraude/evaluar":
            return httpx.Response(503, json={"error": "fraude_caido"})
        return await asgi.handle_async_request(request)

    cliente.app.state.transporte_interno = httpx.MockTransport(fraude_caido)
    antes = saldos(cliente)
    respuesta = transferir(cliente)
    assert respuesta.status_code == 202
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "retenida"
    assert cuerpo["motivos"] == ["fraude_no_disponible"]
    assert saldos(cliente) == antes
    assert estados(cliente, cuerpo["id"]) == ["ok", "ok", "retenida", "omitido", "omitido"]
    fraude = traza(cliente, cuerpo["id"])["saltos"][2]
    assert fraude["nodo"] == "fraude"
    assert fraude["status"] == 503


@pytest.mark.parametrize(
    ("cambios", "motivo"),
    [
        ({"origen": None}, "origen_faltante"),
        ({"origen": ""}, "origen_faltante"),
        ({"destino": None}, "destino_faltante"),
        ({"destino": "DEMO-1001"}, "misma_cuenta"),
        ({"monto": 100.5}, "monto_no_entero"),
        ({"monto": "80000"}, "monto_no_entero"),
        ({"monto": True}, "monto_no_entero"),
        ({"monto": 0}, "monto_no_positivo"),
        ({"monto": -5}, "monto_no_positivo"),
        ({"monto": config.MONTO_MAXIMO + 1}, "monto_excede_maximo"),
        ({"moneda": "USD"}, "moneda_no_soportada"),
        ({"canal": "cajero"}, "canal_invalido"),
        ({"canal": None}, "canal_invalido"),
        ({"canal": "sucursal", "referencia": ""}, "sucursal_sin_referencia"),
        ({"canal": "sucursal", "referencia": None}, "sucursal_sin_referencia"),
        ({"destino": "DEMO-0000"}, "destino_inexistente"),
    ],
)
def test_rechazos_no_pasan_por_fraude(cliente, cambios, motivo):
    antes = saldos(cliente)
    respuesta = transferir(cliente, **cambios)
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "rechazada"
    assert motivo in cuerpo["motivos"]
    assert estados(cliente, cuerpo["id"]) == [
        "ok",
        "rechazada",
        "omitido",
        "omitido",
        "omitido",
    ]
    assert saldos(cliente) == antes


def test_monto_maximo_y_moneda_ars_explicita_se_aceptan(cliente):
    respuesta = transferir(cliente, origen="DEMO-1003", monto=40_000, moneda="ARS")
    assert respuesta.json()["estado"] == "posteada"
    respuesta = transferir(cliente, monto=config.MONTO_MAXIMO)
    assert "monto_excede_maximo" not in respuesta.json()["motivos"]


def test_sucursal_con_referencia_se_postea(cliente):
    assert transferir(cliente, canal="sucursal").json()["estado"] == "posteada"


def test_misma_clave_un_solo_asiento_y_reintento_no_debita(cliente):
    primera = transferir(cliente, clave_idempotencia="tanda-1")
    reintento = transferir(cliente, clave_idempotencia="tanda-1")
    assert reintento.status_code == 200
    assert reintento.json()["reintento"] is True
    assert reintento.json()["id"] == primera.json()["id"]
    assert reintento.json()["estado"] == "posteada"
    assert saldos(cliente)["DEMO-1001"] == 1_920_000
    assert saldos(cliente)["DEMO-2001"] == 480_000
    base = cliente.app.state.base
    assert base.consultar("SELECT COUNT(*) AS n FROM asientos")[0]["n"] == 1
    assert base.consultar("SELECT COUNT(*) AS n FROM transferencias")[0]["n"] == 1


def test_reintento_de_una_retenida_devuelve_la_retenida(cliente):
    primera = transferir(cliente, monto=900_000, clave_idempotencia="k-ret")
    reintento = transferir(cliente, monto=900_000, clave_idempotencia="k-ret")
    assert reintento.json()["id"] == primera.json()["id"]
    assert reintento.json()["estado"] == "retenida"


def test_un_rechazo_no_consume_la_clave(cliente):
    assert transferir(cliente, monto=0, clave_idempotencia="k-fix").status_code == 422
    corregida = transferir(cliente, clave_idempotencia="k-fix")
    assert corregida.status_code == 201
    assert corregida.json()["estado"] == "posteada"


def test_saldo_insuficiente_rechaza_en_el_libro(cliente):
    respuesta = transferir(cliente, origen="DEMO-2002", monto=150_001)
    assert respuesta.json()["estado"] == "rechazada"
    assert respuesta.json()["motivos"] == ["saldo_insuficiente"]
    assert estados(cliente, respuesta.json()["id"]) == ["ok", "ok", "ok", "rechazada", "omitido"]
    assert saldos(cliente)["DEMO-2002"] == 150_000


def test_traza_posteada_en_orden_con_metodo_path_y_status(cliente):
    transferencia_id = transferir(cliente).json()["id"]
    cuerpo = traza(cliente, transferencia_id)
    assert cuerpo["estado"] == "posteada"
    saltos = cuerpo["saltos"]
    assert [s["nodo"] for s in saltos] == ["origen", "api_pagos", "fraude", "libro", "destino"]
    assert [s["estado"] for s in saltos] == ["ok"] * 5
    assert [(s["metodo"], s["path"], s["status"]) for s in saltos] == [
        ("POST", "/v1/pagos/transferencias", 201),
        ("POST", "/v1/pagos/transferencias", 201),
        ("POST", "/v1/fraude/evaluar", 200),
        ("POST", "/v1/libro/asientos", 201),
        ("POST", "/v1/libro/asientos", 201),
    ]
    assert saltos[0]["recorte"]["monto"] == 80_000
    assert saltos[2]["recorte"] == {"decision": "aprobada", "motivos": []}
    assert saltos[3]["recorte"]["debito"] == 80_000
    assert saltos[4]["recorte"] == {
        "asiento_id": saltos[3]["recorte"]["asiento_id"],
        "cuenta": "DEMO-2001",
        "credito": 80_000,
        "saldo": 480_000,
    }


def test_traza_retenida_omite_libro_y_destino(cliente):
    transferencia_id = transferir(cliente, destino="DEMO-9001").json()["id"]
    saltos = traza(cliente, transferencia_id)["saltos"]
    assert [s["nodo"] for s in saltos] == ["origen", "api_pagos", "fraude", "libro", "destino"]
    assert [s["estado"] for s in saltos] == ["ok", "ok", "retenida", "omitido", "omitido"]
    assert saltos[2]["recorte"] == {"decision": "retenida", "motivos": ["destino_observado"]}
    assert saltos[3]["status"] is None and saltos[3]["recorte"] is None
    assert saltos[4]["status"] is None and saltos[4]["recorte"] is None


def test_traza_inexistente_404(cliente):
    assert cliente.get("/v1/pagos/transferencias/TRF-NADA/traza").status_code == 404


def test_bitacora_guarda_solo_ultimos_4_caracteres(cliente):
    transferir(cliente, clave_idempotencia="k-bit")
    transferir(cliente, clave_idempotencia="k-bit")
    transferir(cliente, destino="DEMO-9001")
    transferir(cliente, destino="DEMO-1001")
    filas = cliente.app.state.base.consultar("SELECT * FROM bitacora ORDER BY id")
    assert [f["evento"] for f in filas] == ["posteada", "reintento", "retenida", "rechazada"]
    assert [(f["origen"], f["destino"]) for f in filas] == [
        ("1001", "2001"),
        ("1001", "2001"),
        ("1001", "9001"),
        ("1001", "1001"),
    ]
    volcado = json.dumps([dict(f) for f in filas])
    assert "DEMO-" not in volcado


def test_bitacora_con_cuentas_cortas_o_faltantes(cliente):
    transferir(cliente, origen="AB", destino=None)
    fila = cliente.app.state.base.consultar("SELECT * FROM bitacora")[0]
    assert (fila["origen"], fila["destino"]) == ("AB", "")


def test_listado_de_ultimas_transferencias(cliente):
    transferir(cliente)
    transferir(cliente, monto=900_000)
    transferir(cliente, destino="DEMO-1001")
    listado = cliente.get("/v1/transferencias").json()["transferencias"]
    assert [(t["estado"], t["monto"]) for t in listado] == [
        ("rechazada", 80_000),
        ("retenida", 900_000),
        ("posteada", 80_000),
    ]
    assert listado[1]["motivos"] == ["monto_alto"]
