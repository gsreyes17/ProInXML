"""Consultas de solo lectura para auditoria, XML original y entidades relacionadas."""

import gzip
import json
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder

from app.infrastructure.db import rows, transaction
from app.domain.model_schema import registry
from app.api.security import ADMIN, current_user, require_roles
from app.domain.xml_reader import FIELDS

router = APIRouter(tags=["Exploradores"], dependencies=[Depends(current_user)])
MODEL = {item["tabla"]: item for item in registry()}


def encode(value):
    return jsonable_encoder(value, custom_encoder={Decimal: str})


def page(con, table, columns, filters, params, limit, cursor, *, descending=False):
    where = " AND ".join(filters) or "1=1"
    total = con.execute(
        f"SELECT COUNT_BIG(*) FROM {table} WHERE {where}", *params
    ).fetchone()[0]
    comparison, direction = ("<", "DESC") if descending else (">", "ASC")
    page_where = where + (f" AND Id{comparison}?" if cursor is not None else "")
    page_params = [*params, cursor] if cursor is not None else list(params)
    result = rows(
        con.execute(
            f"SELECT TOP(?) {columns} FROM {table} WHERE {page_where} ORDER BY Id {direction}",
            limit + 1,
            *page_params,
        )
    )
    return encode(
        {
            "registros": result[:limit],
            "total": total,
            "siguiente_cursor": result[limit - 1]["Id"]
            if len(result) > limit
            else None,
        }
    )


@router.get("/auditoria/tablas", dependencies=[Depends(require_roles(ADMIN))])
def audit_tables():
    with transaction() as con:
        return [
            row[0]
            for row in con.execute(
                "SELECT s.name+'.'+t.name FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id "
                "WHERE s.name IN ('integracion','staging','modelo','seguridad') ORDER BY s.name,t.name"
            )
        ]


@router.get("/auditoria", dependencies=[Depends(require_roles(ADMIN))])
def audit_log(
    tabla: str | None = None,
    operacion: Literal["I", "U", "D"] | None = None,
    actor: str | None = None,
    rol: str | None = None,
    registro_id: int | None = Query(None, ge=1),
    desde: datetime | None = None,
    hasta: datetime | None = None,
    antes_de: int | None = Query(None, ge=1),
    limite: int = Query(25, ge=1, le=100),
):
    filters, params = [], []
    for field, value in [
        ("Tabla", tabla),
        ("Operacion", operacion),
        ("RegistroId", registro_id),
        ("Rol", rol),
    ]:
        if value is not None and value != "":
            filters.append(f"{field}=?")
            params.append(value)
    if actor:
        filters.append("CHARINDEX(?,Actor)>0")
        params.append(actor)
    for value, comparison in [(desde, ">="), (hasta, "<")]:
        if value is not None:
            if value.tzinfo is None:
                raise HTTPException(422, "Las fechas deben incluir zona horaria.")
            filters.append(f"FechaUTC{comparison}?")
            params.append(value.astimezone(UTC).replace(tzinfo=None))
    if desde and hasta and desde >= hasta:
        raise HTTPException(422, "La fecha inicial debe ser anterior a la final.")
    with transaction() as con:
        return page(
            con,
            "auditoria.Cambio",
            "Id,Tabla,RegistroId,Operacion,FechaUTC,UsuarioId,Actor,Rol,LoginSQL,Correlacion",
            filters,
            params,
            limite,
            antes_de,
            descending=True,
        )


AUDIT_LOADS = """(SELECT a.*,d.CantidadRegistros,d.EsValido,i.HTTPStatus,
 COALESCE(i.URLSolicitada,c.URL) AS URL,
 CONVERT(bit,CASE WHEN d.Id IS NULL THEN 0 ELSE 1 END) AS DocumentoDisponible,
 CASE WHEN d.Id IS NULL THEN N'Documento eliminado'
      WHEN d.EsValido=0 THEN N'Rechazado'
      WHEN d.CantidadRegistros=0 THEN N'Sin datos'
      ELSE N'Con datos' END AS Resultado
 FROM auditoria.CargaDocumento a
 LEFT JOIN integracion.Documento d ON d.Id=a.DocumentoId
 LEFT JOIN integracion.Consulta c ON c.Id=d.ConsultaId
 LEFT JOIN integracion.Intento i ON i.Id=d.IntentoId) cargas"""


@router.get("/auditoria/cargas", dependencies=[Depends(require_roles(ADMIN))])
def document_audit(
    documento_id: int | None = Query(None, ge=1),
    resultado: Literal["sin_datos", "con_datos", "rechazado", "eliminado"]
    | None = None,
    antes_de: int | None = Query(None, ge=1),
    limite: int = Query(25, ge=1, le=100),
):
    filters, params = [], []
    if documento_id:
        filters.append("DocumentoId=?")
        params.append(documento_id)
    if resultado:
        filters.append("Resultado=?")
        params.append(
            {
                "sin_datos": "Sin datos",
                "con_datos": "Con datos",
                "rechazado": "Rechazado",
                "eliminado": "Documento eliminado",
            }[resultado]
        )
    with transaction() as con:
        return page(
            con,
            AUDIT_LOADS,
            "*",
            filters,
            params,
            limite,
            antes_de,
            descending=True,
        )


@router.get("/auditoria/accesos", dependencies=[Depends(require_roles(ADMIN))])
def access_log(
    antes_de: int | None = Query(None, ge=1), limite: int = Query(25, ge=1, le=100)
):
    with transaction() as con:
        return page(
            con,
            "seguridad.EventoAcceso",
            "*",
            [],
            [],
            limite,
            antes_de,
            descending=True,
        )


@router.get("/auditoria/{cambio_id}", dependencies=[Depends(require_roles(ADMIN))])
def audit_detail(cambio_id: int):
    with transaction() as con:
        result = rows(
            con.execute("SELECT * FROM auditoria.Cambio WHERE Id=?", cambio_id)
        )
    if not result:
        raise HTTPException(404, "Evento de auditoria no encontrado.")
    detail = result[0]
    for field in ("Antes", "Despues"):
        detail[field] = json.loads(detail[field]) if detail[field] is not None else None
    return detail


@router.get("/datos/xml")
def xml_data(
    ano: int | None = Query(None, ge=1900, le=2100),
    anio: int | None = Query(None, ge=1900, le=2100),
    sec_ejec: int | None = Query(None, ge=1),
    proyecto: str | None = None,
    registro_id: int | None = Query(None, ge=1),
    documento_id: int | None = Query(None, ge=1),
    vigentes: bool = True,
    solo_xml: bool = True,
    despues_de: int | None = Query(None, ge=0),
    limite: int = Query(25, ge=1, le=100),
):
    filters, params = [], []
    for field, value in [
        ("AnoEje", ano if ano is not None else anio),
        ("SecEjec", sec_ejec),
        ("IdProyecto", proyecto),
        ("Id", registro_id),
        ("DocumentoId", documento_id),
    ]:
        if value is not None and value != "":
            filters.append(f"[{field}]=?")
            params.append(value)
    with transaction() as con:
        result = page(
            con,
            "staging.GastoActual" if vigentes else "staging.Gasto",
            "*",
            filters,
            params,
            limite,
            despues_de,
        )
    result["columnas"] = ["Id", "DocumentoId", "Ordinal", *FIELDS]
    if solo_xml:
        result["identificadores"] = [r["Id"] for r in result["registros"]]
        result["registros"] = [{f: r[f] for f in FIELDS} for r in result["registros"]]
        result["columnas"] = list(FIELDS)
    return result


@router.get("/datos/xml/{registro_id}")
def xml_detail(registro_id: int):
    with transaction() as con:
        found = rows(con.execute("SELECT * FROM staging.Gasto WHERE Id=?", registro_id))
        if not found:
            raise HTTPException(404, "Registro XML no encontrado.")
        raw = found[0]
        trace = rows(
            con.execute(
                "SELECT d.Id AS DocumentoId,d.ConsultaId,d.IntentoId,d.Sha256,d.EsValido,d.CantidadRegistros,"
                "d.ErrorValidacion,d.CreadoUTC AS DocumentoCreadoUTC,c.URL,"
                "CASE WHEN c.DocumentoActualId=d.Id THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END AS Vigente "
                "FROM integracion.Documento d JOIN integracion.Consulta c ON c.Id=d.ConsultaId WHERE d.Id=?",
                raw["DocumentoId"],
            )
        )[0]
    return encode(
        {
            "registro": {f: raw[f] for f in FIELDS},
            "trazabilidad": {
                "Id": raw["Id"],
                "Ordinal": raw["Ordinal"],
                **trace,
            },
        }
    )


@router.get("/reportes/ejecucion")
def execution_report(
    trabajo_id: int | None = Query(None, ge=1),
    lote_id: int | None = Query(None, ge=1),
    http_status: int | None = Query(None, ge=100, le=599),
    estado: str | None = None,
    solo_fallos: bool = False,
    antes_de: int | None = Query(None, ge=1),
    limite: int = Query(25, ge=1, le=100),
):
    filters, params = [], []
    for column, value in [
        ("TrabajoId", trabajo_id),
        ("LoteId", lote_id),
        ("HTTPStatus", http_status),
        ("Estado", estado),
    ]:
        if value is not None and value != "":
            filters.append(f"{column}=?")
            params.append(value)
    if solo_fallos:
        filters.append(
            "(Estado IN ('Error','Interrumpido') OR HTTPStatus>=400 OR Error IS NOT NULL)"
        )
    with transaction() as con:
        return page(
            con,
            "reportes.EjecucionServicio",
            "*",
            filters,
            params,
            limite,
            antes_de,
            descending=True,
        )


@router.get("/observaciones")
def observations(
    documento_id: int | None = Query(None, ge=1),
    campo: str | None = None,
    codigo: str | None = None,
    severidad: Literal["Info", "Advertencia", "Error"] | None = None,
    antes_de: int | None = Query(None, ge=1),
    limite: int = Query(25, ge=1, le=100),
):
    filters, params = [], []
    for column, value in [
        ("DocumentoId", documento_id),
        ("Campo", campo),
        ("CodigoObservacion", codigo),
        ("Severidad", severidad),
    ]:
        if value is not None and value != "":
            filters.append(f"{column}=?")
            params.append(value)
    with transaction() as con:
        return page(
            con,
            "integracion.ObservacionDato",
            "*",
            filters,
            params,
            limite,
            antes_de,
            descending=True,
        )


DOCUMENTS = """(SELECT d.Id,d.ConsultaId,d.Sha256,d.EsValido,d.CantidadRegistros,d.ErrorValidacion,
 d.ContentType,d.CreadoUTC,c.URL,c.AnoEje,c.SecEjec,a.HTTPStatus,
 CASE WHEN c.DocumentoActualId=d.Id THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END AS Vigente,
 CASE WHEN a.HTTPStatus<>200 THEN N'Error HTTP' WHEN d.EsValido=0 THEN N'Rechazado'
      ELSE N'Valido' END AS EstadoDocumento,
 (SELECT COUNT(*) FROM integracion.ObservacionDato o WHERE o.DocumentoId=d.Id) AS Observaciones,
 (SELECT COUNT(*) FROM integracion.ObservacionDato o WHERE o.DocumentoId=d.Id AND o.Severidad='Error') AS ErroresCalidad,
 (SELECT COUNT(*) FROM staging.Gasto g WHERE g.DocumentoId=d.Id) AS RegistrosDetalle
 FROM integracion.Documento d JOIN integracion.Consulta c ON c.Id=d.ConsultaId
 JOIN integracion.Intento a ON a.Id=d.IntentoId) documentos"""


@router.get("/documentos")
def documents(
    documento_id: int | None = Query(None, ge=1),
    ano: int | None = Query(None, ge=1900, le=2100),
    sec_ejec: int | None = Query(None, ge=1),
    calidad: Literal["validos", "rechazados", "con_observaciones", "errores_http"]
    | None = None,
    http_status: int | None = Query(None, ge=100, le=599),
    antes_de: int | None = Query(None, ge=1),
    limite: int = Query(25, ge=1, le=100),
):
    filters, params = [], []
    for column, value in [
        ("Id", documento_id),
        ("AnoEje", ano),
        ("SecEjec", sec_ejec),
        ("HTTPStatus", http_status),
    ]:
        if value is not None:
            filters.append(f"{column}=?")
            params.append(value)
    conditions = {
        "validos": "EsValido=1",
        "rechazados": "EsValido=0 AND HTTPStatus=200",
        "con_observaciones": "Observaciones>0",
        "errores_http": "HTTPStatus<>200",
    }
    if calidad:
        filters.append(conditions[calidad])
    with transaction() as con:
        return page(
            con, DOCUMENTS, "*", filters, params, limite, antes_de, descending=True
        )


@router.get("/documentos/{documento_id}")
def document_detail(documento_id: int, ordinal: int | None = Query(None, ge=1)):
    with transaction() as con:
        found = rows(con.execute(f"SELECT * FROM {DOCUMENTS} WHERE Id=?", documento_id))
        if not found:
            raise HTTPException(404, "Documento no encontrado o eliminado.")
        payload = con.execute(
            "SELECT Respuesta FROM integracion.Documento WHERE Id=?", documento_id
        ).fetchone()[0]
        record = (
            rows(
                con.execute(
                    "SELECT * FROM staging.Gasto WHERE DocumentoId=? AND Ordinal=?",
                    documento_id,
                    ordinal,
                )
            )
            if ordinal
            else []
        )
    # Vista previa limitada, incluso si el original comprimido es mucho mayor.
    with gzip.GzipFile(fileobj=BytesIO(payload)) as original:
        sample = original.read(65537)
    return encode(
        {
            "documento": found[0],
            "registro": record[0] if record else None,
            "original": {
                "texto": sample[:65536].decode("utf-8", errors="replace"),
                "truncado": len(sample) > 65536,
            },
        }
    )


@router.get("/modelo/tablas")
@router.get("/modelo/estructura")
def model_structure():
    return {
        "tablas": list(MODEL.values()),
        "campos_xml": list(FIELDS),
        "nota": "Claves de contexto propuestas a partir de los codigos recibidos; no son catalogos descriptivos oficiales.",
    }


@router.get("/modelo/tablas/{tabla}")
@router.get("/modelo/{tabla}")
def model_data(
    tabla: str,
    registro_id: int | None = Query(None, ge=1),
    buscar: str | None = Query(None, max_length=100),
    despues_de: int | None = Query(None, ge=0),
    limite: int = Query(25, ge=1, le=100),
):
    definition = MODEL.get(tabla)
    if definition is None:
        raise HTTPException(404, "Tabla no disponible en el explorador.")
    filters, params = [], []
    if registro_id is not None:
        filters.append("Id=?")
        params.append(registro_id)
    if buscar:
        filters.append(
            "("
            + " OR ".join(
                f"CHARINDEX(?,CONVERT(nvarchar(160),[{column}]))>0"
                for column in definition["columnas"]
            )
            + ")"
        )
        params.extend([buscar] * len(definition["columnas"]))
    # Identificadores elegidos exclusivamente del registro fijo, nunca del usuario.
    with transaction() as con:
        result = page(
            con,
            f"[modelo].[{definition['tabla']}]",
            ",".join(f"[{c}]" for c in definition["columnas"]),
            filters,
            params,
            limite,
            despues_de,
        )
    return dict(result, **definition)
