from fastapi.testclient import TestClient

from riel.base import Base
from riel.main import create_app
from riel.semilla import CUENTAS_SEMILLA, sembrar_si_vacia
from tests.conftest import saldos


def asiento(cliente, clave="clave-1", origen="DEMO-1001", destino="DEMO-2001", monto=80_000):
    return cliente.post(
        "/v1/libro/asientos",
        json={"clave_idempotencia": clave, "origen": origen, "destino": destino, "monto": monto},
    )


def test_semilla_carga_las_seis_cuentas_demo(cliente):
    assert saldos(cliente) == {
        "DEMO-1001": 2_000_000,
        "DEMO-1002": 800_000,
        "DEMO-1003": 3_500_000,
        "DEMO-2001": 400_000,
        "DEMO-2002": 150_000,
        "DEMO-9001": 100_000,
    }
    titulares = {c["id"]: c["titular"] for c in cliente.get("/v1/cuentas").json()["cuentas"]}
    assert titulares["DEMO-2002"] == "Mónica Alegre"


def test_semilla_solo_si_la_base_esta_vacia(ruta_base):
    base = Base(ruta_base)
    assert sembrar_si_vacia(base) is True
    with base.transaccion() as conexion:
        conexion.execute("UPDATE cuentas SET saldo = 1 WHERE id = 'DEMO-1001'")
    assert sembrar_si_vacia(base) is False
    base.cerrar()

    with TestClient(create_app(ruta_base)) as cliente:
        assert saldos(cliente)["DEMO-1001"] == 1
        assert len(saldos(cliente)) == len(CUENTAS_SEMILLA)


def test_asiento_debita_origen_y_acredita_destino(cliente):
    respuesta = asiento(cliente)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["reintento"] is False
    assert cuerpo["saldo_origen"] == 1_920_000
    assert cuerpo["saldo_destino"] == 480_000
    assert saldos(cliente)["DEMO-1001"] == 1_920_000
    assert saldos(cliente)["DEMO-2001"] == 480_000


def test_misma_clave_produce_un_solo_asiento(cliente, ruta_base):
    primero = asiento(cliente)
    reintento = asiento(cliente)
    assert reintento.status_code == 200
    assert reintento.json()["reintento"] is True
    assert reintento.json()["asiento_id"] == primero.json()["asiento_id"]
    assert saldos(cliente)["DEMO-1001"] == 1_920_000
    assert saldos(cliente)["DEMO-2001"] == 480_000
    cantidad = cliente.app.state.base.consultar("SELECT COUNT(*) AS n FROM asientos")[0]["n"]
    assert cantidad == 1


def test_saldo_insuficiente_no_mueve_saldos(cliente):
    respuesta = asiento(cliente, origen="DEMO-2002", monto=150_001)
    assert respuesta.status_code == 409
    assert respuesta.json() == {"error": "saldo_insuficiente"}
    assert saldos(cliente)["DEMO-2002"] == 150_000


def test_cuenta_inexistente(cliente):
    respuesta = asiento(cliente, destino="DEMO-0000")
    assert respuesta.status_code == 404
    assert saldos(cliente)["DEMO-1001"] == 2_000_000


def test_monto_debe_ser_entero_positivo(cliente):
    assert asiento(cliente, monto=10.5).status_code == 422
    assert asiento(cliente, monto=0).status_code == 422
