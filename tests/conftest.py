import httpx
import pytest
from fastapi.testclient import TestClient

from riel.main import create_app

TOKEN_DE_FIXTURE = "token-de-fixture-solo-para-tests"


@pytest.fixture(autouse=True)
def token_listas(monkeypatch):
    monkeypatch.setenv("LISTAS_API_TOKEN", TOKEN_DE_FIXTURE)
    monkeypatch.delenv("RIEL_URL_INTERNA", raising=False)
    return TOKEN_DE_FIXTURE


@pytest.fixture
def ruta_base(tmp_path):
    return str(tmp_path / "riel-test.db")


@pytest.fixture
def cliente(ruta_base):
    app = create_app(ruta_base)
    with TestClient(app) as cliente:
        app.state.transporte_interno = httpx.ASGITransport(app=app)
        yield cliente


def saldos(cliente: TestClient) -> dict[str, int]:
    return {c["id"]: c["saldo"] for c in cliente.get("/v1/cuentas").json()["cuentas"]}
