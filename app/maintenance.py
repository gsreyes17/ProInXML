"""Limpieza explicita del laboratorio; conserva cuentas, configuracion y auditoria."""

import hashlib
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app.db import rows, transaction
from app.locks import integration_lock
from app.model_schema import ENTITIES, FACT_COLUMNS
from app.normalizer import acquire_document_lock
from app.security import ADMIN, require_roles

router = APIRouter(
    prefix="/mantenimiento",
    tags=["Mantenimiento"],
    dependencies=[Depends(require_roles(ADMIN))],
)


class Scope(BaseModel):
    alcance: Literal["documento", "todo"]
    documento_id: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def valid_scope(self):
        if (self.alcance == "documento") != (self.documento_id is not None):
            raise ValueError("Indica documento_id solo para eliminar un documento.")
        return self


class Deletion(Scope):
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmacion: str = Field(max_length=100)
    motivo: str = Field(min_length=5, max_length=500)


def confirmation(scope):
    return (
        f"ELIMINAR DOCUMENTO {scope.documento_id}"
        if scope.alcance == "documento"
        else "VACIAR CARGAS"
    )


def snapshot(con, scope):
    document = None
    if scope.documento_id is not None:
        found = rows(
            con.execute(
                "SELECT d.Id,d.ConsultaId,d.Sha256,d.EsValido,d.CantidadRegistros,d.ErrorValidacion,c.Url "
                "FROM integracion.Documento d JOIN integracion.Consulta c ON c.Id=d.ConsultaId WHERE d.Id=?",
                scope.documento_id,
            )
        )
        if not found:
            raise HTTPException(404, "Documento no encontrado o ya eliminado.")
        document = found[0]
    filters = " WHERE DocumentoId=?" if document else ""
    params = [scope.documento_id] if document else []
    counters = {}
    signatures = {}
    for label, table, where, values in [
        (
            "documentos",
            "integracion.Documento",
            " WHERE Id=?" if document else "",
            params,
        ),
        ("registros_xml", "datos.Gasto", filters, params),
        ("observaciones", "integracion.ObservacionDato", filters, params),
        ("trabajos", "integracion.Trabajo", filters, params),
        ("intentos", "integracion.Intento", filters, params),
        ("lotes", "integracion.Lote", " WHERE 1=0" if document else "", []),
        ("consultas", "integracion.Consulta", " WHERE 1=0" if document else "", []),
        (
            "registros_modelo",
            "modelo.Gasto",
            " WHERE Id IN(SELECT Id FROM datos.Gasto WHERE DocumentoId=?)"
            if document
            else "",
            params,
        ),
    ]:
        count, last = con.execute(
            f"SELECT COUNT_BIG(*),COALESCE(MAX(Id),0) FROM {table}{where}", *values
        ).fetchone()
        counters[label] = count
        signatures[label] = [count, last]
    # Las dimensiones se podan globalmente solo si ya no tienen referencias.
    dimensions = {}
    for table in ENTITIES:
        dimensions[table] = list(
            con.execute(
                f"SELECT COUNT_BIG(*),COALESCE(MAX(Id),0) FROM modelo.[{table}]"
            ).fetchone()
        )
    counters["entidades_modelo"] = sum(value[0] for value in dimensions.values())
    running = con.execute(
        "SELECT COUNT(*) FROM integracion.Trabajo WHERE Estado='EnCurso'"
    ).fetchone()[0]
    value = {
        "alcance": scope.alcance,
        "documento": document,
        "conteos": signatures,
        "dimensiones": dimensions,
    }
    revision = hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()
    return {
        "alcance": scope.alcance,
        "documento": document,
        "conteos": counters,
        "trabajos_en_curso": running,
        "revision": revision,
        "confirmacion": confirmation(scope),
        "conserva": [
            "Usuarios y roles",
            "Configuracion del servicio y catalogo TipoActProy",
            "Toda la auditoria",
            "Historial de metricas",
        ],
        "nota": (
            "Se eliminan original, detalle y modelo de este documento. Los trabajos vinculados quedan "
            "cancelados y se conserva su historial. No se publica una version anterior automaticamente."
            if document
            else "Se eliminan todos los documentos, datos, observaciones, intentos, trabajos, "
            "consultas y lotes. Se vacian las entidades del modelo. Los identificadores no se reinician."
        ),
    }


@router.post("/vista-previa")
def preview(body: Scope):
    with transaction() as con:
        integration_lock(con, exclusive=True)
        return snapshot(con, body)


def prune_dimensions(con):
    removed = 0
    for table in reversed(ENTITIES):
        references = [
            ("Gasto", column.name)
            for column in FACT_COLUMNS
            if column.reference == table
        ]
        references += [
            (child, column.name)
            for child, (_, _, columns) in ENTITIES.items()
            for column in columns
            if column.reference == table
        ]
        conditions = [
            f"NOT EXISTS(SELECT 1 FROM modelo.[{child}] r WHERE r.[{column}]=e.Id)"
            for child, column in references
        ]
        # Funciona tambien si la conexion tiene NOCOUNT ON (p. ej. en pruebas).
        removed += con.execute(
            f"SET NOCOUNT ON; DELETE e FROM modelo.[{table}] e WHERE "
            + (" AND ".join(conditions) or "1=1")
            + "; SELECT CONVERT(bigint,@@ROWCOUNT);"
        ).fetchone()[0]
    return removed


@router.post("/eliminar")
def delete_data(body: Deletion):
    if body.confirmacion != confirmation(body) or len(body.motivo.strip()) < 5:
        raise HTTPException(
            422,
            "Escribe la confirmacion exacta y un motivo de al menos cinco caracteres.",
        )
    with transaction() as con:
        integration_lock(con, exclusive=True)
        acquire_document_lock(con)
        if con.execute(
            "SELECT COUNT(*) FROM integracion.Trabajo WHERE Estado='EnCurso'"
        ).fetchone()[0]:
            raise HTTPException(
                409,
                "Hay trabajos en curso. Espera a que terminen antes de eliminar datos.",
            )
        before = snapshot(con, body)
        if before["revision"] != body.revision:
            raise HTTPException(
                409,
                "Los datos cambiaron desde la vista previa. Revisa el alcance nuevamente.",
            )
        # No omitir silenciosamente una migracion: una FK pendiente impediria la limpieza.
        if con.execute(
            "SELECT COUNT(*) FROM sys.foreign_keys WHERE parent_object_id=OBJECT_ID(N'auditoria.CargaDocumento') "
            "AND referenced_object_id IN(OBJECT_ID(N'integracion.Documento'),OBJECT_ID(N'integracion.Lote'))"
        ).fetchone()[0]:
            raise HTTPException(
                409,
                "Actualiza el esquema con scripts/aplicar_sql.py antes de usar la limpieza.",
            )
        doc_id = body.documento_id
        if doc_id is not None:
            con.execute(
                "UPDATE integracion.Consulta SET DocumentoActualId=NULL WHERE DocumentoActualId=?",
                doc_id,
            )
            con.execute(
                "UPDATE integracion.Trabajo SET DocumentoId=NULL,Estado='Cancelado',Token=NULL,LeaseHastaUtc=NULL,"
                "FinalizadoUtc=SYSUTCDATETIME(),UltimoError=N'Documento eliminado desde mantenimiento' WHERE DocumentoId=?",
                doc_id,
            )
            con.execute(
                "UPDATE integracion.Intento SET DocumentoId=NULL WHERE DocumentoId=?",
                doc_id,
            )
            con.execute(
                "DELETE m FROM modelo.Gasto m JOIN datos.Gasto g ON g.Id=m.Id WHERE g.DocumentoId=?",
                doc_id,
            )
            con.execute("DELETE datos.Gasto WHERE DocumentoId=?", doc_id)
            con.execute(
                "DELETE integracion.ObservacionDato WHERE DocumentoId=?", doc_id
            )
            con.execute("DELETE integracion.Documento WHERE Id=?", doc_id)
        else:
            con.execute(
                "UPDATE integracion.Consulta SET DocumentoActualId=NULL WHERE DocumentoActualId IS NOT NULL"
            )
            con.execute(
                "UPDATE integracion.Trabajo SET DocumentoId=NULL WHERE DocumentoId IS NOT NULL"
            )
            con.execute(
                "UPDATE integracion.Intento SET DocumentoId=NULL WHERE DocumentoId IS NOT NULL"
            )
            for table in (
                "modelo.Gasto",
                "datos.Gasto",
                "integracion.ObservacionDato",
                "integracion.Documento",
                "integracion.Intento",
                "integracion.Trabajo",
                "integracion.Consulta",
                "integracion.Lote",
            ):
                con.execute(f"DELETE FROM {table}")
        removed = prune_dimensions(con)
        audit = {
            "accion": "EliminarDocumento" if doc_id else "VaciarCargas",
            "motivo": body.motivo.strip(),
            "documento": before["documento"],
            "conteos_previos": before["conteos"],
            "entidades_sin_referencias_eliminadas": removed,
        }
        con.execute(
            "INSERT auditoria.Cambio(Tabla,RegistroId,Operacion,UsuarioId,Actor,Rol,LoginSql,Correlacion,Antes) "
            "VALUES(N'integracion.Documento',?,'D',TRY_CONVERT(bigint,SESSION_CONTEXT(N'usuario_id')),"
            "CONVERT(nvarchar(128),SESSION_CONTEXT(N'actor')),CONVERT(nvarchar(40),SESSION_CONTEXT(N'rol')),"
            "ORIGINAL_LOGIN(),TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'correlation')),?)",
            doc_id or 0,
            json.dumps(audit, ensure_ascii=False, default=str),
        )
    return {
        "mensaje": "Documento eliminado."
        if doc_id
        else "Cargas del laboratorio eliminadas.",
        "conteos": before["conteos"],
        "entidades_eliminadas": removed,
        "auditoria_conservada": True,
    }
