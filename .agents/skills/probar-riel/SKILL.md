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
