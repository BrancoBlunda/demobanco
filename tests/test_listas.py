import pytest

from riel import fraude
from tests.conftest import TOKEN_DE_FIXTURE

SOLICITUD = {
    "origen": "DEMO-1002",
    "destino": "DEMO-9001",
    "monto": 30_000,
    "canal": "home_banking",
    "referencia": "Pago",
}


def test_listas_devuelve_solo_demo_9001_con_token_valido(cliente):
    respuesta = cliente.get(
        "/v1/listas/observadas", headers={"Authorization": f"Bearer {TOKEN_DE_FIXTURE}"}
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == {"cuentas": ["DEMO-9001"]}


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer otro-token"}, {"Authorization": TOKEN_DE_FIXTURE}],
)
def test_listas_responde_401_sin_token_valido(cliente, headers):
    respuesta = cliente.get("/v1/listas/observadas", headers=headers)
    assert respuesta.status_code == 401


def test_listas_responde_401_si_el_entorno_no_tiene_token(cliente, monkeypatch):
    monkeypatch.delenv("LISTAS_API_TOKEN")
    respuesta = cliente.get("/v1/listas/observadas", headers={"Authorization": "Bearer "})
    assert respuesta.status_code == 401


def test_fraude_consulta_listas_por_http_y_retiene_destino_observado(cliente):
    respuesta = cliente.post("/v1/fraude/evaluar", json=SOLICITUD)
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "decision": "retenida",
        "motivos": ["destino_observado"],
        "listas": {"metodo": "GET", "path": "/v1/listas/observadas", "status": 200},
    }


def test_fraude_aprueba_destino_no_observado(cliente):
    respuesta = cliente.post("/v1/fraude/evaluar", json={**SOLICITUD, "destino": "DEMO-2001"})
    assert respuesta.json()["decision"] == "aprobada"
    assert respuesta.json()["motivos"] == []


def test_token_faltante_retiene_por_listas_no_disponible(cliente, monkeypatch):
    monkeypatch.delenv("LISTAS_API_TOKEN")
    respuesta = cliente.post("/v1/fraude/evaluar", json={**SOLICITUD, "destino": "DEMO-2001"})
    cuerpo = respuesta.json()
    assert cuerpo["decision"] == "retenida"
    assert cuerpo["motivos"] == ["listas_no_disponible"]
    assert cuerpo["listas"]["status"] == 401


def test_token_distinto_retiene_por_listas_no_disponible(cliente, monkeypatch):
    monkeypatch.setattr(fraude, "token_saliente", lambda: "token-que-no-coincide")
    respuesta = cliente.post("/v1/fraude/evaluar", json={**SOLICITUD, "destino": "DEMO-2001"})
    assert respuesta.json()["motivos"] == ["listas_no_disponible"]
    assert respuesta.json()["listas"]["status"] == 401
