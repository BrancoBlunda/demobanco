"""Cliente HTTP para que una API llame a otra dentro del mismo proceso.

Las llamadas son HTTP de verdad (método, path y status). En producción salen por la red hacia el
mismo servidor uvicorn; los tests pueden inyectar un transporte ASGI en `app.state`.
"""

import os

import httpx
from fastapi import Request

TIMEOUT_SEGUNDOS = 5.0


def url_interna(request: Request) -> str:
    configurada = os.environ.get("RIEL_URL_INTERNA")
    if configurada:
        return configurada.rstrip("/")
    host, puerto = request.scope["server"]
    if ":" in host:
        host = f"[{host}]"
    return f"http://{host}:{puerto}"


def cliente_interno(request: Request) -> httpx.AsyncClient:
    transporte = getattr(request.app.state, "transporte_interno", None)
    if transporte is not None:
        return httpx.AsyncClient(
            transport=transporte, base_url="http://riel.interno", timeout=TIMEOUT_SEGUNDOS
        )
    return httpx.AsyncClient(base_url=url_interna(request), timeout=TIMEOUT_SEGUNDOS)
