"""Base SQLite local. Sin base externa: un archivo (o memoria) dentro del mismo proceso."""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

ESQUEMA = """
CREATE TABLE IF NOT EXISTS cuentas (
    id TEXT PRIMARY KEY,
    titular TEXT NOT NULL,
    saldo INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS asientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clave_idempotencia TEXT NOT NULL UNIQUE,
    origen TEXT NOT NULL REFERENCES cuentas(id),
    destino TEXT NOT NULL REFERENCES cuentas(id),
    monto INTEGER NOT NULL,
    saldo_origen INTEGER NOT NULL,
    saldo_destino INTEGER NOT NULL,
    creado TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""


class Base:
    def __init__(self, ruta: str) -> None:
        self._conexion = sqlite3.connect(ruta, check_same_thread=False, isolation_level=None)
        self._conexion.row_factory = sqlite3.Row
        self._conexion.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()
        self._conexion.executescript(ESQUEMA)

    @contextmanager
    def transaccion(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conexion.execute("BEGIN IMMEDIATE")
            try:
                yield self._conexion
            except BaseException:
                self._conexion.execute("ROLLBACK")
                raise
            self._conexion.execute("COMMIT")

    def consultar(self, sql: str, parametros: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conexion.execute(sql, parametros).fetchall()

    def cerrar(self) -> None:
        self._conexion.close()
