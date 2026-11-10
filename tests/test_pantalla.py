def test_la_pagina_se_sirve_en_la_raiz(cliente):
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    html = respuesta.text
    for columna in ("Origen", "API Pagos", "Fraude", "Libro", "Destino"):
        assert f'<div class="titulo">{columna}</div>' in html
    assert "Simular tanda" in html
    assert "no es un banco real" in html
    assert "Reporte mensual de compliance" in html
    assert "/v1/compliance/reporte-mensual" in html


def test_la_pagina_no_llama_a_las_apis_internas(cliente):
    html = cliente.get("/").text
    for interna in ("/v1/fraude/", "/v1/libro/", "/v1/listas/"):
        assert interna not in html
