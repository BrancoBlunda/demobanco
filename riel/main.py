from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="Riel",
        description="Banco ficticio de demostración. Los datos no son reales.",
    )

    @app.get("/v1/salud")
    def salud() -> dict:
        return {"estado": "ok", "servicio": "riel"}

    return app


app = create_app()
