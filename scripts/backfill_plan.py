"""Completa trazabilidad historica y reprocesa documentos guardados, sin usar la red."""
import gzip
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import insert_id, rows, transaction
from app.service import fail_job, persist_records, save_response
from app.xml_reader import iter_records
from app.normalizer import normalize_document


def main():
    with transaction(actor="sistema") as con:
        missing_model = [r[0] for r in con.execute("SELECT d.Id FROM integracion.Documento d WHERE d.EsValido=1 AND EXISTS("
                        "SELECT 1 FROM datos.Gasto g WHERE g.DocumentoId=d.Id AND NOT EXISTS(SELECT 1 FROM modelo.Gasto m WHERE m.Id=g.Id))")]
        # FechaUtc conserva la fecha de procesamiento historica; CreadoUtc indica el backfill.
        con.execute("INSERT auditoria.CargaDocumento(DocumentoId,LoteId,UsuarioId,Rol,FilasInsertadas,FilasReutilizadas,FechaUtc) "
                    "SELECT d.Id,t.LoteId,TRY_CONVERT(bigint,SESSION_CONTEXT(N'usuario_id')),N'Administrador',"
                    "d.CantidadRegistros,0,COALESCE(a.FinUtc,d.CreadoUtc) FROM integracion.Documento d "
                    "JOIN integracion.Intento a ON a.Id=d.IntentoId JOIN integracion.Trabajo t ON t.Id=a.TrabajoId "
                    "WHERE d.EsValido=1 AND NOT EXISTS(SELECT 1 FROM auditoria.CargaDocumento c WHERE c.DocumentoId=d.Id)")
        # Solo se completan las metricas demostrables por el documento de ese intento original.
        con.execute("UPDATE a SET DocumentoId=d.Id,RegistrosLeidos=d.CantidadRegistros,RegistrosInsertados=d.CantidadRegistros,"
                    "RegistrosReutilizados=0,RegistrosRechazados=0,Observaciones=0,Etapa=N'Finalizado' "
                    "FROM integracion.Intento a JOIN integracion.Documento d ON d.IntentoId=a.Id "
                    "WHERE d.EsValido=1 AND a.Estado='Completado' AND a.RegistrosLeidos IS NULL")
        docs = rows(con.execute("SELECT d.Id,d.Respuesta,d.ConsultaId,a.HttpStatus,t.Id AS TrabajoId,c.AnoEje,c.NivelGobierno,c.SecEjec "
                                "FROM integracion.Documento d JOIN integracion.Intento a ON a.Id=d.IntentoId "
                                "JOIN integracion.Trabajo t ON t.Id=a.TrabajoId JOIN integracion.Consulta c ON c.Id=d.ConsultaId "
                                "WHERE d.EsValido=0 AND a.HttpStatus=200 AND t.Estado='Fallido' ORDER BY d.Id"))
    for document_id in missing_model:
        with transaction(actor="sistema") as con:
            normalize_document(con, document_id)
        print(f"Documento {document_id}: modelo historico completado.")
    for doc in docs:
        data = gzip.decompress(doc['Respuesta'])
        source = {'year': doc['AnoEje'], 'level': doc['NivelGobierno'], 'unit': doc['SecEjec']}
        try:
            # No cambiar trabajos de documentos que sigan incumpliendo el contrato.
            count = sum(1 for _ in iter_records(data, source))
        except Exception as exc:
            print(f"Documento {doc['Id']}: pendiente de revision: {exc}")
            continue
        with transaction(actor="sistema") as con:
            found = con.execute("SELECT Estado FROM integracion.Trabajo WITH(UPDLOCK,HOLDLOCK) WHERE Id=?", doc['TrabajoId']).fetchone()
            if found[0] != 'Fallido':
                continue
            token = str(uuid4())
            con.execute("UPDATE integracion.Trabajo SET Estado='EnCurso',Token=?,LeaseHastaUtc=DATEADD(minute,10,SYSUTCDATETIME()),"
                        "Intentos=Intentos+1,FinalizadoUtc=NULL WHERE Id=?", token, doc['TrabajoId'])
            number = con.execute("SELECT COALESCE(MAX(Numero),0)+1 FROM integracion.Intento WHERE TrabajoId=?", doc['TrabajoId']).fetchone()[0]
            job = rows(con.execute("SELECT t.Id,t.LoteId,t.ConsultaId,t.Intentos,t.Token,c.Url,c.AnoEje,c.NivelGobierno,c.SecEjec "
                                   "FROM integracion.Trabajo t JOIN integracion.Consulta c ON c.Id=t.ConsultaId WHERE t.Id=?", doc['TrabajoId']))[0]
            job['IntentoId'] = insert_id(con, "INSERT integracion.Intento(TrabajoId,Numero,UrlSolicitada,Etapa,DocumentoId,HttpStatus) "
                                             "VALUES(?,?,?,N'Validacion',?,?)", job['Id'], number, job['Url'], doc['Id'], doc['HttpStatus'])
        try:
            document_id = save_response(job, data, 'text/xml', doc['HttpStatus'])
            persist_records(job, document_id, data)
            print(f"Documento {document_id}: recuperado con {count} registros, sin nueva descarga.")
        except Exception as exc:
            fail_job(job, str(exc), retryable=False, document_id=doc['Id'], stage='Persistencia')
            raise


if __name__ == '__main__':
    main()
