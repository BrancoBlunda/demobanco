# Riel

Riel es un **banco ficticio** de demostración. Una sola pantalla muestra cómo viaja una
transferencia entre APIs y cómo se frena si fraude la retiene.

> Los datos son de demostración. **No es un banco real.** No hay login, no hay home banking de
> verdad y ninguna cuenta existe fuera de esta app.

## Requisitos

- Python 3.10 o superior.

## Instalar

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

`.env` es local y no se versiona. Completá `LISTAS_API_TOKEN` con un valor que elijas vos. La API
de listas exige ese token y fraude lo envía; si falta, listas responde 401 y toda transferencia
queda retenida con motivo `listas_no_disponible`.

## Correr

```bash
source .venv/bin/activate
uvicorn riel.main:app --env-file .env --port 8000
```

Los datos viven en un archivo SQLite local (`riel.db`, o el que indique `RIEL_DB`). Al arrancar,
si la base está vacía, se cargan seis cuentas DEMO con titulares ficticios. Para volver a la
semilla, frená la app y borrá `riel.db`.

Abrí `http://127.0.0.1:8000/` para ver la pantalla: elegí origen, destino, monto, canal y
referencia y tocá **Transferir**, o tocá **Simular tanda** para ver seis transferencias de ejemplo
(posteada, retenidas, reintento y rechazada).

Chequeo de salud:

```bash
curl http://127.0.0.1:8000/v1/salud
```

Transferencia de ejemplo:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/pagos/transferencias \
  -H 'Content-Type: application/json' \
  -d '{"origen":"DEMO-1001","destino":"DEMO-2001","monto":80000,"canal":"home_banking",
       "referencia":"Factura 0001","clave_idempotencia":"ejemplo-1"}'
```

La documentación interactiva de las APIs está en `http://127.0.0.1:8000/docs`.

## Probar

```bash
source .venv/bin/activate
ruff check . && ruff format --check .
pytest -q
```

Los tests no necesitan `.env`: usan su propio token de fixture.

## Más información

- [AGENTS.md](AGENTS.md): estructura, reglas de negocio y convención de commits.
- [.agents/skills/probar-riel/SKILL.md](.agents/skills/probar-riel/SKILL.md): cómo probar la app de
  punta a punta.
