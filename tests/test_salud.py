from fastapi.testclient import TestClient

from riel.main import create_app


def test_salud_responde_ok():
    respuesta = TestClient(create_app()).get("/v1/salud")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ok"
