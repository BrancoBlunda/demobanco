"""Validación de transferencias: reglas de rechazo previas a fraude.

`validar` produce la lista de motivos de rechazo de una transferencia:

- origen o destino faltantes (`origen_faltante`, `destino_faltante`) o inexistentes
  (`origen_inexistente`, `destino_inexistente`);
- misma cuenta en origen y destino (`misma_cuenta`);
- monto no entero (`monto_no_entero`), no positivo (`monto_no_positivo`) o mayor a
  `MONTO_MAXIMO` (`monto_excede_maximo`);
- moneda distinta de `MONEDA` (`moneda_no_soportada`);
- canal fuera de `CANALES` (`canal_invalido`);
- referencia que no es string (`referencia_invalida`);
- canal `sucursal` sin referencia (`sucursal_sin_referencia`);
- clave de idempotencia que no es string (`clave_invalida`).

Una transferencia con motivos se rechaza (estado `rechazada`) y no pasa por fraude.
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
