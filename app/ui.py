"""Entrega del frontend Vue compilado; la API no necesita un servidor Node en ejecución."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
SCREENS = {"login", "seguimiento", "auditoria", "datos", "modelo", "ejecucion", "observaciones", "usuarios", "mantenimiento", "metricas"}
router = APIRouter(include_in_schema=False)


def index():
    path = DIST / "index.html"
    if not path.is_file():
        raise HTTPException(503, "Falta compilar el frontend. Ejecuta pnpm --dir frontend build.")
    return FileResponse(path, media_type="text/html")


@router.get("/")
def interface():
    return index()


@router.get("/ui/{pantalla}")
def screen(pantalla: str):
    if pantalla not in SCREENS:
        raise HTTPException(404, "Pantalla no encontrada.")
    return index()
