"""API de cargas y consultas, con entrega del cliente Vue compilado."""

from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from fastapi import Depends, FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from openpyxl import load_workbook
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.db import rows, transaction
from app.security import (
    ADMIN,
    OPERATORS,
    current_user,
    require_roles,
    router as security_router,
)
from app.service import create_batch, schedule_again
from app.xml_reader import canonical_source
from app.explorer import router as explorer_router
from app.maintenance import router as maintenance_router
from app.analysis import router as analysis_router
from app.ui import DIST, router as ui_router

app = FastAPI(
    title="ProInXML",
    description="Integracion MEF con SQL Server y auditoria",
    version="1.0.0",
)
app.mount(
    "/assets",
    StaticFiles(directory=DIST / "assets", check_dir=False),
    name="frontend-assets",
)
app.include_router(security_router)
app.include_router(explorer_router)
app.include_router(explorer_router, prefix="/api", include_in_schema=False)
app.include_router(maintenance_router)
app.include_router(analysis_router)
app.include_router(ui_router)


@app.middleware("http")
async def response_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "no-store"
    return response


class UrlInput(BaseModel):
    url: str


class UrlListInput(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=1000)
    nombre: str = Field("Carga manual de URLs", min_length=1, max_length=260)


def validated_sources(urls):
    sources, errors = [], []
    for number, url in enumerate(urls, 1):
        try:
            sources.append(canonical_source(url))
        except ValueError as exc:
            errors.append({"linea": number, "detalle": str(exc)})
    if errors:
        raise HTTPException(
            422,
            {
                "mensaje": "Corrige los enlaces indicados antes de cargar.",
                "errores": errors[:25],
            },
        )
    return sources


def import_excel(file):
    data = file.file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "El Excel supera 10 MB.")
    book = None
    urls = []
    try:
        with ZipFile(BytesIO(data)) as archive:
            if sum(info.file_size for info in archive.infolist()) > 100 * 1024 * 1024:
                raise ValueError("El contenido descomprimido del Excel supera 100 MB.")
        book = load_workbook(BytesIO(data), read_only=True, data_only=True)
        sheet = book["XML"] if "XML" in book.sheetnames else book.active
        for number, values in enumerate(sheet.iter_rows(values_only=True), 1):
            if number > 50001:
                raise ValueError("Se admiten hasta 50.000 filas de Excel por lote.")
            value = values[0] if values else None
            if value is None or not str(value).strip():
                continue
            url = str(value).strip()
            if number == 1 and url.casefold() in (
                "url",
                "urls",
                "enlace",
                "enlaces",
                "xml",
            ):
                continue
            try:
                canonical_source(url)
            except ValueError as exc:
                raise ValueError(f"Fila {number}: {exc}") from exc
            urls.append(url)
    except Exception as exc:
        raise HTTPException(422, f"Excel no admitido: {exc}") from exc
    finally:
        if book is not None:
            book.close()
    if not urls:
        raise HTTPException(422, "El Excel no contiene enlaces en la primera columna.")
    return create_batch(file.filename or "URLs.xlsx", validated_sources(urls))


@app.post("/lotes", status_code=201)
async def new_batch(request: Request, user=Depends(require_roles(*OPERATORS))):
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        form = await request.form(max_files=1, max_fields=2)
        file = form.get("file")
        if not file or not hasattr(file, "file"):
            raise HTTPException(422, "Adjunta el Excel en el campo file.")
        # La tarea es corta; la insercion se ejecuta en un thread para no bloquear la API.
        from starlette.concurrency import run_in_threadpool

        return await run_in_threadpool(import_excel, file)
    try:
        body = UrlListInput.model_validate(await request.json())
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            422, "Indica urls como una lista de 1 a 1000 enlaces."
        ) from exc
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(
        create_batch, body.nombre, validated_sources(body.urls)
    )


@app.post("/lotes/urls", status_code=201)
def batch_urls(body: UrlListInput, user=Depends(require_roles(*OPERATORS))):
    return create_batch(body.nombre, validated_sources(body.urls))


@app.post("/lotes/url", status_code=201)
def batch_url(body: UrlInput, user=Depends(require_roles(*OPERATORS))):
    return create_batch("URL individual", validated_sources([body.url]))


@app.post("/lotes/excel", status_code=201)
def batch_excel(file: UploadFile, user=Depends(require_roles(*OPERATORS))):
    return import_excel(file)


@app.get("/lotes")
def recent_batches(
    limite: int = Query(10, ge=1, le=50),
    antes_de: int | None = Query(None, ge=1),
    user=Depends(current_user),
):
    with transaction() as con:
        return rows(
            con.execute(
                "SELECT TOP(?) l.Id,l.Nombre,l.CreadoUtc,l.CreadoPorUsuarioId,COUNT(t.Id) AS Total,"
                "SUM(CASE WHEN t.Estado IN ('Completado','CompletadoSinDatos','YaCargada') THEN 1 ELSE 0 END) AS Completados,"
                "SUM(CASE WHEN t.Estado='Fallido' THEN 1 ELSE 0 END) AS Fallidos "
                "FROM integracion.Lote l LEFT JOIN integracion.Trabajo t ON t.LoteId=l.Id "
                "WHERE (? IS NULL OR l.Id<?) GROUP BY l.Id,l.Nombre,l.CreadoUtc,l.CreadoPorUsuarioId ORDER BY l.Id DESC",
                limite,
                antes_de,
                antes_de,
            )
        )


@app.get("/salud")
def health():
    try:
        with transaction(actor="salud") as con:
            con.execute("SELECT 1").fetchone()
    except Exception as exc:
        raise HTTPException(503, "La base de datos no esta disponible.") from exc
    return {"estado": "ok"}


@app.get("/lotes/{lote_id}")
def batch_status(lote_id: int, user=Depends(current_user)):
    with transaction() as con:
        lot = rows(
            con.execute(
                "SELECT l.*,u.NombreUsuario AS CreadoPor FROM integracion.Lote l "
                "JOIN seguridad.Usuario u ON u.Id=l.CreadoPorUsuarioId WHERE l.Id=?",
                lote_id,
            )
        )
        if not lot:
            raise HTTPException(404, "Lote no encontrado.")
        summary = rows(
            con.execute(
                "SELECT Estado,COUNT(*) AS Cantidad FROM integracion.Trabajo WHERE LoteId=? GROUP BY Estado",
                lote_id,
            )
        )
        count = con.execute(
            "SELECT COALESCE(SUM(CONVERT(bigint,d.CantidadRegistros)),0) FROM integracion.Trabajo t "
            "JOIN integracion.Documento d ON d.Id=t.DocumentoId WHERE t.LoteId=? "
            "AND t.Estado IN ('Completado','CompletadoSinDatos','YaCargada')",
            lote_id,
        ).fetchone()[0]
        average = con.execute(
            "SELECT AVG(CONVERT(float,DATEDIFF_BIG(millisecond,a.InicioUtc,a.FinUtc)))/1000 "
            "FROM integracion.Intento a JOIN integracion.Trabajo t ON t.Id=a.TrabajoId "
            "WHERE t.LoteId=? AND a.Estado='Completado'",
            lote_id,
        ).fetchone()[0]
    pending = sum(
        r["Cantidad"] for r in summary if r["Estado"] in ("Pendiente", "EnCurso")
    )
    return {
        "lote": lot[0],
        "resumen": summary,
        "registros": count,
        "eta_segundos": round(pending * average / settings.worker_concurrency)
        if average and pending
        else None,
    }


@app.get("/lotes/{lote_id}/trabajos")
def batch_jobs(
    lote_id: int,
    despues_de: int = Query(0, ge=0),
    limite: int = Query(50, ge=1, le=200),
    estado: str | None = None,
    user=Depends(current_user),
):
    estado = estado or None
    with transaction() as con:
        return rows(
            con.execute(
                "SELECT TOP(?) t.Id,t.LoteId,t.ConsultaId,t.DocumentoId,t.Estado,t.Intentos,t.MaxIntentos,t.ProximoIntentoUtc,"
                "t.UltimoError,t.CreadoUtc,t.FinalizadoUtc,c.Url,c.AnoEje,c.NivelGobierno,c.SecEjec,"
                "CASE WHEN t.Estado IN ('Completado','CompletadoSinDatos','YaCargada') THEN d.CantidadRegistros END AS CantidadRegistros,"
                "(SELECT TOP(1) a.HttpStatus FROM integracion.Intento a WHERE a.TrabajoId=t.Id ORDER BY a.Numero DESC) AS HttpStatus "
                "FROM integracion.Trabajo t JOIN integracion.Consulta c ON c.Id=t.ConsultaId "
                "LEFT JOIN integracion.Documento d ON d.Id=t.DocumentoId WHERE t.LoteId=? AND t.Id>? "
                "AND (? IS NULL OR t.Estado=?) ORDER BY t.Id",
                limite,
                lote_id,
                despues_de,
                estado,
                estado,
            )
        )


@app.post("/trabajos/{trabajo_id}/reintentar")
def retry_job(trabajo_id: int, user=Depends(require_roles(*OPERATORS))):
    return reschedule(trabajo_id)


@app.post("/trabajos/{trabajo_id}/forzar-revision")
def force_job(trabajo_id: int, user=Depends(require_roles(ADMIN))):
    return reschedule(trabajo_id, force=True)


def reschedule(job_id, force=False):
    try:
        return schedule_again(job_id, force=force)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/trabajos/{trabajo_id}/gastos")
def job_expenses(
    trabajo_id: int,
    despues_de: int = Query(0, ge=0),
    limite: int = Query(50, ge=1, le=200),
    user=Depends(current_user),
):
    with transaction() as con:
        job = con.execute(
            "SELECT DocumentoId,Estado FROM integracion.Trabajo WHERE Id=?", trabajo_id
        ).fetchone()
        if not job:
            raise HTTPException(404, "Trabajo no encontrado.")
        if job[1] not in ("Completado", "CompletadoSinDatos", "YaCargada"):
            raise HTTPException(409, "La carga todavia no se ha completado.")
        result = rows(
            con.execute(
                "SELECT TOP(?) * FROM datos.Gasto WHERE DocumentoId=? AND Id>? ORDER BY Id",
                limite,
                job[0],
                despues_de,
            )
        )
    return jsonable_encoder(result, custom_encoder={Decimal: str})


@app.get("/trabajos")
def jobs(
    lote_id: int | None = None,
    despues_de: int = Query(0, ge=0),
    limite: int = Query(50, ge=1, le=200),
    user=Depends(current_user),
):
    with transaction() as con:
        return rows(
            con.execute(
                "SELECT TOP(?) * FROM integracion.Trabajo WHERE Id>? AND (? IS NULL OR LoteId=?) ORDER BY Id",
                limite,
                despues_de,
                lote_id,
                lote_id,
            )
        )


@app.get("/gastos", include_in_schema=False)
def legacy_expenses(
    ano: int | None = None,
    anio: int | None = None,
    sec_ejec: int | None = None,
    despues_de: int = Query(0, ge=0),
    limite: int = Query(50, ge=1, le=200),
    user=Depends(current_user),
):
    with transaction() as con:
        result = rows(
            con.execute(
                "SELECT TOP(?) * FROM datos.GastoActual WHERE Id>? "
                "AND (? IS NULL OR AnoEje=?) AND (? IS NULL OR SecEjec=?) ORDER BY Id",
                limite,
                despues_de,
                ano if ano is not None else anio,
                ano if ano is not None else anio,
                sec_ejec,
                sec_ejec,
            )
        )
    return jsonable_encoder(result, custom_encoder={Decimal: str})
