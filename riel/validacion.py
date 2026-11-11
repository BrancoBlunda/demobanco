"""Validación de transferencias: motivos de rechazo que impiden pasar por fraude.

Regla de negocio: una transferencia con al menos un motivo queda `rechazada` (422), no pasa por
fraude, no mueve saldos y no consume la `clave_idempotencia`. `validar` devuelve todos los motivos
que apliquen:

- `origen_faltante` / `destino_faltante`: origen o destino ausente, vacío o que no es texto.
- `misma_cuenta`: origen y destino son la misma cuenta.
- `origen_inexistente` / `destino_inexistente`: la cuenta no existe en la base.
- `monto_no_entero`: el monto no es un entero (los booleanos no cuentan como entero).
- `monto_no_positivo`: el monto es menor o igual a 0.
- `monto_excede_maximo`: el monto es mayor a `MONTO_MAXIMO`.
- `moneda_no_soportada`: la moneda, si viene, es distinta de `MONEDA`.
- `canal_invalido`: el canal está fuera de `CANALES`.
- `referencia_invalida`: la referencia viene y no es texto.
- `sucursal_sin_referencia`: canal `sucursal` con referencia ausente, vacía o solo espacios.
- `clave_invalida`: la `clave_idempotencia` viene y no es texto.
"""

from typing import Any

from riel.config import CANALES, MONEDA, MONTO_MAXIMO
from riel.fraude import sin_referencia


def validar(entrada: dict[str, Any], cuentas: set[str]) -> list[str]:
    """Motivos de rechazo. Una transferencia rechazada no pasa por fraude."""
    motivos = []
    origen, destino = entrada.get("origen"), entrada.get("destino")
    tiene_origen = isinstance(origen, str) and bool(origen.strip())
    tiene_destino = isinstance(destino, str) and bool(destino.strip())
    if not tiene_origen:
        motivos.append("origen_faltante")
    if not tiene_destino:
        motivos.append("destino_faltante")
    if tiene_origen and tiene_destino and origen == destino:
        motivos.append("misma_cuenta")
    if tiene_origen and origen not in cuentas:
        motivos.append("origen_inexistente")
    if tiene_destino and destino != origen and destino not in cuentas:
        motivos.append("destino_inexistente")

    monto = entrada.get("monto")
    if not isinstance(monto, int) or isinstance(monto, bool):
        motivos.append("monto_no_entero")
    elif monto <= 0:
        motivos.append("monto_no_positivo")
    elif monto > MONTO_MAXIMO:
        motivos.append("monto_excede_maximo")

    if entrada.get("moneda", MONEDA) != MONEDA:
        motivos.append("moneda_no_soportada")

    canal = entrada.get("canal")
    referencia = entrada.get("referencia")
    if canal not in CANALES:
        motivos.append("canal_invalido")
    if referencia is not None and not isinstance(referencia, str):
        motivos.append("referencia_invalida")
    elif canal == "sucursal" and sin_referencia(referencia):
        motivos.append("sucursal_sin_referencia")

    clave = entrada.get("clave_idempotencia")
    if clave is not None and not isinstance(clave, str):
        motivos.append("clave_invalida")
    return motivos
