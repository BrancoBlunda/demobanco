import pytest
from fastapi.testclient import TestClient

from riel.main import create_app


@pytest.fixture
def ruta_base(tmp_path):
    return str(tmp_path / "riel-test.db")


@pytest.fixture
def cliente(ruta_base):
    with TestClient(create_app(ruta_base)) as cliente:
        yield cliente


def saldos(cliente: TestClient) -> dict[str, int]:
    return {c["id"]: c["saldo"] for c in cliente.get("/v1/cuentas").json()["cuentas"]}
