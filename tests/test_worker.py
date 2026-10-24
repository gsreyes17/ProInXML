import unittest
from unittest.mock import ANY, patch

import httpx
from app import worker


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.job={'Id':1,'Url':'http://s3.mef.gob.pe/example','Intentos':1,'Token':'test'}
        self.real_client=httpx.Client
        self.patches=[patch('app.worker.save_response',return_value=5),patch('app.worker.persist_records',return_value=0),
                      patch('app.worker.fail_job'),patch('app.worker.circuit',worker.Circuit()),patch('app.metrics.AttemptMetrics.save')]
        self.saved,self.persisted,self.failed,_,self.metric_saved=[p.start() for p in self.patches]

    def tearDown(self):
        for p in reversed(self.patches):p.stop()

    def request(self,handler):
        transport=httpx.MockTransport(handler)
        with patch('app.worker.httpx.Client',side_effect=lambda **kw:self.real_client(transport=transport,**kw)):
            worker.process(self.job)

    def test_http_503_is_preserved_and_retryable(self):
        self.request(lambda req:httpx.Response(503,content=b'servicio no disponible'))
        self.saved.assert_called_once()
        self.assertTrue(self.failed.call_args.kwargs['retryable'])
        self.assertEqual(self.failed.call_args.kwargs['status'],503)
        self.persisted.assert_not_called()

    def test_network_failure_never_invents_http_status(self):
        def timeout(req):raise httpx.ConnectTimeout('sin conexion')
        self.request(timeout)
        self.saved.assert_not_called()
        self.assertIsNone(self.failed.call_args.kwargs['status'])
        self.assertTrue(self.failed.call_args.kwargs['retryable'])

    def test_valid_response_is_persisted(self):
        self.request(lambda req:httpx.Response(200,content=b'<DataGasto/>'))
        self.persisted.assert_called_once_with(self.job,5,b'<DataGasto/>',meter=ANY)
        meter=self.persisted.call_args.kwargs['meter']
        self.assertEqual(meter.state,'Completado')
        self.assertIn('DescargaMs',meter.times)
        self.assertIn('OriginalMs',meter.times)
        self.assertIn('TotalMs',meter.times)
        self.failed.assert_not_called()

    def test_validation_failure_has_stage_and_original_status(self):
        self.persisted.side_effect=ValueError('XML invalido')
        self.request(lambda req:httpx.Response(200,content=b'invalido'))
        self.assertEqual(self.failed.call_args.kwargs['stage'],'Validacion')
        self.assertEqual(self.failed.call_args.kwargs['status'],200)
        self.assertFalse(self.failed.call_args.kwargs['retryable'])

    def test_circuit_pauses_after_configured_failure_streak(self):
        circuit=worker.Circuit()
        for _ in range(worker.settings.circuit_failures):circuit.result(True)
        self.assertFalse(circuit.available())

    def test_twenty_workers_are_supported(self):
        from app.config import Settings
        self.assertEqual(Settings(worker_concurrency=20).worker_concurrency,20)
        with self.assertRaises(ValueError):Settings(worker_concurrency=21)
