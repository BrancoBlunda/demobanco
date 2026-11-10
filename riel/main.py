import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from riel import compliance, fraude, libro, listas, pagos
from riel.base import Base
from riel.semilla import sembrar_si_vacia

PAGINA = Path(__file__).parent / "static" / "index.html"


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

    @app.get("/", include_in_schema=False)
    def pagina() -> FileResponse:
        return FileResponse(PAGINA)

    app.include_router(libro.router)
    app.include_router(fraude.router)
    app.include_router(listas.router)
    app.include_router(pagos.router)
    app.include_router(compliance.router)
    return app


app = create_app()
