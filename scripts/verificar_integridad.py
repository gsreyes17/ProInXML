"""Comprueba originales, compresion, SHA-256, vistas y reconstruccion del modelo."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.db import rows,transaction
from app.xml_reader import FIELDS


def verify():
    columns=','.join('['+f+']' for f in FIELDS)
    with transaction(actor='verificacion-integridad') as con:
        summary={
            'tablas':con.execute("SELECT COUNT(*) FROM sys.tables WHERE SCHEMA_NAME(schema_id) IN('integracion','datos','modelo','catalogo','seguridad','auditoria','analisis')").fetchone()[0],
            'documentos_validos':con.execute('SELECT COUNT(*) FROM integracion.Documento WHERE EsValido=1').fetchone()[0],
            'gastos':con.execute('SELECT COUNT_BIG(*) FROM datos.Gasto').fetchone()[0],
            'gastos_modelo':con.execute('SELECT COUNT_BIG(*) FROM modelo.Gasto').fetchone()[0],
            'unidades_null':con.execute('SELECT COUNT(*) FROM datos.Gasto WHERE Unidad_Medida IS NULL').fetchone()[0],
            'observaciones':con.execute('SELECT COUNT(*) FROM integracion.ObservacionDato').fetchone()[0],
            'columnas_vista_xml':len(con.execute('SELECT TOP(0) * FROM datos.vw_GastoXML').description),
            'diferencias_modelo':con.execute(f'SELECT COUNT(*) FROM (SELECT Id,{columns} FROM datos.Gasto g '
                f'WHERE EXISTS(SELECT 1 FROM integracion.Documento d WHERE d.Id=g.DocumentoId AND d.EsValido=1) '
                f'EXCEPT SELECT Id,{columns} FROM modelo.GastoReconstruido) x').fetchone()[0],
            'diferencias_modelo_inversas':con.execute(f'SELECT COUNT(*) FROM (SELECT Id,{columns} FROM modelo.GastoReconstruido '
                f'EXCEPT SELECT Id,{columns} FROM datos.Gasto) x').fetchone()[0],
            'estados':rows(con.execute('SELECT Estado,COUNT(*) AS Cantidad FROM integracion.Trabajo GROUP BY Estado')),
            'archivos_bd':rows(con.execute('SELECT name,type_desc,size*8.0/1024 AS TamanoMiB FROM sys.database_files')),
        }
        documents=rows(con.execute('SELECT Id,Sha256,Respuesta FROM integracion.Documento ORDER BY Id'))
    original=compressed=0
    bad_hash=[]
    for document in documents:
        data=gzip.decompress(document['Respuesta'])
        original+=len(data);compressed+=len(document['Respuesta'])
        if hashlib.sha256(data).hexdigest()!=document['Sha256'].lower():
            bad_hash.append(document['Id'])
    summary.update(documentos=len(documents),bytes_xml_originales=original,bytes_xml_comprimidos=compressed,
                   documentos_huella_incorrecta=bad_hash)
    if summary['diferencias_modelo'] or summary['diferencias_modelo_inversas'] or bad_hash or summary['columnas_vista_xml']!=39:
        raise ValueError(f'Fallo de integridad: {summary}')
    return summary


if __name__=='__main__':
    result=verify()
    path=ROOT/'.runtime'/'validacion_actual.json';path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,default=str))
