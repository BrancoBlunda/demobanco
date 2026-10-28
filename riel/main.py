import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from riel import fraude, libro, listas
from riel.base import Base
from riel.semilla import sembrar_si_vacia


def create_app(ruta_base: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        base = Base(ruta_base or os.environ.get("RIEL_DB", "riel.db"))
        sembrar_si_vacia(base)
        app.state.base = base
        yield
        base.cerrar()

    app = FastAPI(
        title="Riel",
        description="Banco ficticio de demostración. Los datos no son reales.",
        lifespan=ciclo_de_vida,
    )

    @app.get("/v1/salud")
    def salud() -> dict:
        return {"estado": "ok", "servicio": "riel"}

    app.include_router(libro.router)
    app.include_router(fraude.router)
    app.include_router(listas.router)
    return app


app = create_app()
