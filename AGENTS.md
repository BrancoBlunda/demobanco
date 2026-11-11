# AGENTS.md

Guía para quien trabaje en Riel (personas o agentes). Riel es un banco ficticio de demostración:
los datos no son reales y no es un banco real.

## Estructura

```
riel/            paquete de la app (un solo proceso FastAPI)
  main.py        create_app(): monta las APIs y la página estática
  base.py        SQLite local (archivo RIEL_DB, por defecto riel.db)
  semilla.py     cuentas DEMO que se cargan al arrancar si la base está vacía
  libro.py       GET /v1/cuentas y POST /v1/libro/asientos (interna)
  config.py      constantes de negocio (UMBRAL_MONTO_ALTO, MONTO_MAXIMO, MONEDA, CANALES, ZONA_HORARIA)
  fraude.py      reglas de fraude y POST /v1/fraude/evaluar (interna); consulta listas por HTTP
  listas.py      GET /v1/listas/observadas (interna, exige Bearer LISTAS_API_TOKEN)
  interno.py     cliente HTTP entre APIs del mismo proceso
  pagos.py       POST /v1/pagos/transferencias, GET .../{id}/traza, GET /v1/transferencias
  validacion.py  reglas de rechazo de transferencias (validar: motivos de rechazo, sin pasar por fraude)
  bitacora.py    bitácora de eventos (solo últimos 4 caracteres de cada cuenta)
  compliance.py  GET /v1/compliance/reporte-mensual: total posteado del mes
  static/        index.html: la pantalla (HTML, CSS y JS sin build), servida en GET /
tests/           tests de pytest
.agents/skills/  skills del repo (probar-riel: cómo probar de punta a punta)
```

Un solo proceso Python. FastAPI sirve las APIs de pagos, fraude, libro y listas, y una página
estática. Aunque vivan en el mismo proceso, las llamadas entre APIs son HTTP de verdad (método,
path y status), porque la pantalla las muestra. Sin login, sin base externa, sin microservicios
separados, sin machine learning.

Llamadas internas: `interno.cliente_interno(request)` apunta al mismo servidor uvicorn usando la
dirección local de la conexión (`scope["server"]`), o a `RIEL_URL_INTERNA` si está definida. Los
tests inyectan `app.state.transporte_interno = httpx.ASGITransport(app)`; `tests/test_http_real.py`
levanta uvicorn de verdad para cubrir la red.

## Comandos

```bash
pip install -e ".[dev]"
uvicorn riel.main:app --env-file .env --port 8000
ruff check . && ruff format --check .   # lint, antes de cada PR
pytest -q
```

## Reglas de negocio

Montos en pesos enteros.

Fraude (cualquier motivo retiene la transferencia: no se debita ni se acredita, estado `retenida`):

- Monto mayor o igual a `UMBRAL_MONTO_ALTO` (500000): motivo `monto_alto`. El umbral vive solo en
  `riel/config.py` y no se cambia.
- Canal `api` sin referencia (ausente, vacía o solo espacios): motivo `api_sin_referencia`.
- Fraude evalúa todas las reglas y devuelve todos los motivos que apliquen.
- Destino presente en la API de listas: motivo `destino_observado`.
- Si la API de listas responde 401 (token faltante o distinto): motivo `listas_no_disponible`.

Sin motivos: se debita el origen, se acredita el destino y el estado queda `posteada`.

Idempotencia: la misma `clave_idempotencia` produce un solo asiento. Un reintento devuelve la
operación ya hecha y no debita de nuevo.

Rechazos, sin pasar por fraude (estado `rechazada`): sin origen, sin destino, misma cuenta, monto
no entero, monto menor o igual a 0, monto mayor a 50000000, moneda distinta de `ARS`, canal fuera
de `home_banking`, `api` y `sucursal`, y `sucursal` sin referencia.

Libro: un asiento debita el origen y acredita el destino en una sola transacción. Si el origen no
tiene saldo suficiente, responde 409 `saldo_insuficiente` y no mueve saldos (guarda de demo: evita
saldos negativos).

Semilla: al arrancar, si la base está vacía, se cargan las cuentas DEMO-1001, DEMO-1002,
DEMO-1003, DEMO-2001, DEMO-2002 y DEMO-9001 (titulares ficticios).

Pagos responde 201 `posteada`, 202 `retenida`, 422 `rechazada` y 200 en un reintento
(`reintento: true`). Rechazos adicionales: `origen_inexistente`, `destino_inexistente`,
`referencia_invalida`, `clave_invalida` y, desde el libro, `saldo_insuficiente`. Un rechazo no
consume la `clave_idempotencia`. Si fraude no responde, la transferencia se retiene con
`fraude_no_disponible`.

Traza: saltos en orden `origen`, `api_pagos`, `fraude`, `libro`, `destino`. Cada salto tiene
`nodo`, `estado` (`ok`, `retenida`, `rechazada`, `omitido`), `metodo`, `path`, `status` y
`recorte`. Si fraude retiene, `libro` y `destino` quedan `omitido`.

Bitácora: guarda solo los últimos 4 caracteres de origen y de destino.

Reporte mensual de compliance (`GET /v1/compliance/reporte-mensual?mes=YYYY-MM`, por defecto el
mes actual): suma solo las transferencias `posteada` cuya fecha de creación cae en el mes calendario,
todos los días de lunes a domingo, en hora de `ZONA_HORARIA` (Argentina). Las `procesando`
(pendientes), `retenida` y `rechazada` no entran; un reintento no suma porque no crea fila. Devuelve
`mes`, `desde`, `hasta`, `moneda`, `cantidad` y `total`. Un `mes` inválido responde 422
`mes_invalido`.

Listas: exige `Authorization: Bearer <LISTAS_API_TOKEN>`, leído del entorno. Nunca escribas el
token en el código, en el README ni en los tests (los tests usan un token de fixture).

## Secretos

Cero secretos en el repo. `.env.example` solo nombra `LISTAS_API_TOKEN` con el valor vacío. `.env`
está en `.gitignore`.

## Commits y PRs

Conventional Commits en español, en imperativo y chicos:

```
feat(fraude): retener por monto_alto
fix(pagos): no debitar en reintentos
test(libro): cubrir idempotencia de asientos
docs: explicar cómo correr la app
chore: configurar ruff
```

Tipos: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `ci`. El scope es el módulo (`pagos`,
`fraude`, `libro`, `listas`, `ui`). Un PR por slice que funcione, con lint y tests en verde. Si el PR
toca la pantalla, corré el skill `probar-riel` y adjuntá una grabación de la animación.
