"""Analisis de etapas y concurrencia a partir de mediciones reales por intento."""
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder

from app.config import settings
from app.db import rows, transaction
from app.explorer import page
from app.metrics import PHASES
from app.security import current_user

router = APIRouter(prefix='/metricas', tags=['Metricas'], dependencies=[Depends(current_user)])


def filters(lote_id, concurrencia, estado):
    conditions, params = [], []
    for column, value in [('LoteId', lote_id), ('Concurrencia', concurrencia), ('Estado', estado)]:
        if value is not None:
            conditions.append(f'm.{column}=?')
            params.append(value)
    return conditions, params


@router.get('/lotes')
def batches():
    with transaction() as con:
        return rows(con.execute(
            'WITH lotes AS(SELECT Id AS LoteId,Nombre FROM integracion.Lote UNION '
            'SELECT LoteId,NombreLote FROM analisis.MetricaIntento) '
            'SELECT TOP(50) LoteId,MAX(Nombre) AS Nombre FROM lotes GROUP BY LoteId ORDER BY LoteId DESC'))


@router.get('/intentos')
def attempts(lote_id: int | None = Query(None, ge=1), concurrencia: int | None = Query(None, ge=1, le=20),
             estado: Literal['EnCurso', 'Completado', 'Error', 'Interrumpido'] | None = None,
             antes_de: int | None = Query(None, ge=1), limite: int = Query(25, ge=1, le=100)):
    conditions, params = filters(lote_id, concurrencia, estado)
    with transaction() as con:
        return page(con, 'analisis.MetricaIntento m', 'm.*', conditions, params, limite, antes_de, descending=True)


@router.get('/resumen')
def summary(lote_id: int | None = Query(None, ge=1), concurrencia: int | None = Query(None, ge=1, le=20),
            estado: Literal['EnCurso', 'Completado', 'Error', 'Interrumpido'] | None = None):
    conditions, params = filters(lote_id, concurrencia, estado)
    where = ' AND '.join(conditions) or '1=1'
    with transaction() as con:
        total = rows(con.execute(
            'SELECT COUNT_BIG(*) AS Intentos, '
            "COALESCE(SUM(CASE WHEN Estado='Completado' THEN 1 ELSE 0 END),0) AS Completados, "
            "COALESCE(SUM(CASE WHEN Estado='Error' THEN 1 ELSE 0 END),0) AS Errores, "
            "COALESCE(SUM(CASE WHEN Estado='Interrumpido' THEN 1 ELSE 0 END),0) AS Interrumpidos, "
            "COALESCE(SUM(CASE WHEN Estado='EnCurso' THEN 1 ELSE 0 END),0) AS EnCurso, "
            'COALESCE(SUM(CONVERT(bigint,RegistrosInsertados)),0) AS FilasInsertadas, '
            'COALESCE(SUM(CONVERT(bigint,RegistrosReutilizados)),0) AS FilasReutilizadas, '
            'COALESCE(SUM(CONVERT(bigint,RegistrosNormalizados)),0) AS FilasNormalizadas, '
            'COALESCE(SUM(BytesRecibidos),0) AS BytesRecibidos,MIN(InicioUtc) AS InicioUtc, '
            'MAX(COALESCE(FinUtc,SYSUTCDATETIME())) AS FinVentanaUtc, '
            'DATEDIFF_BIG(millisecond,MIN(InicioUtc),MAX(COALESCE(FinUtc,SYSUTCDATETIME()))) AS VentanaMs '
            f'FROM analisis.MetricaIntento m WHERE {where}', *params))[0]
        values = ','.join(f"('{field}',m.[{field}])" for field, _, _ in [*PHASES, ('TotalMs', '', '')])
        phase_rows = rows(con.execute(
            f'WITH fases AS(SELECT v.Campo,v.Ms FROM analisis.MetricaIntento m '
            f'CROSS APPLY(VALUES{values}) v(Campo,Ms) WHERE {where} AND m.MedicionFinalizada=1 AND v.Ms IS NOT NULL) '
            'SELECT DISTINCT Campo,COUNT_BIG(*) OVER(PARTITION BY Campo) AS Muestras, '
            'AVG(CONVERT(float,Ms)) OVER(PARTITION BY Campo) AS PromedioMs, '
            'MAX(Ms) OVER(PARTITION BY Campo) AS MaximoMs, '
            'PERCENTILE_CONT(0.95) WITHIN GROUP(ORDER BY Ms) OVER(PARTITION BY Campo) AS P95Ms '
            'FROM fases', *params))
        comparisons = rows(con.execute(
            'SELECT m.Concurrencia,COUNT_BIG(*) AS Intentos, '
            "SUM(CASE WHEN Estado='Completado' THEN 1 ELSE 0 END) AS Completados, "
            "SUM(CASE WHEN Estado IN('Error','Interrumpido') THEN 1 ELSE 0 END) AS Fallos, "
            'SUM(CONVERT(bigint,RegistrosInsertados)) AS FilasInsertadas, '
            'AVG(CASE WHEN MedicionFinalizada=1 THEN CONVERT(float,TotalMs) END) AS PromedioMs, '
            'DATEDIFF_BIG(millisecond,MIN(InicioUtc),MAX(COALESCE(FinUtc,SYSUTCDATETIME()))) AS VentanaMs '
            f'FROM analisis.MetricaIntento m WHERE {where} GROUP BY m.Concurrencia ORDER BY m.Concurrencia', *params))
        slow = rows(con.execute('SELECT TOP(5) Id,IntentoId,DocumentoId,LoteId,Concurrencia,Estado,RegistrosLeidos,TotalMs,UrlSolicitada '
                                f'FROM analisis.MetricaIntento m WHERE {where} AND MedicionFinalizada=1 ORDER BY TotalMs DESC,Id DESC', *params))
        legacy = con.execute('SELECT COUNT_BIG(*) FROM integracion.Intento a JOIN integracion.Trabajo t ON t.Id=a.TrabajoId '
                             'WHERE NOT EXISTS(SELECT 1 FROM analisis.MetricaIntento m WHERE m.IntentoId=a.Id) '
                             'AND (? IS NULL OR t.LoteId=?)', lote_id, lote_id).fetchone()[0]
    def rates(item):
        seconds = (item['VentanaMs'] or 0)/1000
        item['XmlPorMinuto'] = round(item['Completados']*60/seconds, 3) if seconds > 0 else None
        item['FilasPorSegundo'] = round(item['FilasInsertadas']/seconds, 3) if seconds > 0 else None
    rates(total)
    for item in comparisons:
        rates(item)
    measured = {row['Campo']: row for row in phase_rows}
    phases = [dict(Campo=field, Nombre=label, Color=color, Muestras=0, PromedioMs=None, P95Ms=None, MaximoMs=None)
              | measured.get(field, {}) for field, label, color in PHASES]
    result = {'resumen': total, 'fases': phases, 'total_intento': measured.get('TotalMs'),
              'comparacion': comparisons, 'lentos': slow, 'intentos_sin_medicion': legacy,
              'concurrencia_configurada': settings.worker_concurrency,
              'nota': 'NULL significa etapa no ejecutada. Las fases y P95 usan solo mediciones finalizadas. '
                      'El rendimiento usa tiempo de pared e incluye esperas entre intentos; los tiempos de las fases no se suman entre workers para calcularlo.'}
    return jsonable_encoder(result, custom_encoder={Decimal: float})
