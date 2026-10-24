"""Crear el administrador inicial; nunca incluye contrasenas predeterminadas."""

import argparse
from getpass import getpass
from pathlib import Path
import secrets
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import insert_id, transaction
from app.security import password_hash

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--usuario", default="administrador")
    p.add_argument(
        "--generar",
        action="store_true",
        help="Genera una clave y la muestra una sola vez",
    )
    args = p.parse_args()
    if args.usuario.casefold() == "sistema" or not re.fullmatch(
        r"[A-Za-z0-9_.-]{3,80}", args.usuario
    ):
        p.error(
            "Nombre reservado o invalido: usar de 3 a 80 letras, numeros, punto, guion o guion bajo."
        )
    password = (
        secrets.token_urlsafe(18)
        if args.generar
        else getpass("Contrasena (minimo 10 caracteres): ")
    )
    if len(password) < 10:
        p.error("La contrasena debe tener al menos 10 caracteres.")
    with transaction(actor="configuracion-inicial", role="Administrador") as con:
        con.execute(
            "SELECT Id FROM seguridad.Usuario WITH(UPDLOCK,HOLDLOCK)"
        ).fetchall()
        if con.execute(
            "SELECT Id FROM seguridad.Usuario WHERE NombreUsuario=?", args.usuario
        ).fetchone():
            p.error("El usuario ya existe. Usa la pantalla Usuarios para modificarlo.")
        role = con.execute(
            "SELECT Id FROM seguridad.Rol WHERE Nombre=N'Administrador'"
        ).fetchone()[0]
        new_id = insert_id(
            con,
            "INSERT seguridad.Usuario(NombreUsuario,NombreCompleto,HashContrasena,RolId) VALUES(?,?,?,?)",
            args.usuario,
            "Administrador local",
            password_hash(password),
            role,
        )
    print(f"Usuario creado: {args.usuario} (Id {new_id})")
    if args.generar:
        print(f"Contrasena: {password}")
