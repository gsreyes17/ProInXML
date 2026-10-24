"""Genera esquema, normalizador y vistas del modelo desde su contrato."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.model_schema import ENTITIES, FACT_COLUMNS
from app.xml_reader import FIELDS


def quote(name):
    return f"[{name}]"


def joins_for(names):
    selected = set()

    def collect(name):
        if name in selected:
            return
        for col in ENTITIES[name][2]:
            if col.reference:
                collect(col.reference)
        selected.add(name)

    for name in names:
        collect(name)
    joins = []
    for name, (_, _, columns) in ENTITIES.items():
        if name not in selected:
            continue
        conditions = [
            equal(f"{quote(name)}.{quote(c.name)}", expression(c), c.nullable)
            for c in columns
        ]
        kind = "LEFT JOIN" if name == "UnidadMedida" else "JOIN"
        joins.append(
            f"{kind} modelo.{quote(name)} {quote(name)} ON " + " AND ".join(conditions)
        )
    return "\n".join(joins)


def expression(col):
    return f"{quote(col.reference)}.Id" if col.reference else f"g.{quote(col.source)}"


def equal(left, right, nullable=False):
    return (
        f"({left}={right} OR ({left} IS NULL AND {right} IS NULL))"
        if nullable
        else f"{left}={right}"
    )


def build_tables():
    out = [
        "-- Tablas del modelo relacional. Generado por scripts/desarrollo/build_model_sql.py.",
        "USE ProInXML;\nGO\nSET NOCOUNT ON;\nSET XACT_ABORT ON;\nBEGIN TRANSACTION;",
        "IF SCHEMA_ID(N'modelo') IS NULL EXEC(N'CREATE SCHEMA modelo AUTHORIZATION dbo');",
    ]
    for name, (_, _, columns) in ENTITIES.items():
        definitions = [f"Id bigint IDENTITY CONSTRAINT PK_modelo_{name} PRIMARY KEY"]
        for c in columns:
            target = (
                f" CONSTRAINT FK_{name}_{c.name} REFERENCES modelo.{quote(c.reference)}(Id)"
                if c.reference
                else ""
            )
            definitions.append(
                f"{quote(c.name)} {c.sql_type} {'NULL' if c.nullable else 'NOT NULL'}{target}"
            )
        definitions.append(
            f"CreadoUtc datetime2(3) NOT NULL CONSTRAINT DF_modelo_{name}_CreadoUtc DEFAULT SYSUTCDATETIME()"
        )
        definitions.append(
            f"CONSTRAINT {quote('UQ_' + name + '_Clave')} UNIQUE("
            + ",".join(quote(c.name) for c in columns)
            + ")"
        )
        out.append(
            f"IF OBJECT_ID(N'modelo.{name}',N'U') IS NULL\nCREATE TABLE modelo.{quote(name)}(\n  "
            + ",\n  ".join(definitions)
            + "\n);"
        )
    definitions = [
        "Id bigint CONSTRAINT PK_modelo_Gasto PRIMARY KEY CONSTRAINT FK_modelo_Gasto_Origen REFERENCES datos.Gasto(Id)"
    ]
    for c in FACT_COLUMNS:
        target = (
            f" CONSTRAINT FK_Gasto_{c.name} REFERENCES modelo.{quote(c.reference)}(Id)"
            if c.reference
            else " CONSTRAINT FK_modelo_Gasto_TipoActProy REFERENCES catalogo.TipoActProy(Id)"
            if c.name == "TipoActProyId"
            else ""
        )
        definitions.append(f"{quote(c.name)} {c.sql_type} NOT NULL{target}")
    definitions.append("CreadoUtc datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME()")
    out.append(
        "IF OBJECT_ID(N'modelo.Gasto',N'U') IS NULL\nCREATE TABLE modelo.Gasto(\n  "
        + ",\n  ".join(definitions)
        + "\n);"
    )
    out.append("COMMIT;\nGO")
    return "\n\n".join(out)


def source_fields(name):
    fields = set()
    for col in ENTITIES[name][2]:
        if col.reference:
            fields.update(source_fields(col.reference))
        else:
            fields.add(col.source)
    return sorted(fields)


def build_normalizer():
    out = [
        "-- Normalizacion transaccional y vistas del modelo. Generado desde app/model_schema.py.",
        "USE ProInXML;\nGO\nSET NOCOUNT ON;\nGO",
    ]
    out.append("""
CREATE OR ALTER PROCEDURE modelo.NormalizarDocumento @DocumentoId bigint AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 BEGIN TRANSACTION;
 DECLARE @resultado int;
 EXEC @resultado=sys.sp_getapplock @Resource=N'ProInXML:modelo:normalizacion',
  @LockMode='Exclusive',@LockOwner='Transaction',@LockTimeout=60000;
 IF @resultado<0 THROW 50200,'No se pudo bloquear la normalizacion del documento.',1;
 SELECT * INTO #origen FROM datos.Gasto WHERE DocumentoId=@DocumentoId;
 IF NOT EXISTS(SELECT 1 FROM #origen) BEGIN COMMIT; RETURN; END;
""")
    for name, (_, _, columns) in ENTITIES.items():
        source = "#origen"
        if name in ("SecuenciaFuncional", "Meta"):
            source = f"#{name}Origen"
            fields = ",".join(quote(field) for field in source_fields(name))
            out.append(f"SELECT DISTINCT {fields} INTO {source} FROM #origen;")
        projection = ",".join(expression(c) + " AS " + quote(c.name) for c in columns)
        joins = joins_for([c.reference for c in columns if c.reference])
        matching = " AND ".join(
            equal(f"d.{quote(c.name)}", f"s.{quote(c.name)}", c.nullable)
            for c in columns
        )
        collist = ",".join(quote(c.name) for c in columns)
        valid = "WHERE g.Unidad_Medida IS NOT NULL" if name == "UnidadMedida" else ""
        out.append(
            f"INSERT modelo.{quote(name)}({collist})\nSELECT {','.join('s.' + quote(c.name) for c in columns)} FROM (\nSELECT DISTINCT {projection} FROM {source} g\n{joins}\n{valid}) s\nWHERE NOT EXISTS(SELECT 1 FROM modelo.{quote(name)} d WITH(UPDLOCK,HOLDLOCK) WHERE {matching});"
        )
    fact_projection = ",".join(
        expression(c) + " AS " + quote(c.name) for c in FACT_COLUMNS
    )
    fact_joins = joins_for([c.reference for c in FACT_COLUMNS if c.reference])
    out.append(
        f"SELECT g.Id,{fact_projection} INTO #hechos FROM #origen g\n{fact_joins};"
    )
    out.append(
        "UPDATE d SET "
        + ",".join(f"d.{quote(c.name)}=s.{quote(c.name)}" for c in FACT_COLUMNS)
        + "\nFROM modelo.Gasto d JOIN #hechos s ON s.Id=d.Id WHERE "
        + " OR ".join(f"d.{quote(c.name)}<>s.{quote(c.name)}" for c in FACT_COLUMNS)
        + ";"
    )
    collist = "Id," + ",".join(quote(c.name) for c in FACT_COLUMNS)
    out.append(
        f"INSERT modelo.Gasto({collist}) SELECT {','.join('s.' + quote(c) for c in ['Id'] + [c.name for c in FACT_COLUMNS])} FROM #hechos s WHERE NOT EXISTS(SELECT 1 FROM modelo.Gasto d WHERE d.Id=s.Id);"
    )
    out.append(
        "IF (SELECT COUNT_BIG(*) FROM #origen)<>(SELECT COUNT_BIG(*) FROM #hechos) THROW 50201,'La normalizacion no conserva todas las filas.',1;\nCOMMIT;\nEND;\nGO\nGRANT EXECUTE ON modelo.NormalizarDocumento TO proinxml_app;\nGO"
    )
    # Reconstruccion explicita de los 39 campos desde entidades, sin leerlos de datos.Gasto.
    raw_mapping = {}
    view_joins = []
    visited = set()

    def reconstruct(name, on, nullable=False):
        if name in visited:
            return
        visited.add(name)
        kind = "LEFT JOIN" if nullable else "JOIN"
        view_joins.append(
            f"{kind} modelo.{quote(name)} {quote(name)} ON {quote(name)}.Id={on}"
        )
        for c in ENTITIES[name][2]:
            if c.reference:
                reconstruct(c.reference, f"{quote(name)}.{quote(c.name)}", c.nullable)
            else:
                raw_mapping[c.source] = f"{quote(name)}.{quote(c.name)}"

    for c in FACT_COLUMNS:
        if c.reference:
            reconstruct(c.reference, f"f.{quote(c.name)}")
        else:
            raw_mapping[c.source] = f"f.{quote(c.name)}"
    assert set(raw_mapping) == set(FIELDS)
    out.append(
        "CREATE OR ALTER VIEW modelo.GastoReconstruido AS\nSELECT f.Id,"
        + ",\n".join(raw_mapping[name] + " AS " + quote(name) for name in FIELDS)
        + "\nFROM modelo.Gasto f\n"
        + "\n".join(view_joins)
        + ";\nGO\n"
    )
    return "\n\n".join(out)


if __name__ == "__main__":
    for name, build in [
        ("002_modelo.sql", build_tables),
        ("003_normalizacion.sql", build_normalizer),
    ]:
        path = ROOT / "sql" / name
        path.write_text(build(), encoding="utf-8", newline="\n")
        print(f"Generado {path.name}.")
