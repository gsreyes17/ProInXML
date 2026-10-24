"""Pruebas SQL reales: transacciones reversibles; concurrencia solo en la base aislada."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import gzip
import os
from pathlib import Path
import re
from threading import Barrier
import unittest
from unittest.mock import patch
from xml.etree.ElementTree import ParseError

from fastapi.testclient import TestClient
from app import db, service
from app.main import app
from app.security import current_user, password_hash, sessions
from app.xml_reader import FIELDS, canonical_source

URL='http://s3.mef.gob.pe/servicios/WSPCM/SG/gastopipsg-old.asmx/ObtenerDataGastoPIP_old_2?anoEje=2020&nivelGobierno=E&sec_ejec=3'
ENABLED=os.getenv('PROINXML_RUN_SQL_TESTS')=='1'


@unittest.skipUnless(ENABLED,'SQL opcional: PROINXML_RUN_SQL_TESTS=1')
class SqlIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.context=db.transaction(actor='sistema')
        self.con=self.context.__enter__()
        self.con.execute('BEGIN TRANSACTION')
        self.system_id=self.con.execute("SELECT Id FROM seguridad.Usuario WHERE NombreUsuario=N'sistema'").fetchone()[0]
        self.sequence=0

        @contextmanager
        def scoped_transaction(*args,**kwargs):
            self.sequence+=1
            name=f'test_save_{self.sequence}'
            self.con.execute(f'SAVE TRANSACTION {name}')
            current=db.identity.get() or {}
            self.con.execute("EXEC sys.sp_set_session_context @key=N'usuario_id',@value=?",current.get('Id',self.system_id))
            self.con.execute("EXEC sys.sp_set_session_context @key=N'actor',@value=?",kwargs.get('actor') or current.get('NombreUsuario','sistema'))
            self.con.execute("EXEC sys.sp_set_session_context @key=N'rol',@value=?",current.get('Rol','Administrador'))
            try:
                yield self.con
            except BaseException:
                self.con.execute(f'ROLLBACK TRANSACTION {name}')
                raise
        self.patchers=[patch(module+'.transaction',scoped_transaction) for module in
                       ('app.service','app.main','app.explorer','app.security','app.maintenance','app.metrics','app.analysis')]
        for p in self.patchers:p.start()
        self.data=(Path(__file__).parent/'fixtures'/'mef_partial_fixture.xml').read_bytes()
        self.source=canonical_source(URL)
        async def user_override():
            return {'Id':self.system_id,'NombreUsuario':'test','Rol':'Administrador'}
        app.dependency_overrides[current_user]=user_override
        self.client=TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        sessions.clear()
        for p in reversed(self.patchers):p.stop()
        self.con.rollback()
        self.context.__exit__(None,None,None)

    def new_job(self,source=None):
        batch=service.create_batch('TEST: transaccion reversible',[source or self.source])
        job_id=self.con.execute('SELECT Id FROM integracion.Trabajo WHERE LoteId=?',batch['lote_id']).fetchone()[0]
        if batch['ya_cargadas']:service.schedule_again(job_id,force=True)
        self.con.execute('UPDATE integracion.Trabajo SET ProximoIntentoUtc=DATEADD(second,-1,SYSUTCDATETIME()) WHERE Id=?',job_id)
        job=service.claim_job()
        self.assertEqual(job['Id'],job_id)
        return job

    def ingest(self,data=None,source=None):
        data=data or self.data
        job=self.new_job(source)
        doc=service.save_response(job,data,'text/xml',200)
        count=service.persist_records(job,doc,data)
        self.assertEqual(count,7)
        return doc,job

    def assert_reconstruction(self,doc):
        columns=','.join('['+n+']' for n in FIELDS)
        original=list(self.con.execute(f'SELECT Id,{columns} FROM datos.Gasto WHERE DocumentoId=? ORDER BY Id',doc))
        reconstructed=list(self.con.execute(f"SELECT n.Id,{','.join('n.['+n+']' for n in FIELDS)} FROM modelo.GastoReconstruido n "
                                             'JOIN datos.Gasto g ON g.Id=n.Id WHERE g.DocumentoId=? ORDER BY n.Id',doc))
        self.assertEqual([tuple(r) for r in original],[tuple(r) for r in reconstructed])

    def test_versions_idempotence_and_current_view(self):
        first,_=self.ingest()
        second,job=self.ingest()
        self.assertEqual(first,second)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM datos.Gasto WHERE DocumentoId=?',first).fetchone()[0],7)
        self.assertEqual(tuple(self.con.execute('SELECT RegistrosInsertados,RegistrosReutilizados FROM integracion.Intento WHERE Id=?',job['IntentoId']).fetchone()),(0,7))
        third,_=self.ingest(self.data.replace(b'<PIA>1800</PIA>',b'<PIA>1801</PIA>',1))
        self.assertNotEqual(first,third)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM datos.GastoActual WHERE DocumentoId=?',first).fetchone()[0],0)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM modelo.GastoActual m JOIN datos.Gasto g ON g.Id=m.Id WHERE g.DocumentoId=?',third).fetchone()[0],7)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM auditoria.CargaDocumento WHERE DocumentoId=?',first).fetchone()[0],1)

    def test_registration_skips_valid_document_without_download(self):
        doc,_=self.ingest()
        result=service.create_batch('TEST ya cargada',[self.source,self.source])
        self.assertEqual((result['ya_cargadas'],result['nuevas'],result['duplicados_omitidos']),(1,0,1))
        row=self.con.execute('SELECT Estado,Intentos,DocumentoId FROM integracion.Trabajo WHERE LoteId=?',result['lote_id']).fetchone()
        self.assertEqual(tuple(row),('YaCargada',0,doc))
        self.assertIsNone(service.claim_job())

    def test_same_payload_is_scoped_to_consulta(self):
        # Cero Item es contenido identico y valido para consultas distintas.
        data=b'<DataGasto xmlns="http://www.mef.gob.pe/"/>'
        docs=[]
        for unit in (2147483001,2147483002):
            job=self.new_job(canonical_source(URL.replace('sec_ejec=3',f'sec_ejec={unit}')))
            doc=service.save_response(job,data,'text/xml',200)
            self.assertEqual(service.persist_records(job,doc,data),0)
            self.assertEqual(self.con.execute('SELECT Estado FROM integracion.Trabajo WHERE Id=?',job['Id']).fetchone()[0],'CompletadoSinDatos')
            docs.append(doc)
        self.assertNotEqual(*docs)

    def test_truncated_xml_rolls_back_more_than_one_batch(self):
        job=self.new_job()
        body=self.data.split(b'<DataGasto xmlns="http://www.mef.gob.pe/">',1)[1].split(b'</DataGasto>',1)[0]
        invalid=b'<DataGasto xmlns="http://www.mef.gob.pe/">'+body*100
        doc=service.save_response(job,invalid,'text/xml',200)
        with self.assertRaises(ParseError):service.persist_records(job,doc,invalid)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM datos.Gasto WHERE DocumentoId=?',doc).fetchone()[0],0)
        service.fail_job(job,'XML truncado',retryable=False,document_id=doc,stage='Validacion')
        self.assertEqual(self.con.execute('SELECT Estado FROM integracion.Trabajo WHERE Id=?',job['Id']).fetchone()[0],'Fallido')
        stored=self.con.execute('SELECT Respuesta FROM integracion.Documento WHERE Id=?',doc).fetchone()[0]
        self.assertEqual(gzip.decompress(stored),invalid)

    def test_expired_lease_recovers_without_exhausting_error_budget(self):
        first=self.new_job()
        self.con.execute('UPDATE integracion.Trabajo SET LeaseHastaUtc=DATEADD(minute,-1,SYSUTCDATETIME()) WHERE Id=?',first['Id'])
        second=service.claim_job()
        self.assertEqual(first['Id'],second['Id'])
        self.assertNotEqual(first['Token'],second['Token'])
        self.assertEqual(second['Intentos'],1)
        self.assertEqual(self.con.execute('SELECT Estado FROM integracion.Intento WHERE Id=?',first['IntentoId']).fetchone()[0],'Interrumpido')
        with self.assertRaisesRegex(ValueError,'no pertenece'):service.save_response(first,self.data,'text/xml',200)

    def test_unit_null_is_normalized_and_observed_once(self):
        data=re.sub(rb'<Unidad_Medida>.*?</Unidad_Medida>',b'<Unidad_Medida/>',self.data,count=1)
        doc,_=self.ingest(data)
        self.assertIsNone(self.con.execute('SELECT Unidad_Medida FROM datos.Gasto WHERE DocumentoId=? AND Ordinal=1',doc).fetchone()[0])
        self.assert_reconstruction(doc)
        before=self.con.execute('SELECT COUNT(*) FROM modelo.Meta').fetchone()[0]
        self.con.execute('EXEC modelo.NormalizarDocumento ?',doc)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM modelo.Meta').fetchone()[0],before)
        self.ingest(data)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM integracion.ObservacionDato WHERE DocumentoId=?',doc).fetchone()[0],1)

    def test_invalid_type_is_retained_but_never_published(self):
        data=re.sub(rb'<TipoActProy>[23]</TipoActProy>',b'<TipoActProy>4</TipoActProy>',self.data,count=1)
        job=self.new_job()
        before=self.con.execute('SELECT DocumentoActualId FROM integracion.Consulta WHERE Id=?',job['ConsultaId']).fetchone()[0]
        doc=service.save_response(job,data,'text/xml',200)
        with self.assertRaises(service.QualityError):service.persist_records(job,doc,data)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM datos.Gasto WHERE DocumentoId=?',doc).fetchone()[0],7)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM modelo.Gasto m JOIN datos.Gasto g ON g.Id=m.Id WHERE g.DocumentoId=?',doc).fetchone()[0],0)
        self.assertEqual(self.con.execute('SELECT DocumentoActualId FROM integracion.Consulta WHERE Id=?',job['ConsultaId']).fetchone()[0],before)
        self.assertEqual(self.con.execute('SELECT Severidad FROM integracion.ObservacionDato WHERE DocumentoId=?',doc).fetchone()[0],'Error')

    def test_reconstruction_of_39_columns_and_no_bulk_row_audit(self):
        start=self.con.execute("SELECT COUNT(*) FROM auditoria.Cambio WHERE Tabla IN ('datos.Gasto','modelo.Gasto')").fetchone()[0]
        doc,_=self.ingest()
        self.assert_reconstruction(doc)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM auditoria.Cambio WHERE Tabla IN ('datos.Gasto','modelo.Gasto')").fetchone()[0],start)
        self.assertEqual(len(self.con.execute('SELECT TOP(0) * FROM datos.vw_GastoXML').description),39)

    def test_explorers_return_pure_xml_and_trace_separately(self):
        doc,job=self.ingest()
        result=self.client.get(f'/datos/xml?documento_id={doc}&limite=2').json()
        self.assertEqual(len(result['columnas']),39)
        self.assertEqual(len(result['registros'][0]),39)
        self.assertEqual(result['total'],7)
        next_page=self.client.get(f"/datos/xml?documento_id={doc}&limite=2&despues_de={result['siguiente_cursor']}").json()
        self.assertGreater(next_page['identificadores'][0],result['identificadores'][-1])
        detail=self.client.get(f"/datos/xml/{result['identificadores'][0]}").json()
        self.assertEqual(detail['trazabilidad']['DocumentoId'],doc)
        report=self.client.get(f"/reportes/ejecucion?trabajo_id={job['Id']}").json()['registros'][0]
        self.assertEqual(report['HttpStatus'],200)
        self.assertIsNotNone(report['FinUtc'])
        self.assertEqual(report['RegistrosLeidos'],7)
        jobs=self.client.get(f"/lotes/{job['LoteId']}/trabajos?estado=").json()
        self.assertEqual(len(jobs),1)
        self.assertEqual(self.client.get(f"/lotes/{job['LoteId']}/trabajos?estado=CompletadoSinDatos").json(),[])

    def require_validation_database(self):
        if self.con.execute('SELECT DB_NAME()').fetchone()[0] != 'ProInXML_Validacion':
            self.skipTest('Mantenimiento solo en ProInXML_Validacion y con rollback.')

    def process_measured_fixture(self, data=None, status=200, *, timeout=False):
        import httpx
        from app.worker import process
        self.require_validation_database()
        job = self.new_job()
        real_client = httpx.Client
        def handler(request):
            if timeout:
                raise httpx.ConnectTimeout('Sin conexion de prueba')
            return httpx.Response(status, content=self.data if data is None else data, headers={'content-type':'text/xml'})
        with patch('app.worker.httpx.Client', side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw)):
            process(job, concurrency=20)
        return job

    def metric(self, job):
        return db.rows(self.con.execute('SELECT * FROM analisis.MetricaIntento WHERE IntentoId=?',job['IntentoId']))[0]

    def test_metrics_record_actual_phases_and_survive_reset(self):
        job = self.process_measured_fixture()
        metric = self.metric(job)
        self.assertEqual((metric['Estado'],metric['Concurrencia'],metric['RegistrosInsertados'],metric['RegistrosNormalizados']),('Completado',20,7,7))
        self.assertTrue(metric['MedicionFinalizada'])
        for field in ('DescargaMs','OriginalMs','EsperaSqlMs','ValidacionMs','InsercionMs','NormalizacionMs','ConfirmacionMs','TotalMs'):
            self.assertIsNotNone(metric[field],field)
            self.assertGreaterEqual(metric[field],0,field)
        summary = self.client.get(f"/metricas/resumen?lote_id={job['LoteId']}")
        self.assertEqual(summary.status_code,200,summary.text)
        payload = summary.json()
        self.assertEqual(payload['resumen']['Completados'],1)
        self.assertEqual(payload['resumen']['FilasInsertadas'],7)
        self.assertEqual(payload['comparacion'][0]['Concurrencia'],20)
        self.assertEqual(payload['fases'][0]['Muestras'],1)
        self.assertIsNotNone(payload['total_intento']['P95Ms'])
        self.delete_with_preview()
        self.assertEqual(self.metric(job)['IntentoId'],job['IntentoId'])
        self.assertIn(job['LoteId'],[r['LoteId'] for r in self.client.get('/metricas/lotes').json()])
        self.assertEqual(self.client.get(f"/metricas/intentos?lote_id={job['LoteId']}").json()['total'],1)

    def test_metrics_failed_network_has_no_invented_sql_times(self):
        job = self.process_measured_fixture(timeout=True)
        metric = self.metric(job)
        self.assertEqual(metric['Estado'],'Error')
        self.assertIsNone(metric['HttpStatus'])
        self.assertEqual(metric['BytesRecibidos'],0)
        self.assertIsNotNone(metric['DescargaMs'])
        self.assertIsNone(metric['NormalizacionMs'])
        self.assertIsNone(metric['OriginalMs'])

    def test_metrics_do_not_count_rolled_back_inserts(self):
        body = self.data.split(b'<DataGasto xmlns="http://www.mef.gob.pe/">',1)[1].split(b'</DataGasto>',1)[0]
        invalid = b'<DataGasto xmlns="http://www.mef.gob.pe/">'+body*100
        job = self.process_measured_fixture(invalid)
        metric = self.metric(job)
        self.assertEqual(metric['Estado'],'Error')
        self.assertGreaterEqual(metric['RegistrosLeidos'],500)
        self.assertEqual(metric['RegistrosInsertados'],0)
        self.assertIsNotNone(metric['InsercionMs'])
        self.assertIsNone(metric['NormalizacionMs'])
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM datos.Gasto WHERE DocumentoId=?',metric['DocumentoId']).fetchone()[0],0)

    def test_metrics_quality_error_preserves_committed_detail(self):
        data = re.sub(rb'<TipoActProy>[23]</TipoActProy>',b'<TipoActProy>4</TipoActProy>',self.data,count=1)
        job = self.process_measured_fixture(data)
        metric = self.metric(job)
        self.assertEqual((metric['Estado'],metric['RegistrosInsertados'],metric['RegistrosNormalizados']),('Error',7,0))
        self.assertIsNone(metric['NormalizacionMs'])
        self.assertIsNotNone(metric['ConfirmacionMs'])

    def test_metrics_reused_document_is_not_new_throughput(self):
        self.process_measured_fixture()
        second = self.process_measured_fixture()
        metric = self.metric(second)
        self.assertEqual((metric['RegistrosInsertados'],metric['RegistrosReutilizados'],metric['RegistrosNormalizados']),(0,7,0))
        self.assertIsNone(metric['NormalizacionMs'])
        self.assertIsNone(metric['ValidacionMs'])

    def test_metrics_expired_lease_closes_partial_measurement(self):
        self.require_validation_database()
        from app.metrics import AttemptMetrics
        job = self.new_job()
        meter = AttemptMetrics(job,20)
        meter.save()
        self.con.execute('UPDATE integracion.Trabajo SET LeaseHastaUtc=DATEADD(second,-1,SYSUTCDATETIME()) WHERE Id=?',job['Id'])
        service.claim_job()
        metric = self.metric(job)
        self.assertEqual(metric['Estado'],'Interrumpido')
        self.assertFalse(metric['MedicionFinalizada'])
        self.assertIsNone(metric['DescargaMs'])

    def test_metrics_failure_does_not_fail_business_load(self):
        with patch('app.metrics.transaction',side_effect=RuntimeError('Analisis no disponible')):
            with self.assertLogs('proinxml.metricas',level='WARNING'):
                job = self.process_measured_fixture()
        self.assertEqual(self.con.execute('SELECT Estado FROM integracion.Trabajo WHERE Id=?',job['Id']).fetchone()[0],'Completado')
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM analisis.MetricaIntento WHERE IntentoId=?',job['IntentoId']).fetchone()[0],0)

    def delete_with_preview(self, doc=None):
        scope = {'alcance': 'documento' if doc else 'todo', 'documento_id': doc}
        response = self.client.post('/mantenimiento/vista-previa', json=scope)
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()
        result = self.client.post('/mantenimiento/eliminar', json={**scope, 'revision': preview['revision'],
                                  'confirmacion': preview['confirmacion'], 'motivo': 'Prueba reversible de laboratorio'})
        self.assertEqual(result.status_code, 200, result.text)
        return preview, result.json()

    def test_delete_document_preserves_other_version_shared_entities_and_audit(self):
        self.require_validation_database()
        first, _ = self.ingest()
        second, second_job = self.ingest(self.data.replace(b'<PIA>1800</PIA>', b'<PIA>1801</PIA>', 1))
        counts = self.con.execute('SELECT (SELECT COUNT(*) FROM modelo.Meta),(SELECT COUNT(*) FROM auditoria.CargaDocumento)').fetchone()
        preview, _ = self.delete_with_preview(first)
        self.assertEqual(preview['conteos']['registros_xml'], 7)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM integracion.Documento WHERE Id=?', first).fetchone()[0], 0)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM datos.Gasto WHERE DocumentoId=?', first).fetchone()[0], 0)
        self.assertEqual(tuple(self.con.execute('SELECT (SELECT COUNT(*) FROM modelo.Meta),(SELECT COUNT(*) FROM auditoria.CargaDocumento)').fetchone()), tuple(counts))
        self.assertEqual(self.con.execute('SELECT DocumentoActualId FROM integracion.Consulta WHERE Id=?', second_job['ConsultaId']).fetchone()[0], second)
        self.assert_reconstruction(second)
        self.delete_with_preview(second)
        self.assertIsNone(self.con.execute('SELECT DocumentoActualId FROM integracion.Consulta WHERE Id=?', second_job['ConsultaId']).fetchone()[0])
        self.assertEqual(self.con.execute('SELECT Estado FROM integracion.Trabajo WHERE Id=?', second_job['Id']).fetchone()[0], 'Cancelado')
        self.assertEqual(service.create_batch('Reimportar documento eliminado', [self.source])['nuevas'], 1)

    def test_reset_clears_operational_tables_and_preserves_accounts_and_audit(self):
        self.require_validation_database()
        doc, _ = self.ingest()
        before = tuple(self.con.execute('SELECT (SELECT COUNT(*) FROM seguridad.Usuario),(SELECT COUNT(*) FROM seguridad.Rol),'
                                       '(SELECT COUNT(*) FROM integracion.Servicio),(SELECT COUNT(*) FROM auditoria.CargaDocumento),'
                                       '(SELECT COUNT(*) FROM seguridad.EventoAcceso)').fetchone())
        self.delete_with_preview()
        from app.model_schema import ENTITIES
        for table in ['integracion.Documento', 'datos.Gasto', 'modelo.Gasto', 'integracion.ObservacionDato',
                      'integracion.Intento', 'integracion.Trabajo', 'integracion.Consulta', 'integracion.Lote',
                      *[f'modelo.[{table}]' for table in ENTITIES]]:
            self.assertEqual(self.con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0], 0, table)
        self.assertEqual(tuple(self.con.execute('SELECT (SELECT COUNT(*) FROM seguridad.Usuario),(SELECT COUNT(*) FROM seguridad.Rol),'
                                               '(SELECT COUNT(*) FROM integracion.Servicio),(SELECT COUNT(*) FROM auditoria.CargaDocumento),'
                                               '(SELECT COUNT(*) FROM seguridad.EventoAcceso)').fetchone()), before)
        audit = self.con.execute("SELECT TOP(1) Antes FROM auditoria.Cambio WHERE Tabla='integracion.Documento' AND RegistroId=0 ORDER BY Id DESC").fetchone()[0]
        self.assertIn('VaciarCargas', audit)
        job = self.new_job()
        new_doc = service.save_response(job, self.data, 'text/xml', 200)
        self.assertGreater(new_doc, doc, 'No reutilizar identidades de la auditoria historica')
        service.persist_records(job, new_doc, self.data)
        self.assert_reconstruction(new_doc)

    def test_deletion_rejects_active_jobs_and_stale_preview(self):
        self.require_validation_database()
        doc, _ = self.ingest()
        scope = {'alcance': 'todo'}
        preview = self.client.post('/mantenimiento/vista-previa', json=scope).json()
        payload = {**scope, 'revision': preview['revision'], 'confirmacion': preview['confirmacion'], 'motivo': 'Prueba de proteccion'}
        service.create_batch('Cambio posterior a vista previa', [self.source])
        self.assertEqual(self.client.post('/mantenimiento/eliminar', json=payload).status_code, 409)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM integracion.Documento WHERE Id=?', doc).fetchone()[0], 1)
        job = self.new_job()
        preview = self.client.post('/mantenimiento/vista-previa', json=scope).json()
        self.assertGreater(preview['trabajos_en_curso'], 0)
        self.assertEqual(self.client.post('/mantenimiento/eliminar', json={**payload, 'revision': preview['revision']}).status_code, 409)
        self.assertEqual(self.con.execute('SELECT Estado FROM integracion.Trabajo WHERE Id=?', job['Id']).fetchone()[0], 'EnCurso')

    def test_document_deletion_rolls_back_if_cleanup_fails(self):
        self.require_validation_database()
        doc, job = self.ingest()
        scope = {'alcance': 'documento', 'documento_id': doc}
        preview = self.client.post('/mantenimiento/vista-previa', json=scope).json()
        with patch('app.maintenance.prune_dimensions', side_effect=RuntimeError('Fallo simulado al limpiar')):
            with self.assertRaisesRegex(RuntimeError, 'Fallo simulado'):
                self.client.post('/mantenimiento/eliminar', json={**scope, 'revision': preview['revision'],
                                  'confirmacion': preview['confirmacion'], 'motivo': 'Comprobar rollback completo'})
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM datos.Gasto WHERE DocumentoId=?', doc).fetchone()[0], 7)
        self.assertEqual(self.con.execute('SELECT DocumentoActualId FROM integracion.Consulta WHERE Id=?', job['ConsultaId']).fetchone()[0], doc)
        self.assertEqual(self.con.execute('SELECT Estado,DocumentoId FROM integracion.Trabajo WHERE Id=?', job['Id']).fetchone()[0], 'Completado')
        self.assert_reconstruction(doc)

    def test_reset_works_with_limited_application_sql_role(self):
        self.require_validation_database()
        self.ingest()
        self.con.execute('CREATE USER ProInXML_TestMantenimiento WITHOUT LOGIN')
        self.con.execute('ALTER ROLE proinxml_app ADD MEMBER ProInXML_TestMantenimiento')
        self.con.execute("EXECUTE AS USER=N'ProInXML_TestMantenimiento'")
        try:
            self.delete_with_preview()
            self.assertEqual(self.con.execute('SELECT COUNT(*) FROM datos.Gasto').fetchone()[0], 0)
            self.assertEqual(self.con.execute('SELECT COUNT(*) FROM integracion.Documento').fetchone()[0], 0)
        finally:
            self.con.execute('REVERT')

    def test_inspection_exposes_quality_value_and_rejected_response_as_text(self):
        self.require_validation_database()
        data = re.sub(rb'<TipoActProy>[23]</TipoActProy>', b'<TipoActProy>4</TipoActProy>', self.data, count=1)
        job = self.new_job()
        doc = service.save_response(job, data, 'text/xml', 200)
        with self.assertRaises(service.QualityError):
            service.persist_records(job, doc, data)
        service.fail_job(job, 'Dato de calidad invalido', retryable=False, document_id=doc, stage='Validacion')
        listing = self.client.get('/documentos?calidad=rechazados').json()
        self.assertIn(doc, [row['Id'] for row in listing['registros']])
        observation = self.client.get(f'/observaciones?documento_id={doc}&severidad=Error').json()['registros'][0]
        detail = self.client.get(f"/documentos/{doc}?ordinal={observation['OrdinalItem']}").json()
        self.assertEqual(detail['registro']['TipoActProy'], 4)
        self.assertIn('<TipoActProy>4</TipoActProy>', detail['original']['texto'])
        self.assertIn(doc, [row['Id'] for row in self.client.get('/documentos?calidad=con_observaciones').json()['registros']])
        self.assertEqual(self.client.get('/reportes/ejecucion?solo_fallos=true').json()['registros'][0]['Estado'], 'Error')
        job2 = self.new_job()
        html = b'<html><script>alert(1)</script>HTTP 500</html>'
        error_doc = service.save_response(job2, html, 'text/html', 500)
        service.fail_job(job2, 'HTTP 500', retryable=False, status=500, document_id=error_doc)
        self.assertIn(error_doc, [row['Id'] for row in self.client.get('/documentos?calidad=errores_http').json()['registros']])
        self.assertEqual(self.client.get(f'/documentos/{error_doc}').json()['original']['texto'], html.decode())
        oversized = gzip.compress(b'a'*70000)
        self.con.execute('UPDATE integracion.Documento SET Respuesta=? WHERE Id=?', oversized, error_doc)
        original = self.client.get(f'/documentos/{error_doc}').json()['original']
        self.assertTrue(original['truncado'])
        self.assertEqual(len(original['texto']), 65536)

    def create_user(self,username,role='Operador'):
        role_id=self.con.execute('SELECT Id FROM seguridad.Rol WHERE Nombre=?',role).fetchone()[0]
        return db.insert_id(self.con,'INSERT seguridad.Usuario(NombreUsuario,NombreCompleto,HashContrasena,RolId) VALUES(?,?,?,?)',
                            username,'Usuario de prueba',password_hash('ClaveDePrueba123'),role_id)

    def test_login_failure_and_permissions_with_real_session(self):
        app.dependency_overrides.clear()
        self.create_user('test_consulta','Consulta')
        bad=self.client.post('/auth/login',json={'usuario':'test_consulta','contrasena':'incorrecta'})
        self.assertEqual(bad.status_code,401,bad.text)
        self.assertEqual(self.con.execute("SELECT TOP(1) Exitoso FROM seguridad.EventoAcceso WHERE NombreIntentado='test_consulta' ORDER BY Id DESC").fetchone()[0],False)
        login=self.client.post('/auth/login',json={'usuario':'test_consulta','contrasena':'ClaveDePrueba123'})
        self.assertEqual(login.status_code,200,login.text)
        headers={'X-CSRF-Token':login.json()['csrf']}
        self.assertEqual(self.client.post('/lotes/urls',json={'urls':[URL]},headers=headers).status_code,403)
        self.assertEqual(self.client.post('/auth/logout',headers=headers).status_code,200)
        self.assertEqual(self.client.get('/auth/me').status_code,401)

    def test_operator_actor_role_and_before_after_are_audited(self):
        app.dependency_overrides.clear()
        user_id=self.create_user('test_operador')
        login=self.client.post('/auth/login',json={'usuario':'test_operador','contrasena':'ClaveDePrueba123'})
        self.assertEqual(login.status_code,200,login.text)
        self.assertEqual(self.client.post('/lotes/urls',json={'urls':[URL]}).status_code,403,'CSRF requerido')
        response=self.client.post('/lotes/urls',json={'urls':[URL]},headers={'X-CSRF-Token':login.json()['csrf']})
        self.assertEqual(response.status_code,201,response.text)
        audit=self.con.execute("SELECT UsuarioId,Actor,Rol,Antes,Despues FROM auditoria.Cambio WHERE Tabla='integracion.Lote' AND RegistroId=?",response.json()['lote_id']).fetchone()
        self.assertEqual(tuple(audit[:3]),(user_id,'test_operador','Operador'))
        self.assertIsNone(audit[3])
        self.assertIn('CreadoPorUsuarioId',audit[4])
        self.assertEqual(self.client.get('/auditoria').status_code,403)

    def test_manual_retry_preserves_attempt_history(self):
        job=self.new_job()
        service.fail_job(job,'Sin red',retryable=False)
        service.schedule_again(job['Id'])
        self.con.execute('UPDATE integracion.Trabajo SET ProximoIntentoUtc=DATEADD(second,-1,SYSUTCDATETIME()) WHERE Id=?',job['Id'])
        second=service.claim_job()
        self.assertNotEqual(second['IntentoId'],job['IntentoId'])
        self.assertEqual(self.con.execute('SELECT Numero FROM integracion.Intento WHERE Id=?',second['IntentoId']).fetchone()[0],2)
        report=self.client.get(f"/reportes/ejecucion?trabajo_id={job['Id']}").json()['registros']
        self.assertIsNone(report[0]['HttpStatus'])

    def test_four_transient_failures_finish_without_invented_http(self):
        job=self.new_job()
        for number in range(1,5):
            self.assertEqual(job['Intentos'],number)
            service.fail_job(job,'Sin conexion',retryable=True)
            state=self.con.execute('SELECT Estado FROM integracion.Trabajo WHERE Id=?',job['Id']).fetchone()[0]
            self.assertEqual(state,'Pendiente' if number<4 else 'Fallido')
            if number<4:
                self.con.execute('UPDATE integracion.Trabajo SET ProximoIntentoUtc=DATEADD(second,-1,SYSUTCDATETIME()) WHERE Id=?',job['Id'])
                job=service.claim_job()
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM integracion.Intento WHERE TrabajoId=? AND HttpStatus IS NULL',job['Id']).fetchone()[0],4)


@unittest.skipUnless(ENABLED and os.getenv('MSSQL_DATABASE')=='ProInXML_Validacion','Concurrencia solo en base aislada')
class ConcurrentQueueTests(unittest.TestCase):
    def test_twenty_downloads_record_real_sql_metrics(self):
        import httpx
        import secrets
        from app.worker import process
        with db.transaction() as con:
            while True:
                base = 2147000000+secrets.randbelow(200000)
                if not con.execute('SELECT COUNT(*) FROM integracion.Consulta WHERE SecEjec BETWEEN ? AND ?',base,base+19).fetchone()[0]:
                    break
        sources = [canonical_source(URL.replace('sec_ejec=3',f'sec_ejec={base+i}')) for i in range(20)]
        batch = service.create_batch('TEST metricas: 20 descargas HTTP simuladas',sources)
        barrier = Barrier(20)
        data = (Path(__file__).parent/'fixtures'/'mef_partial_fixture.xml').read_bytes()
        real_client = httpx.Client
        def handler(request):
            source = canonical_source(str(request.url))
            barrier.wait(timeout=20)
            payload = data.replace(b'<SecEjec>3</SecEjec>',f"<SecEjec>{source['unit']}</SecEjec>".encode())
            return httpx.Response(200,content=payload,headers={'content-type':'text/xml'})
        def consume_one():
            job = service.claim_job(batch['lote_id'])
            self.assertIsNotNone(job)
            process(job,concurrency=20)
        try:
            with patch('app.worker.httpx.Client',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw)):
                with ThreadPoolExecutor(max_workers=20) as pool:
                    futures = [pool.submit(consume_one) for _ in range(20)]
                    for future in futures:
                        future.result(timeout=40)
            with db.transaction() as con:
                found = con.execute('SELECT COUNT(*),SUM(RegistrosInsertados),MIN(Concurrencia),MAX(Concurrencia) '
                                    "FROM analisis.MetricaIntento WHERE LoteId=? AND Estado='Completado'",batch['lote_id']).fetchone()
                self.assertEqual(tuple(found),(20,140,20,20))
                self.assertEqual(con.execute('SELECT COUNT(*) FROM integracion.Trabajo WHERE LoteId=? AND Estado<>?',batch['lote_id'],'Completado').fetchone()[0],0)
            async def reader():return {'Id':1,'NombreUsuario':'qa','Rol':'Consulta'}
            app.dependency_overrides[current_user] = reader
            try:
                with TestClient(app) as client:
                    response = client.get(f"/metricas/resumen?lote_id={batch['lote_id']}")
                    self.assertEqual(response.status_code,200,response.text)
                    summary = response.json()
                    attempts = client.get(f"/metricas/intentos?lote_id={batch['lote_id']}").json()
                evidence = {'modo':'SQL real; 20 HTTP simuladas en paralelo; 7 Items por XML',
                            'lote_id':batch['lote_id'],'resumen':summary,'intentos':attempts}
                target = Path(__file__).resolve().parents[1]/'.runtime'/'qa_metricas_sql.json'
                target.write_text(__import__('json').dumps(evidence,indent=2,default=str),encoding='utf-8')
            finally:
                app.dependency_overrides.clear()
        finally:
            with db.transaction() as con:
                con.execute("UPDATE integracion.Intento SET Estado='Interrumpido',FinUtc=SYSUTCDATETIME() WHERE TrabajoId IN(SELECT Id FROM integracion.Trabajo WHERE LoteId=?) AND Estado='EnCurso'",batch['lote_id'])
                con.execute("UPDATE integracion.Trabajo SET Estado='Cancelado',Token=NULL,LeaseHastaUtc=NULL WHERE LoteId=? AND Estado IN('EnCurso','Pendiente')",batch['lote_id'])

    def test_two_independent_workers_claim_different_jobs(self):
        sources=[canonical_source(URL.replace('sec_ejec=3',f'sec_ejec={unit}')) for unit in (2147482991,2147482992)]
        batch=service.create_batch('TEST concurrencia aislada',sources)
        barrier=Barrier(2)
        def take():
            barrier.wait(timeout=5)
            return service.claim_job()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(take) for _ in range(2)]
                jobs=[f.result(timeout=15) for f in futures]
            self.assertEqual(len({j['Id'] for j in jobs}),2)
            self.assertEqual({j['LoteId'] for j in jobs},{batch['lote_id']})
        finally:
            with db.transaction() as con:
                con.execute("UPDATE integracion.Intento SET Estado='Interrumpido',FinUtc=SYSUTCDATETIME() WHERE TrabajoId IN (SELECT Id FROM integracion.Trabajo WHERE LoteId=?) AND Estado='EnCurso'",batch['lote_id'])
                con.execute("UPDATE integracion.Trabajo SET Estado='Cancelado',Token=NULL,LeaseHastaUtc=NULL,FinalizadoUtc=SYSUTCDATETIME() WHERE LoteId=?",batch['lote_id'])


if __name__=='__main__':unittest.main()
