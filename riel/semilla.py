"""Cuentas DEMO con titulares ficticios. No son personas ni cuentas reales."""

from riel.base import Base

CUENTAS_SEMILLA: tuple[tuple[str, str, int], ...] = (
    ("DEMO-1001", "Ana Ferreiro", 2_000_000),
    ("DEMO-1002", "Luis Pereyra", 800_000),
    ("DEMO-1003", "Estudio Norte", 3_500_000),
    ("DEMO-2001", "Proveedor Sur", 400_000),
    ("DEMO-2002", "Mónica Alegre", 150_000),
    ("DEMO-9001", "Cuenta observada", 100_000),
)


def sembrar_si_vacia(base: Base) -> bool:
    with base.transaccion() as conexion:
        (cantidad,) = conexion.execute("SELECT COUNT(*) FROM cuentas").fetchone()
        if cantidad:
            return False
        conexion.executemany(
            "INSERT INTO cuentas (id, titular, saldo) VALUES (?, ?, ?)", CUENTAS_SEMILLA
        )
    return True
