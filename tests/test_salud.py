def test_salud_responde_ok(cliente):
    respuesta = cliente.get("/v1/salud")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ok"
