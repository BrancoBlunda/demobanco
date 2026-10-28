"""Levanta uvicorn de verdad en un puerto libre: las APIs se llaman por la red, sin atajos."""

import socket
import threading
import time

import httpx
import pytest
import uvicorn

from riel.main import create_app


@pytest.fixture
def servidor(ruta_base):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        puerto = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(create_app(ruta_base), host="127.0.0.1", port=puerto, log_level="warning")
    )
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()
    limite = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < limite, "uvicorn no arrancó"
        time.sleep(0.02)
    yield f"http://127.0.0.1:{puerto}"
    server.should_exit = True
    hilo.join(timeout=10)


def test_fraude_llama_a_listas_por_la_red(servidor):
    respuesta = httpx.post(
        f"{servidor}/v1/fraude/evaluar",
        json={"origen": "DEMO-1002", "destino": "DEMO-9001", "monto": 1, "canal": "home_banking"},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["motivos"] == ["destino_observado"]
    assert respuesta.json()["listas"]["status"] == 200


def test_transferencia_viaja_por_la_red(servidor):
    respuesta = httpx.post(
        f"{servidor}/v1/pagos/transferencias",
        json={
            "origen": "DEMO-1001",
            "destino": "DEMO-2001",
            "monto": 80_000,
            "canal": "home_banking",
            "referencia": "Factura 0001",
            "clave_idempotencia": "red-1",
        },
    )
    assert respuesta.status_code == 201
    traza = httpx.get(f"{servidor}{respuesta.json()['traza']}").json()
    assert [s["estado"] for s in traza["saltos"]] == ["ok"] * 5
