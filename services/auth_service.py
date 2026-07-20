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

# ---------------------------------------------------------
# Rate limiting de /api/login
# ---------------------------------------------------------
# APP_PASSWORD_HASH usa PBKDF2 200k iteraciones + comparación en
# tiempo constante, pero eso solo protege contra timing attacks --
# no pone ningún límite a CUÁNTAS veces alguien puede intentar por
# red. Como esta es la única puerta que protege todos los datos
# (patrones de conducta, historial emocional, tareas), sin esto
# alguien podía intentar contraseñas indefinidamente.
#
# Ventana deslizante simple por IP: si hay MAX_INTENTOS fallidos
# dentro de VENTANA_MINUTOS, la IP queda bloqueada por
# BLOQUEO_MINUTOS. Un login exitoso limpia el contador de esa IP.
MAX_INTENTOS_LOGIN = 5
VENTANA_INTENTOS_MINUTOS = 15
BLOQUEO_LOGIN_MINUTOS = 15


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
        conn.execute('''
            CREATE TABLE IF NOT EXISTS intentos_login (
                ip TEXT PRIMARY KEY,
                intentos INTEGER NOT NULL DEFAULT 0,
                primer_intento DATETIME NOT NULL,
                bloqueado_hasta DATETIME
            )
        ''')


def ip_bloqueada(ip: str) -> int:
    """
    Devuelve los segundos restantes de bloqueo para esta IP, o 0 si
    puede intentar login. Se llama ANTES de verificar la contraseña,
    para no gastar ni siquiera el PBKDF2 en una IP ya bloqueada.
    """
    if not ip:
        return 0
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT bloqueado_hasta FROM intentos_login WHERE ip = ?",
                (ip,),
            )
            fila = cursor.fetchone()

        if not fila or not fila[0]:
            return 0

        bloqueado_hasta = datetime.strptime(fila[0], FORMATO_FECHA).replace(tzinfo=BOGOTA)
        ahora = datetime.now(BOGOTA)
        if ahora >= bloqueado_hasta:
            return 0

        return int((bloqueado_hasta - ahora).total_seconds())
    except Exception:
        logging.exception("Error revisando bloqueo de login para IP %s", ip)
        return 0  # ante un error de la propia protección, no dejamos a nadie afuera


def registrar_intento_login(ip: str, exitoso: bool):
    """
    Actualiza el contador de intentos de esta IP. Un login exitoso
    borra el registro (empieza limpio la próxima vez). Un fallo suma
    al contador; si supera MAX_INTENTOS_LOGIN dentro de la ventana,
    se activa el bloqueo.
    """
    if not ip:
        return
    try:
        with db_connection() as conn:
            cursor = conn.cursor()

            if exitoso:
                cursor.execute("DELETE FROM intentos_login WHERE ip = ?", (ip,))
                return

            ahora = datetime.now(BOGOTA)
            cursor.execute(
                "SELECT intentos, primer_intento FROM intentos_login WHERE ip = ?",
                (ip,),
            )
            fila = cursor.fetchone()

            if fila:
                intentos, primer_intento_str = fila
                primer_intento = datetime.strptime(primer_intento_str, FORMATO_FECHA).replace(tzinfo=BOGOTA)
                ventana_vencida = ahora - primer_intento > timedelta(minutes=VENTANA_INTENTOS_MINUTOS)
            else:
                intentos = 0
                ventana_vencida = True

            if ventana_vencida:
                # Empieza (o reinicia) la ventana de conteo.
                nuevos_intentos = 1
                nuevo_primer_intento = ahora.strftime(FORMATO_FECHA)
                bloqueado_hasta = None
            else:
                nuevos_intentos = intentos + 1
                nuevo_primer_intento = primer_intento_str
                bloqueado_hasta = (
                    (ahora + timedelta(minutes=BLOQUEO_LOGIN_MINUTOS)).strftime(FORMATO_FECHA)
                    if nuevos_intentos >= MAX_INTENTOS_LOGIN
                    else None
                )

            cursor.execute('''
                INSERT INTO intentos_login (ip, intentos, primer_intento, bloqueado_hasta)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ip) DO UPDATE SET
                    intentos=excluded.intentos,
                    primer_intento=excluded.primer_intento,
                    bloqueado_hasta=excluded.bloqueado_hasta
            ''', (ip, nuevos_intentos, nuevo_primer_intento, bloqueado_hasta))
    except Exception:
        logging.exception("Error registrando intento de login para IP %s", ip)


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