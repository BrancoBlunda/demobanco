---
name: probar-riel
description: Cómo instalar, levantar y probar Riel (banco ficticio de demostración) de punta a punta.
---

# Probar Riel

Riel es un banco ficticio de demostración. Los datos no son reales.

## 1. Instalar

```bash
cd demobanco
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Lint y tests

```bash
ruff check . && ruff format --check .
pytest -q
```

## 3. Levantar la app

El token de listas se lee del entorno. Para probar localmente generá uno descartable; no lo
escribas en ningún archivo versionado.

```bash
export LISTAS_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(16))')"
uvicorn riel.main:app --port 8000
```

## 4. Chequeo de salud

```bash
curl -s http://127.0.0.1:8000/v1/salud
# {"estado":"ok","servicio":"riel"}
```

## 5. Transferencia posteada

```bash
curl -s -X POST http://127.0.0.1:8000/v1/pagos/transferencias \
  -H 'Content-Type: application/json' \
  -d '{"origen":"DEMO-1001","destino":"DEMO-2001","monto":80000,"canal":"home_banking",
       "referencia":"Factura 0001","clave_idempotencia":"skill-1"}'
# HTTP 201, "estado":"posteada", "motivos":[]
```

Repetir el mismo comando: HTTP 200, `"reintento":true`, mismo `id`, y `GET /v1/cuentas` muestra
que DEMO-1001 se debitó una sola vez (2000000 → 1920000).

## 6. Transferencia retenida

```bash
curl -s -X POST http://127.0.0.1:8000/v1/pagos/transferencias \
  -H 'Content-Type: application/json' \
  -d '{"origen":"DEMO-1003","destino":"DEMO-2002","monto":900000,"canal":"home_banking",
       "referencia":"Honorarios","clave_idempotencia":"skill-2"}'
# HTTP 202, "estado":"retenida", "motivos":["monto_alto"]
```

## 7. Traza

```bash
curl -s http://127.0.0.1:8000/v1/pagos/transferencias/<id>/traza
```

Posteada: los cinco saltos `origen, api_pagos, fraude, libro, destino` en `ok`. Retenida: `fraude`
en `retenida` y `libro`, `destino` en `omitido`. En el log de uvicorn se ven las llamadas HTTP
reales: `GET /v1/listas/observadas`, `POST /v1/fraude/evaluar`, `POST /v1/libro/asientos`.

Para volver a la semilla: frená uvicorn y borrá `riel.db` (o usá `RIEL_DB=/tmp/riel.db`).

## 8. Reporte mensual de compliance

```bash
curl -s http://127.0.0.1:8000/v1/compliance/reporte-mensual
# {"mes":"2026-11","desde":"2026-11-01T00:00:00-03:00","hasta":"2026-12-01T00:00:00-03:00",
#  "moneda":"ARS","cantidad":1,"total":80000}
```

Solo suman las `posteada`. `?mes=2026-13` responde 422 `mes_invalido`.

## 9. Pantalla y animación

Con la app levantada (paso 3, con `LISTAS_API_TOKEN` exportado y una base nueva, por ejemplo
`RIEL_DB=/tmp/riel-ui.db`), abrí `http://127.0.0.1:8000/` en el navegador.

Qué comprobar:

1. Fondo oscuro, textos en español y el aviso "Datos de demostración · no es un banco real".
2. Cinco columnas en fila unidas por una línea: Origen, API Pagos, Fraude, Libro, Destino.
3. A la izquierda: selectores de origen y destino con las seis cuentas DEMO, monto, canal,
   referencia, y los botones Transferir y Simular tanda.
4. Transferir con los valores por defecto (DEMO-1001 → DEMO-2001, 80000, home_banking): el círculo
   viaja de columna en columna (unos 700 ms por salto), todas quedan verdes y debajo de la columna
   activa aparece la tarjeta con método, path, status y JSON corto. El saldo de DEMO-1001 baja.
5. Simular tanda: seis transferencias en serie, cada una se anima antes de empezar la siguiente
   (el texto de estado dice "Tanda n/6"):
   1. 80000 → `posteada`, cinco saltos verdes.
   2. 900000 → `retenida` por `monto_alto`: el círculo se frena rojo en Fraude; Libro y Destino
      grises.
   3. canal api sin referencia → `retenida` por `api_sin_referencia`, frena en Fraude.
   4. reintento con la misma clave que la 1 → HTTP 200, "reintento: misma clave, no se volvió a
      debitar"; el saldo de DEMO-1001 no cambia respecto de después de la 1.
   5. hacia DEMO-9001 → `retenida` por `destino_observado`, frena en Fraude.
   6. DEMO-2002 → DEMO-2002 → `rechazada` (`misma_cuenta`): el círculo se frena rojo en API Pagos;
      Fraude, Libro y Destino grises.
6. Abajo, "Últimas transferencias" lista cada una con estado, monto y motivos (el reintento no
   agrega fila nueva).
7. Al terminar la tanda, `document.body.dataset.tanda === "terminada"`.
8. Debajo de los saldos, "Reporte mensual de compliance" muestra el mes actual (por ejemplo
   "noviembre de 2026") y, con una base nueva, $ 80.000 y "1 transferencia posteada": solo la
   posteada suma; las retenidas, la rechazada y el reintento no.

Grabá la tanda completa como evidencia para el PR.
