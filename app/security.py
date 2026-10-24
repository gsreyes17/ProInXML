"""Sesiones locales revocables y permisos; no se persisten tokens ni contrasenas en claro."""

import hashlib
import secrets
from threading import RLock
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.config import settings
from app.db import identity, insert_id, rows, transaction

router = APIRouter(tags=["Seguridad"])
hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(32))
sessions: dict[str, dict] = {}
attempts: dict[tuple[str, str], list[float]] = {}
guard = RLock()
COOKIE = "proinxml_session"
ADMIN = "Administrador"
OPERATORS = (ADMIN, "Operador")


def password_hash(password):
    return hasher.hash(password)


def user_row(con, *, user_id=None, username=None, include_hash=False):
    columns = "u.Id,u.NombreUsuario,u.NombreCompleto,u.Activo,r.Nombre AS Rol"
    if include_hash:
        columns += ",u.HashContrasena"
    found = rows(
        con.execute(
            f"SELECT {columns} FROM seguridad.Usuario u JOIN seguridad.Rol r ON r.Id=u.RolId "
            + ("WHERE u.Id=?" if user_id is not None else "WHERE u.NombreUsuario=?"),
            user_id if user_id is not None else username,
        )
    )
    return found[0] if found else None


async def current_user(request: Request):
    authorization = request.headers.get("authorization", "")
    bearer = authorization.startswith("Bearer ")
    token = authorization[7:] if bearer else request.cookies.get(COOKIE, "")
    key = hashlib.sha256(token.encode()).hexdigest()
    with guard:
        session = sessions.get(key)
        if session is None or session["expires"] <= time.monotonic():
            sessions.pop(key, None)
            raise HTTPException(401, "Inicia sesion para continuar.")
        session = session.copy()
    if request.method not in ("GET", "HEAD", "OPTIONS") and not bearer:
        if not secrets.compare_digest(
            request.headers.get("x-csrf-token", ""), session["csrf"]
        ):
            raise HTTPException(
                403, "Token de sesion ausente o incorrecto. Actualiza la pagina."
            )
    with transaction(actor="sesion") as con:
        user = user_row(con, user_id=session["user_id"])
    if not user or not user["Activo"] or user["NombreUsuario"] == "sistema":
        with guard:
            sessions.pop(key, None)
        raise HTTPException(401, "La cuenta ya no tiene acceso.")
    request.state.session_key = key
    request.state.csrf = session["csrf"]
    context = identity.set(user)
    try:
        yield user
    finally:
        identity.reset(context)


def require_roles(*roles):
    async def permission(user=Depends(current_user)):
        if user["Rol"] not in roles:
            raise HTTPException(403, "Tu rol no permite esta accion.")
        return user

    return permission


class Login(BaseModel):
    usuario: str = Field(min_length=1, max_length=80)
    contrasena: str = Field(min_length=1, max_length=256)


@router.post("/auth/login")
def login(body: Login, request: Request, response: Response):
    username = body.usuario.strip()
    ip = request.client.host if request.client else "local"
    now = time.monotonic()
    bucket = (ip, username.casefold())
    with guard:
        # Eliminar entradas antiguas para no crecer indefinidamente.
        for old in list(attempts):
            attempts[old] = [t for t in attempts[old] if now - t < 60]
            if not attempts[old]:
                del attempts[old]
        limited = len(attempts.get(bucket, [])) >= 8
        attempts.setdefault(bucket, []).append(now)
    with transaction(actor=username) as con:
        user = user_row(con, username=username, include_hash=True)
        valid = False
        try:
            valid = hasher.verify(
                user["HashContrasena"] if user and user["Activo"] else dummy_hash,
                body.contrasena,
            )
        except (VerificationError, InvalidHashError):
            pass
        valid = bool(
            valid
            and user
            and user["Activo"]
            and username.casefold() != "sistema"
            and not limited
        )
        con.execute(
            "INSERT seguridad.EventoAcceso(UsuarioId,NombreIntentado,Evento,Exitoso,Ip) VALUES(?,?,?,?,?)",
            user["Id"] if user else None,
            username,
            "Login",
            int(valid),
            ip[:64],
        )
    if not valid:
        raise HTTPException(
            429 if limited else 401,
            "Demasiados intentos. Espera un minuto."
            if limited
            else "Usuario o contrasena incorrectos.",
        )
    user.pop("HashContrasena", None)
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with guard:
        for old in list(sessions):
            if sessions[old]["expires"] <= now:
                del sessions[old]
        # Reemplazar la sesion de este navegador para evitar sesiones huerfanas.
        old_token = request.cookies.get(COOKIE, "")
        sessions.pop(hashlib.sha256(old_token.encode()).hexdigest(), None)
        sessions[hashlib.sha256(token.encode()).hexdigest()] = {
            "user_id": user["Id"],
            "expires": now + settings.session_seconds,
            "csrf": csrf,
        }
    response.set_cookie(
        COOKIE,
        token,
        max_age=settings.session_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"usuario": user, "csrf": csrf, "token": token}


@router.get("/auth/me")
def me(request: Request, response: Response, user=Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {"usuario": user, "csrf": request.state.csrf}


@router.post("/auth/logout")
def logout(request: Request, response: Response, user=Depends(current_user)):
    with guard:
        sessions.pop(request.state.session_key, None)
    with transaction() as con:
        con.execute(
            "INSERT seguridad.EventoAcceso(UsuarioId,NombreIntentado,Evento,Exitoso,Ip) VALUES(?,?,?,?,?)",
            user["Id"],
            user["NombreUsuario"],
            "Logout",
            1,
            request.client.host if request.client else None,
        )
    response.delete_cookie(COOKIE, path="/")
    return {"mensaje": "Sesion cerrada."}


class UserInput(BaseModel):
    id: int | None = Field(None, ge=1)
    usuario: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    nombre: str = Field(min_length=1, max_length=160)
    contrasena: str | None = Field(None, min_length=10, max_length=256)
    rol: str = Field(pattern=r"^(Administrador|Operador|Consulta)$")
    activo: bool = True


@router.get("/usuarios")
def users(despues_de: int = 0, limite: int = 25, user=Depends(require_roles(ADMIN))):
    if despues_de < 0 or not 1 <= limite <= 100:
        raise HTTPException(422, "Paginacion fuera de rango.")
    with transaction() as con:
        result = rows(
            con.execute(
                "SELECT TOP(?) u.Id,u.NombreUsuario,u.NombreCompleto,r.Nombre AS Rol,u.Activo,u.CreadoUtc "
                "FROM seguridad.Usuario u JOIN seguridad.Rol r ON r.Id=u.RolId WHERE u.Id>? ORDER BY u.Id",
                limite + 1,
                despues_de,
            )
        )
        total = con.execute("SELECT COUNT_BIG(*) FROM seguridad.Usuario").fetchone()[0]
    return {
        "registros": result[:limite],
        "total": total,
        "siguiente_cursor": result[limite - 1]["Id"] if len(result) > limite else None,
    }


@router.post("/usuarios")
def save_user(body: UserInput, user=Depends(require_roles(ADMIN))):
    if body.usuario.casefold() == "sistema":
        raise HTTPException(409, "La identidad sistema esta reservada para el worker.")
    with transaction() as con:
        # Serializa cambios administrativos para proteger al ultimo administrador.
        con.execute(
            "SELECT Id FROM seguridad.Usuario WITH(UPDLOCK,HOLDLOCK) ORDER BY Id"
        ).fetchall()
        role = con.execute(
            "SELECT Id FROM seguridad.Rol WHERE Nombre=?", body.rol
        ).fetchone()
        existing = user_row(con, user_id=body.id) if body.id else None
        if body.id and (not existing or existing["NombreUsuario"] == "sistema"):
            raise HTTPException(404, "Usuario editable no encontrado.")
        collision = con.execute(
            "SELECT Id FROM seguridad.Usuario WHERE NombreUsuario=?", body.usuario
        ).fetchone()
        if collision and (not existing or collision[0] != body.id):
            raise HTTPException(409, "Ese nombre de usuario ya existe.")
        if (
            existing
            and existing["Rol"] == ADMIN
            and existing["Activo"]
            and (body.rol != ADMIN or not body.activo)
        ):
            admins = con.execute(
                "SELECT COUNT(*) FROM seguridad.Usuario u JOIN seguridad.Rol r ON r.Id=u.RolId "
                "WHERE u.Activo=1 AND r.Nombre=N'Administrador' AND u.Id<>?",
                body.id,
            ).fetchone()[0]
            if admins == 0:
                raise HTTPException(
                    409, "Debe quedar al menos un administrador activo."
                )
        if existing:
            con.execute(
                "UPDATE seguridad.Usuario SET NombreUsuario=?,NombreCompleto=?,RolId=?,Activo=? WHERE Id=?",
                body.usuario,
                body.nombre,
                role[0],
                int(body.activo),
                body.id,
            )
            if body.contrasena:
                con.execute(
                    "UPDATE seguridad.Usuario SET HashContrasena=? WHERE Id=?",
                    password_hash(body.contrasena),
                    body.id,
                )
            user_id = body.id
        else:
            if not body.contrasena:
                raise HTTPException(
                    422, "Indica una contrasena de al menos 10 caracteres."
                )
            user_id = insert_id(
                con,
                "INSERT seguridad.Usuario(NombreUsuario,NombreCompleto,HashContrasena,RolId,Activo) VALUES(?,?,?,?,?)",
                body.usuario,
                body.nombre,
                password_hash(body.contrasena),
                role[0],
                int(body.activo),
            )
        con.execute(
            "INSERT seguridad.EventoAcceso(UsuarioId,NombreIntentado,Evento,Exitoso) VALUES(?,?,?,1)",
            user_id,
            body.usuario,
            "UsuarioActualizado" if existing else "UsuarioCreado",
        )
    if existing:
        with guard:
            for key in list(sessions):
                if sessions[key]["user_id"] == user_id:
                    del sessions[key]
    return {"id": user_id, "mensaje": "Usuario guardado."}
