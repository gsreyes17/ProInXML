"""Instala y reaplica el esquema en ProInXML_Validacion, aislada de los datos reales."""

import argparse
import os
from pathlib import Path
import sys
import re

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.db import transaction
from scripts.aplicar_sql import apply

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-datos", default="ProInXML_Validacion")
    args = parser.parse_args()
    target = args.base_datos
    if not re.fullmatch(r"ProInXML(?:_[A-Za-z0-9]+)*_Validacion", target):
        parser.error("La base debe ser una base aislada ProInXML_*_Validacion.")
    directory = ROOT / ".runtime" / "validacion_sql" / target
    directory.mkdir(parents=True, exist_ok=True)
    os.environ["MSSQL_DATABASE"] = "master"
    with transaction(actor="verificacion-esquema") as con:
        con.commit()
        con.autocommit = True
        if not con.execute("SELECT DB_ID(?)", target).fetchone()[0]:
            data = str(directory / "datos.mdf").replace("'", "''")
            log = str(directory / "log.ldf").replace("'", "''")
            con.execute(
                f"CREATE DATABASE [{target}] ON PRIMARY(NAME=N'ProInXML_Validacion',FILENAME=N'{data}',SIZE=32MB) "
                f"LOG ON(NAME=N'ProInXML_Validacion_log',FILENAME=N'{log}',SIZE=16MB)"
            )
        for repeat in range(2):
            for path in sorted((ROOT / "sql").glob("[0-9]*.sql")):
                print(f"Pasada {repeat + 1}: {path.name}", flush=True)
                apply(con, path, target)
        table_count = con.execute(
            "SELECT COUNT(*) FROM sys.tables WHERE SCHEMA_NAME(schema_id) "
            "IN('integracion','datos','modelo','catalogo','seguridad','auditoria','analisis')"
        ).fetchone()[0]
        print("Tablas:", table_count)
        assert table_count == 45, "Cantidad de tablas inesperada."
        print(
            "Columnas vista XML:",
            con.execute(
                "SELECT COUNT(*) FROM sys.columns WHERE object_id=OBJECT_ID(N'datos.vw_GastoXML')"
            ).fetchone()[0],
        )
        assert (
            con.execute(
                "SELECT COUNT(*) FROM sys.columns WHERE object_id=OBJECT_ID(N'datos.vw_GastoXML')"
            ).fetchone()[0]
            == 39
        )
        print(
            "Tablas sin CreadoUtc:",
            con.execute(
                "SELECT COUNT(*) FROM sys.tables t WHERE NOT EXISTS(SELECT 1 FROM sys.columns c WHERE c.object_id=t.object_id AND c.name='CreadoUtc')"
            ).fetchone()[0],
        )
