import pytest

from riel import config
from riel.fraude import SolicitudFraude, evaluar

OBSERVADAS = frozenset({"DEMO-9001"})


def solicitud(**cambios) -> SolicitudFraude:
    datos = {
        "origen": "DEMO-1001",
        "destino": "DEMO-2001",
        "monto": 80_000,
        "canal": "home_banking",
        "referencia": "Factura 0001",
    }
    return SolicitudFraude(**{**datos, **cambios})


def test_umbral_monto_alto_es_500000():
    assert config.UMBRAL_MONTO_ALTO == 500_000


def test_sin_motivos_se_aprueba():
    evaluacion = evaluar(solicitud(), OBSERVADAS)
    assert evaluacion.decision == "aprobada"
    assert evaluacion.motivos == []


@pytest.mark.parametrize(
    ("monto", "motivos"),
    [(499_999, []), (500_000, ["monto_alto"]), (900_000, ["monto_alto"])],
)
def test_monto_alto_desde_el_umbral_inclusive(monto, motivos):
    assert evaluar(solicitud(monto=monto), OBSERVADAS).motivos == motivos


@pytest.mark.parametrize("referencia", [None, "", "   "])
def test_api_sin_referencia_retiene(referencia):
    evaluacion = evaluar(solicitud(canal="api", referencia=referencia), OBSERVADAS)
    assert evaluacion.decision == "retenida"
    assert evaluacion.motivos == ["api_sin_referencia"]


def test_api_con_referencia_y_otros_canales_sin_referencia_no_retienen():
    assert evaluar(solicitud(canal="api"), OBSERVADAS).motivos == []
    assert evaluar(solicitud(referencia=None), OBSERVADAS).motivos == []


def test_destino_observado_retiene():
    evaluacion = evaluar(solicitud(destino="DEMO-9001"), OBSERVADAS)
    assert evaluacion.decision == "retenida"
    assert evaluacion.motivos == ["destino_observado"]


def test_listas_no_disponible_retiene():
    evaluacion = evaluar(solicitud(), None)
    assert evaluacion.decision == "retenida"
    assert evaluacion.motivos == ["listas_no_disponible"]


def test_acumula_todos_los_motivos():
    evaluacion = evaluar(
        solicitud(destino="DEMO-9001", monto=600_000, canal="api", referencia=None), OBSERVADAS
    )
    assert evaluacion.motivos == ["monto_alto", "api_sin_referencia", "destino_observado"]


def test_endpoint_evaluar(cliente):
    respuesta = cliente.post(
        "/v1/fraude/evaluar",
        json={"origen": "DEMO-1003", "destino": "DEMO-2002", "monto": 900_000, "canal": "api"},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["decision"] == "retenida"
    assert respuesta.json()["motivos"] == ["monto_alto", "api_sin_referencia"]
