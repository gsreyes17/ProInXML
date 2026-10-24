"""Aplica los SQL activos en orden; no ejecuta el archivo de scripts heredados."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.db import transaction


def apply(connection, path, database="ProInXML"):
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,100}", database):
        raise ValueError("Nombre de base no admitido.")
    source = path.read_text(encoding="utf-8").replace("USE ProInXML;", f"USE [{database}];")
    source = source.replace("DB_ID(N'ProInXML')", f"DB_ID(N'{database}')")
    source = source.replace("CREATE DATABASE ProInXML", f"CREATE DATABASE [{database}]")
    for batch in re.split(r"^\s*GO\s*$", source, flags=re.I | re.M):
        if not batch.strip():
            continue
        cursor = connection.execute(batch)
        while cursor.nextset():
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivos", nargs="*")
    parser.add_argument("--base-datos", default="ProInXML")
    args = parser.parse_args()
    paths = [ROOT / p for p in args.archivos] if args.archivos else sorted((ROOT / "sql").glob("[0-9]*.sql"))
    # Conectar a master permite instalar tambien cuando ProInXML aun no existe.
    import os
    os.environ["MSSQL_DATABASE"] = "master"
    with transaction(actor="migracion") as con:
        con.commit()
        con.autocommit = True
        for path in paths:
            print(f"Aplicando {path.name}", flush=True)
            apply(con, path, args.base_datos)
    print("Esquema aplicado.")
