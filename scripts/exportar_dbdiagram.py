"""Exporta metadatos de SQL Server a DBML, sin leer registros ni credenciales."""
import argparse
from collections import OrderedDict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.db import rows, transaction
from app.model_schema import ENTITIES

SCHEMAS = "('integracion','datos','modelo','catalogo','seguridad','auditoria','analisis')"
GROUPS = OrderedDict([
    ('Sistema', ('#2563EB', 'Usuarios, roles y configuracion del servicio.')),
    ('Integracion_y_cola', ('#0F766E', 'Lotes, consultas, trabajos e intentos de descarga.')),
    ('XML_y_calidad', ('#EA580C', 'Original recibido, detalle de 39 campos y observaciones.')),
    ('Auditoria', ('#7C3AED', 'Bitacoras inmutables de cambios, cargas y accesos.')),
    ('Analisis', ('#0369A1', 'Mediciones de tiempos, rendimiento y concurrencia por intento.')),
    ('Catalogo', ('#475569', 'Valores permitidos del tipo de actividad o proyecto.')),
    ('Modelo_gasto', ('#166534', 'Hecho normalizado con la misma identidad que el detalle XML.')),
    ('Modelo_instituciones', ('#0284C7', 'Gobierno, sector, pliego y ejecutora por ejercicio.')),
    ('Modelo_presupuesto', ('#0D9488', 'Funcion, programas y categoria de gasto.')),
    ('Modelo_clasificadores', ('#4F46E5', 'Jerarquia del clasificador de gasto.')),
    ('Modelo_financiamiento', ('#B45309', 'Fuente, rubro y tipo de recurso.')),
    ('Modelo_proyectos_y_metas', ('#BE185D', 'Proyecto, componente, finalidad, metas y unidad de medida opcional.')),
    ('Modelo_ubicaciones', ('#4338CA', 'Departamento, provincia y distrito.')),
])
MODEL_GROUP = {'Instituciones': 'Modelo_instituciones', 'Presupuesto': 'Modelo_presupuesto',
               'Clasificadores': 'Modelo_clasificadores', 'Financiamiento': 'Modelo_financiamiento',
               'Proyectos y metas': 'Modelo_proyectos_y_metas', 'Ubicaciones': 'Modelo_ubicaciones'}
NOTES = {
    'analisis.MetricaIntento': 'Una medicion por intento; fases en milisegundos con tres decimales. NULL significa etapa no ejecutada. Filas insertadas solo tras commit. Los IDs de lote, trabajo, intento y documento son historicos SIN FK; las metricas sobreviven a la limpieza. Concurrencia es la configurada por el worker, no una medicion instantanea de actividad.',
    'integracion.Documento': 'Respuesta original gzip y SHA-256 de los bytes originales. Puede contener un XML rechazado o una respuesta HTTP de error.',
    'datos.Gasto': 'Detalle persistente de los 39 campos XML mas identidad, documento, ordinal y fecha. AnoEje conserva el nombre XML. Unidad_Medida admite NULL.',
    'integracion.ObservacionDato': 'Documento y ordinal del Item observado. Advertencias no bloquean; errores de calidad impiden publicar.',
    'integracion.Consulta': 'URL canonica y parametros de negocio. DocumentoActualId publica la version vigente de esta misma consulta.',
    'integracion.Trabajo': 'Cola persistente por lote y consulta. Reintentos, lease, token y estado.',
    'integracion.Intento': 'HTTP, inicio/fin, etapa, error y conteos de cada intento. HTTP NULL significa que no hubo respuesta.',
    'auditoria.Cambio': 'Inmutable. Antes/Despues en JSON, usuario, actor, rol y correlacion. RegistroId=0 en integracion.Documento identifica un vaciado global.',
    'auditoria.CargaDocumento': 'Inmutable. DocumentoId y LoteId son identificadores historicos SIN FK, para conservar auditoria tras eliminar cargas. UsuarioId mantiene su FK.',
    'seguridad.EventoAcceso': 'Inmutable. Historial de autenticacion y gestion de cuentas.',
    'seguridad.Usuario': 'Hash Argon2, nunca contrasenas en claro. La cuenta sistema identifica al worker y no permite login.',
    'modelo.Gasto': 'Hecho normalizado. Su Id tambien es FK a datos.Gasto.Id; representa una relacion 1 a 0..1, pues un detalle rechazado no se normaliza.',
    'modelo.Meta': 'UnidadMedidaId es opcional. La clave natural incluye ese valor nulo segun las reglas de SQL Server.',
}


def quoted(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n') + "'"


def identifier(value):
    return '"' + value.replace('"', '\\"') + '"'


def qualified(schema, table):
    return f'{identifier(schema)}.{identifier(table)}'


def group_for(schema, table):
    if schema == 'analisis':
        return 'Analisis'
    if schema == 'auditoria' or (schema == 'seguridad' and table == 'EventoAcceso'):
        return 'Auditoria'
    if schema == 'seguridad' or table == 'Servicio':
        return 'Sistema'
    if schema == 'datos' or table in ('Documento', 'ObservacionDato'):
        return 'XML_y_calidad'
    if schema == 'integracion':
        return 'Integracion_y_cola'
    if schema == 'catalogo':
        return 'Catalogo'
    return 'Modelo_gasto' if table == 'Gasto' else MODEL_GROUP[ENTITIES[table][0]]


def sql_type(column):
    name, size = column['Tipo'], column['Longitud']
    if name in ('varchar', 'char', 'nvarchar', 'nchar', 'binary', 'varbinary'):
        length = 'max' if size == -1 else str(size//2 if name.startswith('n') else size)
        return f'{name}({length})'
    if name in ('decimal', 'numeric'):
        return f"{name}({column['Precision']},{column['Escala']})"
    if name in ('datetime2', 'datetimeoffset', 'time'):
        return f"{name}({column['Escala']})"
    return name


def export(output):
    with transaction(actor='exportacion-diagrama') as con:
        database = con.execute('SELECT DB_NAME()').fetchone()[0]
        tables = rows(con.execute(f'SELECT t.object_id AS Id,s.name AS Esquema,t.name AS Tabla FROM sys.tables t '
                                  f'JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE s.name IN {SCHEMAS} ORDER BY s.name,t.name'))
        columns = rows(con.execute(f'SELECT c.object_id AS TablaId,c.column_id AS Orden,c.name AS Columna,ty.name AS Tipo,'
                                   'c.max_length AS Longitud,c.precision AS Precision,c.scale AS Escala,c.is_nullable AS Nulo,'
                                   'c.is_identity AS Identidad,d.definition AS Predeterminado FROM sys.columns c '
                                   'JOIN sys.types ty ON ty.user_type_id=c.user_type_id '
                                   'JOIN sys.tables t ON t.object_id=c.object_id JOIN sys.schemas s ON s.schema_id=t.schema_id '
                                   f'LEFT JOIN sys.default_constraints d ON d.object_id=c.default_object_id WHERE s.name IN {SCHEMAS} '
                                   'ORDER BY c.object_id,c.column_id'))
        keys = rows(con.execute('SELECT i.object_id AS TablaId,i.index_id AS IndiceId,i.name AS Nombre,i.is_primary_key AS Primaria,'
                                'ic.key_ordinal AS Orden,c.name AS Columna FROM sys.indexes i '
                                'JOIN sys.tables t ON t.object_id=i.object_id JOIN sys.schemas s ON s.schema_id=t.schema_id '
                                'JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id AND ic.key_ordinal>0 '
                                'JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id '
                                f'WHERE s.name IN {SCHEMAS} AND i.is_unique=1 AND i.has_filter=0 ORDER BY i.object_id,i.index_id,ic.key_ordinal'))
        references = rows(con.execute('SELECT f.object_id AS Id,f.name AS Nombre,ps.name AS EsquemaOrigen,pt.name AS TablaOrigen,'
                                      'pc.name AS ColumnaOrigen,rs.name AS EsquemaDestino,rt.name AS TablaDestino,rc.name AS ColumnaDestino,'
                                      'k.constraint_column_id AS Orden FROM sys.foreign_keys f '
                                      'JOIN sys.foreign_key_columns k ON k.constraint_object_id=f.object_id '
                                      'JOIN sys.tables pt ON pt.object_id=f.parent_object_id JOIN sys.schemas ps ON ps.schema_id=pt.schema_id '
                                      'JOIN sys.tables rt ON rt.object_id=f.referenced_object_id JOIN sys.schemas rs ON rs.schema_id=rt.schema_id '
                                      'JOIN sys.columns pc ON pc.object_id=pt.object_id AND pc.column_id=k.parent_column_id '
                                      'JOIN sys.columns rc ON rc.object_id=rt.object_id AND rc.column_id=k.referenced_column_id '
                                      f'WHERE ps.name IN {SCHEMAS} AND rs.name IN {SCHEMAS} ORDER BY f.object_id,k.constraint_column_id'))
        checks = rows(con.execute('SELECT ch.parent_object_id AS TablaId,ch.name AS Nombre,ch.definition AS Expresion '
                                 'FROM sys.check_constraints ch JOIN sys.tables t ON t.object_id=ch.parent_object_id '
                                 f'JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE s.name IN {SCHEMAS} ORDER BY ch.parent_object_id,ch.name'))
    lines = ['// Generado desde metadatos de SQL Server; sin registros ni credenciales.',
             '// Copiar TODO este archivo en el editor DBML de dbdiagram.io.',
             '// PK, identidad, nulabilidad, tipos, valores por defecto, claves unicas, checks y FK fisicas.',
             '// No incluye vistas, procedimientos, triggers ni indices no unicos.',
             f'Project {identifier(database)} {{', "  database_type: 'MSSQL'",
             "  Note: 'ProInXML: XML original, detalle, modelo normalizado, cola, sistema y auditoria. Las sesiones actuales viven en memoria de FastAPI.'", '}', '']
    members = {name: [] for name in GROUPS}
    for table in tables:
        table_id, schema, name = table['Id'], table['Esquema'], table['Tabla']
        full = qualified(schema, name)
        group = group_for(schema, name)
        members[group].append(full)
        table_keys = OrderedDict()
        for key in keys:
            if key['TablaId'] == table_id:
                table_keys.setdefault(key['IndiceId'], []).append(key)
        pk = next((items for items in table_keys.values() if items[0]['Primaria']), [])
        lines.append(f'Table {full} [headercolor: {GROUPS[group][0]}] {{')
        for column in (c for c in columns if c['TablaId'] == table_id):
            options = ['null' if column['Nulo'] else 'not null']
            if len(pk) == 1 and pk[0]['Columna'] == column['Columna']:
                options.insert(0, 'pk')
            if column['Identidad']:
                options.append('increment')
            if column['Predeterminado']:
                options.append('default: `' + column['Predeterminado'].replace('`', '') + '`')
            if schema == 'auditoria' and name == 'CargaDocumento' and column['Columna'] in ('DocumentoId', 'LoteId'):
                options.append("note: 'Identificador historico; no es FK tras la migracion 005.'")
            lines.append(f"  {identifier(column['Columna'])} {sql_type(column)} [{', '.join(options)}]")
        indexes = [items for items in table_keys.values() if not items[0]['Primaria'] or len(items)>1]
        if indexes:
            lines.append('  indexes {')
            for items in indexes:
                fields = ', '.join(identifier(item['Columna']) for item in items)
                fields = f'({fields})' if len(items)>1 else fields
                kind = 'pk' if items[0]['Primaria'] else 'unique'
                lines.append(f"    {fields} [{kind}, name: {quoted(items[0]['Nombre'])}]")
            lines.append('  }')
        table_checks = [c for c in checks if c['TablaId'] == table_id]
        if table_checks:
            lines.append('  checks {')
            for check in table_checks:
                lines.append(f"    `{check['Expresion'].replace('`', '')}` [name: {quoted(check['Nombre'])}]")
            lines.append('  }')
        if schema+'.'+name in NOTES:
            lines.append('  Note: ' + quoted(NOTES[schema+'.'+name]))
        lines.extend(['}', ''])
    foreign_keys = OrderedDict()
    for ref in references:
        foreign_keys.setdefault(ref['Id'], []).append(ref)
    lines.append('// Relaciones fisicas. Las referencias historicas de auditoria no se dibujan como FK.')
    for items in foreign_keys.values():
        first = items[0]
        def endpoint(side):
            fields = ', '.join(identifier(item['Columna'+side]) for item in items)
            return qualified(first['Esquema'+side], first['Tabla'+side]) + '.' + (f'({fields})' if len(items)>1 else fields)
        if first['EsquemaOrigen'] == 'modelo' and first['TablaOrigen'] == 'Gasto' and first['ColumnaOrigen'] == 'Id':
            lines.append(f"Ref {identifier(first['Nombre'])}: {endpoint('Destino')} - {endpoint('Origen')}")
        else:
            lines.append(f"Ref {identifier(first['Nombre'])}: {endpoint('Origen')} > {endpoint('Destino')}")
    lines.append('')
    for group, (color, note) in GROUPS.items():
        lines.append(f'TableGroup {group} [color: {color}, note: {quoted(note)}] {{')
        lines.extend('  '+member for member in members[group])
        lines.extend(['}', ''])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines), encoding='utf-8')
    print(f'DBML generado: {len(tables)} tablas, {len(columns)} columnas, {len(foreign_keys)} FK, {len(GROUPS)} grupos. {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', default='docs/DIAGRAMA_BD.dbml.txt')
    args = parser.parse_args()
    output = (ROOT/args.salida).resolve()
    if not output.is_relative_to(ROOT):
        parser.error('La salida debe estar dentro del proyecto.')
    export(output)
