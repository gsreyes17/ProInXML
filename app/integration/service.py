"""Lotes, cola persistente, idempotencia y publicacion atomica de documentos."""

import gzip
from itertools import islice
import random
from time import perf_counter_ns

from app.infrastructure.db import insert_id, rows, transaction
from app.infrastructure.locks import integration_lock
from app.integration.metrics import close_interrupted, timing
from app.integration.normalizer import acquire_document_lock, normalize_document
from app.domain.xml_reader import FIELDS, content_hash, iter_records


class QualityError(ValueError):
    pass


def create_batch(name: str, sources: list[dict]) -> dict:
    unique = {(s["year"], s["level"], s["unit"]): s for s in sources}
    if not unique:
        raise ValueError("No hay URLs validas para importar.")
    loaded = 0
    with transaction() as con:
        integration_lock(con)
        service = con.execute(
            "SELECT TOP(1) Id FROM integracion.Servicio WHERE Activo=1 ORDER BY Id"
        ).fetchone()
        if not service:
            raise ValueError("El servicio MEF no esta activo.")
        creator = con.execute(
            "SELECT TRY_CONVERT(bigint,SESSION_CONTEXT(N'usuario_id'))"
        ).fetchone()[0]
        if creator is None:
            raise ValueError("La carga requiere una identidad de usuario.")
        batch_id = insert_id(
            con,
            "INSERT integracion.Lote(Nombre,CreadoPorUsuarioId) VALUES(?,?)",
            name[:260],
            creator,
        )
        for key in sorted(unique):
            source = unique[key]
            found = con.execute(
                "SELECT c.Id,c.DocumentoActualId,d.EsValido FROM integracion.Consulta c WITH(UPDLOCK,HOLDLOCK) "
                "LEFT JOIN integracion.Documento d ON d.Id=c.DocumentoActualId "
                "WHERE c.ServicioId=? AND c.AnoEje=? AND c.NivelGobierno=? AND c.SecEjec=?",
                service[0],
                *key,
            ).fetchone()
            source_id = (
                found[0]
                if found
                else insert_id(
                    con,
                    "INSERT integracion.Consulta(ServicioId,URL,AnoEje,NivelGobierno,SecEjec) VALUES(?,?,?,?,?)",
                    service[0],
                    source["url"],
                    *key,
                )
            )
            already = bool(found and found[1] and found[2])
            loaded += int(already)
            con.execute(
                "INSERT integracion.Trabajo(LoteId,ConsultaId,Estado,DocumentoId,FinalizadoUTC) "
                "VALUES(?,?,?,?,CASE WHEN ?=1 THEN SYSUTCDATETIME() END)",
                batch_id,
                source_id,
                "YaCargada" if already else "Pendiente",
                found[1] if already else None,
                int(already),
            )
    return {
        "lote_id": batch_id,
        "trabajos": len(unique),
        "nuevas": len(unique) - loaded,
        "ya_cargadas": loaded,
        "duplicados_omitidos": len(sources) - len(unique),
    }


def claim_job(batch_id: int | None = None) -> dict | None:
    with transaction(actor="sistema") as con:
        integration_lock(con)
        result = rows(con.execute("EXEC integracion.TomarTrabajo @LoteId=?", batch_id))
        close_interrupted(con)
        return result[0] if result else None


def lock_job(con, job: dict):
    found = con.execute(
        "SELECT Id FROM integracion.Trabajo WITH(UPDLOCK,HOLDLOCK) WHERE Id=? AND Estado='EnCurso' AND Token=?",
        job["Id"],
        job["Token"],
    ).fetchone()
    if not found:
        raise ValueError("El trabajo ya no pertenece a este worker.")


def save_response(job: dict, data: bytes, content_type: str, status: int) -> int:
    """La huella se calcula sobre los bytes originales; gzip es solo almacenamiento."""
    with transaction(actor="sistema", correlation=str(job["Token"])) as con:
        integration_lock(con)
        lock_job(con, job)
        con.execute(
            "SELECT Id FROM integracion.Consulta WITH(UPDLOCK,HOLDLOCK) WHERE Id=?",
            job["ConsultaId"],
        ).fetchone()
        digest = content_hash(data).hex()
        old = con.execute(
            "SELECT Id FROM integracion.Documento WHERE ConsultaId=? AND Sha256=?",
            job["ConsultaId"],
            digest,
        ).fetchone()
        document_id = (
            int(old[0])
            if old
            else insert_id(
                con,
                "INSERT integracion.Documento(ConsultaId,IntentoId,Sha256,Respuesta,ContentType) VALUES(?,?,?,?,?)",
                job["ConsultaId"],
                job["IntentoId"],
                digest,
                gzip.compress(data, mtime=0),
                content_type[:200],
            )
        )
        con.execute(
            "UPDATE integracion.Intento SET HTTPStatus=?,DocumentoId=?,Etapa=N'Validacion' WHERE Id=?",
            status,
            document_id,
            job["IntentoId"],
        )
        con.execute(
            "UPDATE integracion.Trabajo SET DocumentoId=? WHERE Id=?",
            document_id,
            job["Id"],
        )
        return document_id


def save_observations(con, document_id, observations):
    for obs in observations:
        con.execute(
            "INSERT integracion.ObservacionDato(DocumentoId,OrdinalItem,Campo,CodigoObservacion,Severidad,Detalle) "
            "SELECT ?,?,?,?,?,? WHERE NOT EXISTS(SELECT 1 FROM integracion.ObservacionDato "
            "WHERE DocumentoId=? AND OrdinalItem=? AND Campo=? AND CodigoObservacion=?)",
            document_id,
            obs["ordinal"],
            obs["campo"],
            obs["codigo"],
            obs["severidad"],
            obs["detalle"],
            document_id,
            obs["ordinal"],
            obs["campo"],
            obs["codigo"],
        )


def persist_records(job: dict, document_id: int, data: bytes, *, meter=None) -> int:
    source = {
        "year": job["AnoEje"],
        "level": job["NivelGobierno"],
        "unit": job["SecEjec"],
    }
    observations = []
    quality_error = False
    count = inserted = reused = 0
    commit_started = None
    try:
        with transaction(actor="sistema", correlation=str(job["Token"])) as con:
            with timing(meter, "EsperaSQLMs"):
                integration_lock(con)
                acquire_document_lock(con)
                lock_job(con, job)
                con.execute(
                    "SELECT Id FROM integracion.Consulta WITH(UPDLOCK,HOLDLOCK) WHERE Id=?",
                    job["ConsultaId"],
                ).fetchone()
            document = con.execute(
                "SELECT EsValido,CantidadRegistros FROM integracion.Documento WITH(UPDLOCK,HOLDLOCK) WHERE Id=?",
                document_id,
            ).fetchone()
            if document[0]:
                count = reused = document[1]
                if meter is not None:
                    meter.read = count
            else:
                existing = {
                    r[0]
                    for r in con.execute(
                        "SELECT Ordinal FROM staging.Gasto WHERE DocumentoId=?",
                        document_id,
                    )
                }

                def tracked_records():
                    for record in iter_records(data, source, observations):
                        if meter is not None:
                            meter.read += 1
                        yield record

                records = tracked_records()
                columns = ",".join(f"[{f}]" for f in FIELDS)
                placeholders = ",".join("?" for _ in range(len(FIELDS) + 2))
                statement = f"INSERT staging.Gasto(DocumentoId,Ordinal,{columns}) VALUES({placeholders})"
                cursor = con.cursor()
                while True:
                    with timing(meter, "ValidacionMs"):
                        batch = list(islice(records, 500))
                    if not batch:
                        break
                    with timing(meter, "InsercionMs"):
                        values = [
                            (document_id, count + i, *(record[f] for f in FIELDS))
                            for i, record in enumerate(batch, 1)
                            if count + i not in existing
                        ]
                        if values:
                            cursor.executemany(statement, values)
                    inserted += len(values)
                    reused += len(batch) - len(values)
                    count += len(batch)
                save_observations(con, document_id, observations)
                quality_error = any(obs["severidad"] == "Error" for obs in observations)
                if not quality_error:
                    with timing(meter, "NormalizacionMs"):
                        normalize_document(con, document_id)
                con.execute(
                    "UPDATE integracion.Documento SET EsValido=?,CantidadRegistros=?,ErrorValidacion=? WHERE Id=?",
                    int(not quality_error),
                    count,
                    "Observaciones de severidad Error" if quality_error else None,
                    document_id,
                )
            if meter is not None:
                meter.stage = "Publicacion"
            errors = sum(o["severidad"] == "Error" for o in observations)
            observed = con.execute(
                "SELECT COUNT(*) FROM integracion.ObservacionDato WHERE DocumentoId=?",
                document_id,
            ).fetchone()[0]
            con.execute(
                "UPDATE integracion.Intento SET RegistrosLeidos=?,RegistrosInsertados=?,RegistrosReutilizados=?, "
                "RegistrosRechazados=?,Observaciones=? WHERE Id=?",
                count,
                inserted,
                reused,
                errors,
                observed,
                job["IntentoId"],
            )
            con.execute(
                "INSERT auditoria.CargaDocumento(DocumentoId,LoteId,UsuarioId,Rol,FilasInsertadas,FilasReutilizadas) "
                "SELECT ?,?,TRY_CONVERT(bigint,SESSION_CONTEXT(N'usuario_id')),CONVERT(nvarchar(40),SESSION_CONTEXT(N'rol')),?,? "
                "WHERE NOT EXISTS(SELECT 1 FROM auditoria.CargaDocumento WHERE DocumentoId=?)",
                document_id,
                job["LoteId"],
                inserted,
                reused,
                document_id,
            )
            if not quality_error:
                con.execute(
                    "UPDATE integracion.Consulta SET DocumentoActualId=? WHERE Id=?",
                    document_id,
                    job["ConsultaId"],
                )
                state = "Completado" if count else "CompletadoSinDatos"
                con.execute(
                    "UPDATE integracion.Trabajo SET Estado=?,FinalizadoUTC=SYSUTCDATETIME(),LeaseHastaUTC=NULL,Token=NULL,"
                    "UltimoError=NULL,DocumentoId=? WHERE Id=?",
                    state,
                    document_id,
                    job["Id"],
                )
                con.execute(
                    "UPDATE integracion.Intento SET Estado='Completado',Etapa=N'Finalizado',FinUTC=SYSUTCDATETIME() WHERE Id=?",
                    job["IntentoId"],
                )
            commit_started = perf_counter_ns()
    finally:
        if meter is not None and commit_started is not None:
            meter.add("ConfirmacionMs", perf_counter_ns() - commit_started)
    if meter is not None:
        # Solo se cuentan como insertadas las filas cuya transaccion se confirmo.
        meter.inserted, meter.reused = inserted, reused
        meter.normalized = (
            count if not quality_error and "NormalizacionMs" in meter.times else 0
        )
    if quality_error:
        if meter is not None:
            meter.stage = "Validacion"
        raise QualityError(
            "El XML se conservo, pero contiene observaciones de severidad Error y no se publico."
        )
    return count


def fail_job(
    job: dict,
    error: str,
    *,
    retryable: bool,
    status: int | None = None,
    document_id: int | None = None,
    stage: str = "Descarga",
):
    error = error[:2000]
    delay = min(1800, 15 * (2 ** min(job["Intentos"] - 1, 8))) + random.randint(0, 10)
    with transaction(actor="sistema", correlation=str(job["Token"])) as con:
        integration_lock(con)
        lock_job(con, job)
        con.execute(
            "UPDATE integracion.Intento SET Estado='Error',Etapa=?,FinUTC=SYSUTCDATETIME(),"
            "HTTPStatus=COALESCE(?,HTTPStatus),Error=? WHERE Id=?",
            stage,
            status,
            error,
            job["IntentoId"],
        )
        if document_id is not None:
            con.execute(
                "UPDATE integracion.Documento SET ErrorValidacion=? WHERE Id=? AND EsValido=0",
                error,
                document_id,
            )
        con.execute(
            "UPDATE integracion.Trabajo SET "
            "Estado=CASE WHEN ?=1 AND Intentos<MaxIntentos THEN 'Pendiente' ELSE 'Fallido' END,"
            "ProximoIntentoUTC=DATEADD(second,?,SYSUTCDATETIME()),"
            "FinalizadoUTC=CASE WHEN ?=1 AND Intentos<MaxIntentos THEN NULL ELSE SYSUTCDATETIME() END,"
            "LeaseHastaUTC=NULL,Token=NULL,UltimoError=? WHERE Id=?",
            int(retryable),
            delay,
            int(retryable),
            error,
            job["Id"],
        )


def schedule_again(job_id: int, *, force=False):
    with transaction() as con:
        integration_lock(con)
        job = con.execute(
            "SELECT Estado FROM integracion.Trabajo WITH(UPDLOCK,HOLDLOCK) WHERE Id=?",
            job_id,
        ).fetchone()
        if not job:
            raise LookupError("Trabajo no encontrado.")
        allowed = (
            ("Completado", "CompletadoSinDatos", "YaCargada", "Fallido")
            if force
            else ("Fallido",)
        )
        if job[0] not in allowed:
            raise ValueError(
                "El trabajo no se encuentra en un estado que permita esta accion."
            )
        # No se agrega un indicador de fuerza: solo se encolan las revisiones solicitadas.
        con.execute(
            "UPDATE integracion.Trabajo SET Estado='Pendiente',Intentos=0,ProximoIntentoUTC=SYSUTCDATETIME(),"
            "FinalizadoUTC=NULL,LeaseHastaUTC=NULL,Token=NULL,UltimoError=NULL WHERE Id=?",
            job_id,
        )
    return {
        "trabajo_id": job_id,
        "mensaje": "Revision forzada encolada." if force else "Reintento encolado.",
    }
