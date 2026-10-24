"""Carga sintetica con SQL real y transporte HTTP simulado, solo en ProInXML_Validacion.

No contacta al MEF. Cada respuesta tiene un Item adaptado a los parametros de su URL.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
from threading import Lock
import time
from unittest.mock import patch
import xml.etree.ElementTree as ET

import httpx
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.db import rows,transaction
from app.service import claim_job,create_batch
from app.worker import process
from app.xml_reader import FIELDS,NS,canonical_source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cantidad',type=int,default=100)
    parser.add_argument('--concurrencia',type=int,default=20)
    args=parser.parse_args()
    if os.getenv('MSSQL_DATABASE')!='ProInXML_Validacion':
        parser.error('Define MSSQL_DATABASE=ProInXML_Validacion para aislar la prueba.')
    if not 1<=args.cantidad<=5655 or not 1<=args.concurrencia<=20:
        parser.error('Cantidad: 1 a 5655; concurrencia: 1 a 20.')
    book=load_workbook(ROOT/'XML_models'/'URLs.xlsx',read_only=True,data_only=True)
    try:
        urls=[str(row[0]) for row in book['XML'].iter_rows(min_row=2,values_only=True) if row and row[0]][:args.cantidad]
    finally:book.close()
    sources=[canonical_source(url) for url in urls]
    sample=ET.fromstring((ROOT/'tests/fixtures/mef_partial_fixture.xml').read_bytes())
    template=ET.tostring(sample[0],encoding='utf-8')
    calls=Counter();guard=Lock()
    real_client=httpx.Client
    def handler(request):
        source=canonical_source(str(request.url))
        with guard:
            calls[str(request.url)]+=1
            number=calls[str(request.url)]
        # Comprueba recuperacion de un HTTP transitorio en una fraccion de las URLs.
        if source['unit']%97==0 and number==1:
            return httpx.Response(503,content=b'fallo transitorio simulado')
        item=ET.fromstring(template)
        for field,value in [('AnoEje',source['year']),('IdNivelGobierno',source['level']),('SecEjec',source['unit'])]:
            item.find('{'+NS+'}'+field).text=str(value)
        if source['unit']%10==0:item.find('{'+NS+'}Unidad_Medida').text=None
        root=ET.Element('{'+NS+'}DataGasto');root.append(item)
        return httpx.Response(200,content=ET.tostring(root,encoding='utf-8'),headers={'content-type':'text/xml'})
    transport=httpx.MockTransport(handler)
    started=time.monotonic()
    batch=create_batch(f'TEST sintetico {args.cantidad} URLs',sources)
    registration=time.monotonic()-started
    # Simula un corte despues de tomar un trabajo y antes de recibir respuesta.
    abandoned=claim_job(batch['lote_id'])
    if abandoned:
        with transaction() as con:
            con.execute('UPDATE integracion.Trabajo SET LeaseHastaUtc=DATEADD(second,-1,SYSUTCDATETIME()) WHERE Id=?',abandoned['Id'])
    def consume():
        while True:
            job=claim_job(batch['lote_id'])
            if job is None:
                return
            process(job,concurrency=args.concurrencia)
            # Acelera solo el reloj de reintentos de esta prueba: no cambia la politica del worker.
            with transaction() as con:
                con.execute("UPDATE integracion.Trabajo SET ProximoIntentoUtc=DATEADD(second,-1,SYSUTCDATETIME()) "
                            "WHERE LoteId=? AND Estado='Pendiente' AND Intentos>0 AND ProximoIntentoUtc>SYSUTCDATETIME()",batch['lote_id'])
    with patch('app.worker.httpx.Client',side_effect=lambda **kw:real_client(transport=transport,**kw)):
        with ThreadPoolExecutor(max_workers=args.concurrencia) as pool:
            futures=[pool.submit(consume) for _ in range(args.concurrencia)]
            for future in futures:future.result()
    duration=time.monotonic()-started
    repeated=create_batch('TEST repeticion sin descarga',sources)
    columns=','.join('['+f+']' for f in FIELDS)
    with transaction() as con:
        states=rows(con.execute('SELECT Estado,COUNT(*) AS Cantidad FROM integracion.Trabajo WHERE LoteId=? GROUP BY Estado',batch['lote_id']))
        differences=con.execute(f'SELECT COUNT(*) FROM (SELECT Id,{columns} FROM datos.Gasto EXCEPT SELECT Id,{columns} FROM modelo.GastoReconstruido) x').fetchone()[0]
        metrics=rows(con.execute('SELECT Estado,COUNT(*) AS Cantidad FROM integracion.Intento WHERE TrabajoId IN '
                                '(SELECT Id FROM integracion.Trabajo WHERE LoteId=?) GROUP BY Estado',batch['lote_id']))
        size=con.execute("SELECT SUM(reserved_page_count)*8.0/1024 FROM sys.dm_db_partition_stats").fetchone()[0]
    result={'modo':'HTTP simulado; SQL Server real','cantidad':len(sources),'concurrencia':args.concurrencia,
            'lote':batch,'segundos_registro':round(registration,3),'segundos_total':round(duration,3),
            'solicitudes_simuladas':sum(calls.values()),'estados':states,'intentos':metrics,
            'repeticion_ya_cargadas':repeated['ya_cargadas'],'diferencias_modelo':differences,'espacio_reservado_mib':str(size)}
    path=ROOT/'.runtime'/f'carga_local_{args.cantidad}.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)
    if differences or repeated['ya_cargadas']!=len({(s['year'],s['level'],s['unit']) for s in sources}):
        raise RuntimeError('La prueba no completo todas las consultas o no conserva la integridad.')


if __name__=='__main__':main()
