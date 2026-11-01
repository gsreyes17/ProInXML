from contextlib import contextmanager
from contextvars import ContextVar
import os
from uuid import uuid4

import pyodbc
from app.infrastructure.config import settings  # noqa: F401 - Carga .env al ejecutar scripts SQL.

identity = ContextVar("audit_identity", default=None)
# Cada conexion se configura con su contexto; no reutilizar identidad de otra sesion.
pyodbc.pooling = False


def quote_odbc(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


@contextmanager
def transaction(
    actor: str | None = None,
    correlation: str | None = None,
    user_id: int | None = None,
    role: str | None = None,
):
    values = {
        "DRIVER": os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server"),
        "SERVER": os.getenv("MSSQL_SERVER", "localhost"),
        "DATABASE": os.getenv("MSSQL_DATABASE", "ProInXML"),
        "Encrypt": os.getenv("MSSQL_ENCRYPT", "yes"),
        "TrustServerCertificate": os.getenv("MSSQL_TRUST_SERVER_CERTIFICATE", "yes"),
        "APP": "ProInXML",
    }
    if os.getenv("MSSQL_TRUSTED_CONNECTION", "yes").lower() == "yes":
        values["Trusted_Connection"] = "yes"
    else:
        values.update(UID=os.environ["MSSQL_USER"], PWD=os.environ["MSSQL_PASSWORD"])
    connection = pyodbc.connect(
        ";".join(f"{k}={quote_odbc(v)}" for k, v in values.items()), timeout=5
    )
    try:
        current = identity.get() or {}
        user_id = user_id if user_id is not None else current.get("Id")
        role = role or current.get("Rol", "Sin identificar")
        if (
            user_id is None
            and not current
            and actor in (None, "sistema", "worker-local")
        ):
            system_cursor = connection.execute(
                "IF OBJECT_ID(N'seguridad.Usuario',N'U') IS NOT NULL "
                "SELECT u.Id,r.Nombre FROM seguridad.Usuario u JOIN seguridad.Rol r ON r.Id=u.RolId "
                "WHERE u.NombreUsuario=N'sistema'"
            )
            system = system_cursor.fetchone() if system_cursor.description else None
            if system:
                user_id, role = system
        connection.execute(
            "EXEC sys.sp_set_session_context @key=N'actor', @value=?",
            (actor or current.get("NombreUsuario", "sistema"))[:128],
        )
        connection.execute(
            "EXEC sys.sp_set_session_context @key=N'usuario_id', @value=?", user_id
        )
        connection.execute(
            "EXEC sys.sp_set_session_context @key=N'rol', @value=?", role[:40]
        )
        connection.execute(
            "EXEC sys.sp_set_session_context @key=N'correlation', @value=?",
            correlation or str(uuid4()),
        )
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def rows(cursor) -> list[dict]:
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def insert_id(connection, sql: str, *params) -> int:
    cursor = connection.execute(
        "SET NOCOUNT ON; " + sql + "; SELECT CAST(SCOPE_IDENTITY() AS bigint)", *params
    )
    return int(cursor.fetchone()[0])
