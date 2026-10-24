"""Worker con descargas concurrentes y cola durable en SQL Server."""

from concurrent.futures import ThreadPoolExecutor
import logging
from threading import Event, Lock
import time
from xml.etree.ElementTree import ParseError

import httpx
from defusedxml.common import DefusedXmlException

from app.config import settings
from app.metrics import AttemptMetrics
from app.service import claim_job, fail_job, persist_records, save_response

log = logging.getLogger("proinxml.worker")


class Circuit:
    def __init__(self):
        self.guard = Lock()
        self.failures = 0
        self.until = 0.0

    def available(self):
        with self.guard:
            return time.monotonic() >= self.until

    def result(self, failed):
        with self.guard:
            self.failures = self.failures + 1 if failed else 0
            if self.failures >= settings.circuit_failures:
                self.until = time.monotonic() + settings.circuit_pause_seconds
                self.failures = 0
                log.warning(
                    "Pausa automatica del servicio durante %s segundos",
                    settings.circuit_pause_seconds,
                )


circuit = Circuit()


def process(job: dict, *, concurrency=None):
    document_id = status = None
    stage = "Descarga"
    meter = AttemptMetrics(job, concurrency)
    meter.save()
    outcome, metric_error = "Error", None
    try:
        deadline = time.monotonic() + 180
        with meter.phase("DescargaMs"):
            with httpx.Client(
                timeout=httpx.Timeout(45, connect=10),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream("GET", job["Url"]) as response:
                    status = meter.status = response.status_code
                    content_type = response.headers.get("content-type", "")
                    payload = bytearray()
                    for chunk in response.iter_bytes():
                        meter.bytes += len(chunk)
                        if len(payload) + len(chunk) > settings.max_xml_bytes:
                            raise ValueError(
                                "Respuesta excede MAX_XML_BYTES; revisar antes de reintentar."
                            )
                        if time.monotonic() > deadline:
                            raise httpx.ReadTimeout("Descarga excede 180 segundos.")
                        payload.extend(chunk)
                    data = bytes(payload)
        del payload
        stage = "Persistencia"
        with meter.phase("OriginalMs"):
            document_id = save_response(job, data, content_type, status)
        meter.document_id = document_id
        meter.save()
        if status != 200:
            meter.stage = "Descarga"
            transient = status in (408, 429) or status >= 500
            circuit.result(transient)
            metric_error = f"HTTP {status}"
            fail_job(
                job,
                metric_error,
                retryable=transient,
                status=status,
                document_id=document_id,
                stage="Descarga",
            )
            return
        circuit.result(False)
        stage = "Validacion"
        count = persist_records(job, document_id, data, meter=meter)
        outcome = "Completado"
        log.info("Trabajo %s completado: %s registros", job["Id"], count)
    except (ValueError, ParseError, DefusedXmlException) as exc:
        metric_error = exc
        fail_job(
            job,
            str(exc),
            retryable=False,
            status=status,
            document_id=document_id,
            stage=stage,
        )
    except httpx.HTTPError as exc:
        metric_error = exc
        circuit.result(True)
        fail_job(
            job,
            f"{type(exc).__name__}: {exc}",
            retryable=True,
            status=status,
            document_id=document_id,
            stage="Descarga",
        )
    except Exception as exc:
        metric_error = exc
        log.exception("Error de persistencia en trabajo %s", job["Id"])
        # Si SQL no esta disponible tampoco se podra marcar el fallo; el lease lo recuperara.
        fail_job(
            job,
            f"{type(exc).__name__}: {exc}",
            retryable=True,
            status=status,
            document_id=document_id,
            stage="Persistencia",
        )
    finally:
        meter.finish(outcome, metric_error)


def consume(stop: Event):
    while not stop.is_set():
        try:
            if not circuit.available():
                stop.wait(1)
                continue
            job = claim_job()
            if job is None:
                stop.wait(settings.poll_seconds)
            else:
                process(job)
        except Exception:
            log.exception(
                "Worker interrumpido; la cola conserva el trabajo para recuperarlo"
            )
            stop.wait(5)


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    stop = Event()
    with ThreadPoolExecutor(
        max_workers=settings.worker_concurrency, thread_name_prefix="mef"
    ) as pool:
        futures = [
            pool.submit(consume, stop) for _ in range(settings.worker_concurrency)
        ]
        log.info(
            "Worker iniciado: %s descargas simultaneas", settings.worker_concurrency
        )
        try:
            while not stop.wait(1):
                for future in futures:
                    if future.done():
                        future.result()
        except KeyboardInterrupt:
            log.info("Deteniendo worker; las transacciones en curso terminan primero")
        finally:
            stop.set()


if __name__ == "__main__":
    main()
