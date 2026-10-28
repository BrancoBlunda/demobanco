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
