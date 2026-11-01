"""Carga nombres INEI de departamento, provincia, region y distrito."""

import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.infrastructure.db import transaction
from app.integration.normalizer import acquire_document_lock

SOURCE = ROOT / "data_models" / "ubigeo_distrito.csv"


def read_source():
    raw = SOURCE.read_bytes()
    entries = []
    skipped = []
    known = set()
    departments = {}
    provinces = {}
    for line, row in enumerate(csv.DictReader(raw.decode("utf-8-sig").splitlines()), 2):
        code = row["inei"].strip()
        if len(code) != 6 or not code.isdigit():
            skipped.append(line)
            continue
        if code in known:
            raise ValueError(f"Ubigeo INEI duplicado en la linea {line}: {code}")
        known.add(code)
        department, province, district = code[:2], code[2:4], code[4:6]
        names = tuple(
            row[key].strip()
            for key in ("departamento", "provincia", "distrito", "region")
        )
        if not all(names):
            raise ValueError(f"Nombre geografico vacio en la linea {line}.")
        if department in departments and departments[department] != names[0]:
            raise ValueError(
                f"Nombre de departamento contradictorio en la linea {line}."
            )
        departments[department] = names[0]
        province_key = department + province
        province_names = (names[1], names[3])
        if province_key in provinces and provinces[province_key] != province_names:
            raise ValueError(f"Provincia o region contradictoria en la linea {line}.")
        provinces[province_key] = province_names
        entries.append((department, province, district, *names))
    if not entries:
        raise ValueError("El CSV no contiene ubigeos INEI validos.")
    return entries, skipped, hashlib.sha256(raw).hexdigest()


def load(database, *, auditar=True):
    entries, skipped, digest = read_source()
    os.environ["MSSQL_DATABASE"] = database
    with transaction(actor="catalogo-ubigeo") as con:
        acquire_document_lock(con)
        if con.execute("SELECT DB_NAME()").fetchone()[0] != database:
            raise RuntimeError("La conexion no apunta a la base solicitada.")
        for table, column in (
            ("Departamento", "Nombre"),
            ("Provincia", "Nombre"),
            ("Provincia", "NombreRegion"),
            ("Distrito", "Nombre"),
        ):
            if (
                con.execute(
                    "SELECT COL_LENGTH(?,?)", f"modelo.{table}", column
                ).fetchone()[0]
                is None
            ):
                raise RuntimeError("Aplica primero sql/002_modelo.sql.")
        con.execute(
            "CREATE TABLE #Ubigeo(DepartamentoCodigo varchar(2) NOT NULL,"
            "ProvinciaCodigo varchar(2) NOT NULL,DistritoCodigo varchar(2) NOT NULL,"
            "DepartamentoNombre nvarchar(160) NOT NULL,ProvinciaNombre nvarchar(160) NOT NULL,"
            "DistritoNombre nvarchar(160) NOT NULL,RegionNombre nvarchar(160) NOT NULL,"
            "PRIMARY KEY(DepartamentoCodigo,ProvinciaCodigo,DistritoCodigo))"
        )
        con.cursor().executemany("INSERT #Ubigeo VALUES(?,?,?,?,?,?,?)", entries)
        con.execute(
            "INSERT modelo.Departamento(Codigo) "
            "SELECT DISTINCT u.DepartamentoCodigo FROM #Ubigeo u "
            "WHERE NOT EXISTS(SELECT 1 FROM modelo.Departamento d WITH(UPDLOCK,HOLDLOCK) "
            "WHERE d.Codigo=u.DepartamentoCodigo)"
        )
        con.execute(
            "UPDATE d SET Nombre=u.DepartamentoNombre FROM modelo.Departamento d "
            "JOIN #Ubigeo u ON u.DepartamentoCodigo=d.Codigo "
            "WHERE d.Nombre IS NULL OR d.Nombre<>u.DepartamentoNombre"
        )
        con.execute(
            "INSERT modelo.Provincia(DepartamentoId,Codigo) "
            "SELECT DISTINCT d.Id,u.ProvinciaCodigo FROM #Ubigeo u "
            "JOIN modelo.Departamento d ON d.Codigo=u.DepartamentoCodigo "
            "WHERE NOT EXISTS(SELECT 1 FROM modelo.Provincia p WITH(UPDLOCK,HOLDLOCK) "
            "WHERE p.DepartamentoId=d.Id AND p.Codigo=u.ProvinciaCodigo)"
        )
        con.execute(
            "UPDATE p SET Nombre=u.ProvinciaNombre,NombreRegion=u.RegionNombre "
            "FROM modelo.Provincia p JOIN modelo.Departamento d ON d.Id=p.DepartamentoId "
            "JOIN #Ubigeo u ON u.DepartamentoCodigo=d.Codigo AND u.ProvinciaCodigo=p.Codigo "
            "WHERE p.Nombre IS NULL OR p.Nombre<>u.ProvinciaNombre "
            "OR p.NombreRegion IS NULL OR p.NombreRegion<>u.RegionNombre"
        )
        con.execute(
            "INSERT modelo.Distrito(ProvinciaId,Codigo) "
            "SELECT p.Id,u.DistritoCodigo FROM #Ubigeo u "
            "JOIN modelo.Departamento d ON d.Codigo=u.DepartamentoCodigo "
            "JOIN modelo.Provincia p ON p.DepartamentoId=d.Id AND p.Codigo=u.ProvinciaCodigo "
            "WHERE NOT EXISTS(SELECT 1 FROM modelo.Distrito x WITH(UPDLOCK,HOLDLOCK) "
            "WHERE x.ProvinciaId=p.Id AND x.Codigo=u.DistritoCodigo)"
        )
        con.execute(
            "UPDATE x SET Nombre=u.DistritoNombre FROM modelo.Distrito x "
            "JOIN modelo.Provincia p ON p.Id=x.ProvinciaId "
            "JOIN modelo.Departamento d ON d.Id=p.DepartamentoId "
            "JOIN #Ubigeo u ON u.DepartamentoCodigo=d.Codigo "
            "AND u.ProvinciaCodigo=p.Codigo AND u.DistritoCodigo=x.Codigo "
            "WHERE x.Nombre IS NULL OR x.Nombre<>u.DistritoNombre"
        )
        summary = {
            "base": database,
            "fuente": SOURCE.name,
            "sha256": digest,
            "codigos_inei": len(entries),
            "filas_omitidas_sin_inei": len(skipped),
            "departamentos_con_nombre": con.execute(
                "SELECT COUNT(*) FROM modelo.Departamento WHERE Nombre IS NOT NULL"
            ).fetchone()[0],
            "provincias_con_nombre": con.execute(
                "SELECT COUNT(*) FROM modelo.Provincia WHERE Nombre IS NOT NULL"
            ).fetchone()[0],
            "distritos_con_nombre": con.execute(
                "SELECT COUNT(*) FROM modelo.Distrito WHERE Nombre IS NOT NULL"
            ).fetchone()[0],
        }
        if auditar:
            con.execute(
                "INSERT auditoria.Cambio(Tabla,RegistroId,Operacion,UsuarioId,Actor,Rol,LoginSQL,Correlacion,Despues) "
                "VALUES(N'modelo.Distrito',0,'U',TRY_CONVERT(bigint,SESSION_CONTEXT(N'usuario_id')),"
                "CONVERT(nvarchar(128),SESSION_CONTEXT(N'actor')),CONVERT(nvarchar(40),SESSION_CONTEXT(N'rol')),"
                "ORIGINAL_LOGIN(),TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'correlation')),?)",
                json.dumps({"accion": "CargarUbigeo", **summary}, ensure_ascii=False),
            )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-datos", default=os.getenv("MSSQL_DATABASE", "ProInXML"))
    parser.add_argument(
        "--sin-auditoria", action="store_true", help="Carga inicial sin evento de auditoria"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            load(args.base_datos, auditar=not args.sin_auditoria),
            ensure_ascii=False,
            indent=2,
        )
    )
