"""Tiempos monotónicos por intento; se guardan aparte del trabajo transaccional."""

from contextlib import contextmanager, nullcontext
from decimal import Decimal
import logging
from time import perf_counter_ns

from app.infrastructure.config import settings
from app.infrastructure.db import transaction

log = logging.getLogger("proinxml.metricas")
PHASES = (
    ("DescargaMs", "Descarga", "#2563eb"),
    ("OriginalMs", "Guardar original", "#0891b2"),
    ("EsperaSQLMs", "Espera de bloqueos SQL", "#d97706"),
    ("ValidacionMs", "Lectura y validación", "#7c3aed"),
    ("InsercionMs", "Inserción del detalle", "#0f766e"),
    ("NormalizacionMs", "Normalización", "#be185d"),
    ("ConfirmacionMs", "Confirmación SQL", "#475569"),
)
TIME_FIELDS = [field for field, _, _ in PHASES] + ["TotalMs"]


def milliseconds(nanoseconds):
    return (Decimal(nanoseconds) / Decimal(1_000_000)).quantize(Decimal("0.001"))


def timing(meter, field):
    return meter.phase(field) if meter is not None else nullcontext()


class AttemptMetrics:
    def __init__(self, job, concurrency=None):
        self.job = job
        self.concurrency = (
            concurrency if concurrency is not None else settings.worker_concurrency
        )
        self.started = perf_counter_ns()
        self.times = {}
        self.bytes = self.read = self.inserted = self.reused = self.normalized = 0
        self.document_id = self.status = None
        self.state, self.stage, self.error = "EnCurso", "Descarga", None
        self.finished = False

    @contextmanager
    def phase(self, field):
        self.stage = next(label for key, label, _ in PHASES if key == field)
        start = perf_counter_ns()
        try:
            yield
        finally:
            self.add(field, perf_counter_ns() - start)

    def add(self, field, nanoseconds):
        self.times[field] = self.times.get(field, Decimal(0)) + milliseconds(
            nanoseconds
        )

    def finish(self, state, error=None):
        self.state, self.error, self.finished = (
            state,
            str(error)[:2000] if error else None,
            True,
        )
        self.times["TotalMs"] = milliseconds(perf_counter_ns() - self.started)
        if state == "Completado":
            self.stage = "Finalizado"
        self.save()

    def save(self):
        # Un fallo de observabilidad nunca convierte una carga correcta en fallida.
        try:
            with transaction(
                actor="sistema", correlation=str(self.job["Token"])
            ) as con:
                con.execute(
                    "IF NOT EXISTS(SELECT 1 FROM analisis.MetricaIntento WHERE IntentoId=?) "
                    "INSERT analisis.MetricaIntento(IntentoId,TrabajoId,LoteId,NombreLote,URLSolicitada,AnoEje,SecEjec,Concurrencia) "
                    "SELECT ?,?,?,Nombre,?,?,?,? FROM integracion.Lote WHERE Id=?",
                    self.job["IntentoId"],
                    self.job["IntentoId"],
                    self.job["Id"],
                    self.job["LoteId"],
                    self.job["URL"],
                    self.job["AnoEje"],
                    self.job["SecEjec"],
                    self.concurrency,
                    self.job["LoteId"],
                )
                assignments = ",".join(f"[{field}]=?" for field in TIME_FIELDS)
                con.execute(
                    "UPDATE analisis.MetricaIntento SET DocumentoId=?,HTTPStatus=?,BytesRecibidos=?,Estado=?,Etapa=?,Error=?, "
                    "RegistrosLeidos=?,RegistrosInsertados=?,RegistrosReutilizados=?,RegistrosNormalizados=?, "
                    f"{assignments},MedicionFinalizada=?,FinUTC=CASE WHEN ?=1 THEN SYSUTCDATETIME() ELSE NULL END "
                    "WHERE IntentoId=? AND Estado='EnCurso'",
                    self.document_id,
                    self.status,
                    self.bytes,
                    self.state,
                    self.stage,
                    self.error,
                    self.read,
                    self.inserted,
                    self.reused,
                    self.normalized,
                    *(self.times.get(field) for field in TIME_FIELDS),
                    int(self.finished),
                    int(self.finished),
                    self.job["IntentoId"],
                )
        except Exception:
            log.warning(
                "No se pudieron guardar las metricas del intento %s",
                self.job.get("IntentoId"),
                exc_info=True,
            )


def close_interrupted(con):
    con.execute(
        "IF OBJECT_ID(N'analisis.MetricaIntento',N'U') IS NOT NULL "
        "UPDATE m SET Estado='Interrumpido',Etapa=N'Interrumpido',FinUTC=a.FinUTC,Error=a.Error,"
        "TotalMs=CONVERT(decimal(19,3),DATEDIFF_BIG(millisecond,m.InicioUTC,a.FinUTC)) "
        "FROM analisis.MetricaIntento m JOIN integracion.Intento a ON a.Id=m.IntentoId "
        "WHERE m.Estado='EnCurso' AND a.Estado='Interrumpido'"
    )
