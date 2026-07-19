# auth_service.py
# ---------------------------------------------------------
# Login por contraseña + sesiones por token, pensado para
# funcionar igual desde el navegador y desde una futura app
# móvil (ninguno de los dos necesita cookies ni CORS con
# credenciales: mandan "Authorization: Bearer <token>").
#
# Reemplaza el viejo esquema de API_KEY estática expuesta al
# cliente via NEXT_PUBLIC_API_KEY. Diferencias clave:
#   - La contraseña nunca se guarda en texto plano, solo su hash
#     (PBKDF2-HMAC-SHA256, 200k iteraciones + salt) en la env var
#     APP_PASSWORD_HASH.
#   - El token de sesión es aleatorio (32 bytes), distinto en cada
#     login, y se guarda en la base de datos solo como hash SHA-256
#     (si alguien lee la tabla, no puede usar esos valores como
#     token real).
#   - El token expira solo (SESSION_TTL_DIAS) y se puede revocar
#     (logout) sin redeploy ni cambiar variables de entorno.
# ---------------------------------------------------------

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from config import APP_PASSWORD_HASH, BOGOTA, SESSION_TTL_DIAS
from db import db_connection

FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def init_tabla_sesiones():
    with db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sesiones_auth (
                token_hash TEXT PRIMARY KEY,
                creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
                expira_en DATETIME NOT NULL,
                ultimo_uso DATETIME
            )
        ''')


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _derivar_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)


def verificar_password(password: str) -> bool:
    """
    APP_PASSWORD_HASH tiene el formato "salt_hex$hash_hex", generado
    por scripts/generar_password_hash.py. Si no está configurada,
    el login queda deshabilitado (nadie puede entrar) -- mejor que
    aceptar cualquier contraseña por accidente.
    """
    if not APP_PASSWORD_HASH or not password:
        return False

    try:
        salt_hex, hash_hex = APP_PASSWORD_HASH.split("$")
        salt = bytes.fromhex(salt_hex)
        esperado = bytes.fromhex(hash_hex)
    except ValueError:
        logging.error(
            "APP_PASSWORD_HASH mal formado. Debe verse como "
            "'salt_hex$hash_hex' (ver scripts/generar_password_hash.py)."
        )
        return False

    calculado = _derivar_password(password, salt)

    # Comparación en tiempo constante: != normal filtra, por timing,
    # cuántos bytes iniciales coinciden. Con secrets.compare_digest
    # el tiempo de comparación no depende del contenido.
    return secrets.compare_digest(calculado, esperado)


def crear_sesion() -> tuple[str, datetime]:
    """
    Crea una sesión nueva y devuelve (token_sin_cifrar, fecha_expiracion).
    El token solo se devuelve esta vez; en la base de datos únicamente
    queda su hash.
    """
    token = secrets.token_urlsafe(32)
    expira = datetime.now(BOGOTA) + timedelta(days=SESSION_TTL_DIAS)

    with db_connection() as conn:
        conn.execute(
            "INSERT INTO sesiones_auth (token_hash, expira_en) VALUES (?, ?)",
            (_hash_token(token), expira.strftime(FORMATO_FECHA)),
        )

    return token, expira


def validar_sesion(token: str) -> bool:
    if not token:
        return False

    token_hash = _hash_token(token)

    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT expira_en FROM sesiones_auth WHERE token_hash = ?",
                (token_hash,),
            )
            fila = cursor.fetchone()

        if not fila:
            return False

        expira = datetime.strptime(fila[0], FORMATO_FECHA).replace(tzinfo=BOGOTA)
        if datetime.now(BOGOTA) >= expira:
            return False

        with db_connection() as conn:
            conn.execute(
                "UPDATE sesiones_auth SET ultimo_uso = ? WHERE token_hash = ?",
                (datetime.now(BOGOTA).strftime(FORMATO_FECHA), token_hash),
            )

        return True

    except Exception:
        logging.exception("Error validando sesión")
        return False


def revocar_sesion(token: str):
    if not token:
        return
    try:
        with db_connection() as conn:
            conn.execute(
                "DELETE FROM sesiones_auth WHERE token_hash = ?",
                (_hash_token(token),),
            )
    except Exception:
        logging.exception("Error revocando sesión")


def revocar_todas_las_sesiones():
    """Util para un botón de pánico ("cerrar sesión en todos lados")."""
    with db_connection() as conn:
        conn.execute("DELETE FROM sesiones_auth")


def limpiar_sesiones_expiradas():
    """
    Borra filas de sesiones ya vencidas. No es indispensable (validar_sesion
    ya las trata como inválidas), pero evita que la tabla crezca para
    siempre. Se puede llamar periódicamente desde el scheduler.
    """
    try:
        ahora = datetime.now(BOGOTA).strftime(FORMATO_FECHA)
        with db_connection() as conn:
            conn.execute(
                "DELETE FROM sesiones_auth WHERE expira_en < ?",
                (ahora,),
            )
    except Exception:
        logging.exception("Error limpiando sesiones expiradas")