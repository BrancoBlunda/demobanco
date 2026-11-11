"""Bitácora de eventos de transferencias. Guarda solo los últimos 4 caracteres de cada cuenta."""

import json
import logging
import sqlite3

logger = logging.getLogger("riel.bitacora")


def ultimos4(cuenta: object) -> str:
    return cuenta[-4:] if isinstance(cuenta, str) else ""


def registrar(
    conexion: sqlite3.Connection,
    transferencia_id: str,
    evento: str,
    origen: object,
    destino: object,
    monto: int | None,
    motivos: list[str],
) -> None:
    origen4, destino4 = ultimos4(origen), ultimos4(destino)
    conexion.execute(
        "INSERT INTO bitacora (transferencia_id, evento, origen, destino, monto, motivos)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (transferencia_id, evento, origen4, destino4, monto, json.dumps(motivos)),
    )
    logger.info(
        "%s %s origen=%s destino=%s monto=%s motivos=%s",
        transferencia_id,
        evento,
        origen4,
        destino4,
        monto,
        ",".join(motivos),
    )
