# auth_ticktick.py (archivo nuevo)
import logging
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from cryptography.fernet import Fernet, InvalidToken
from db import db_connection
from repositories.db_repository import execute
import os
from dotenv import load_dotenv
load_dotenv()
from config import BOGOTA, TOKEN_ENCRYPTION_KEY

TICKTICK_CLIENT_ID = os.getenv("TICKTICK_CLIENT_ID")
TICKTICK_CLIENT_SECRET = os.getenv("TICKTICK_CLIENT_SECRET")

 

# Hoy solo existe este usuario. El día que haya más, cada fila de
# usuario real reemplaza este default — el resto del código no cambia.
USUARIO_DEFAULT = "default_user"

TICKTICK_TOKEN_URL = "https://ticktick.com/oauth/token"

# ---------------------------------------------------------
# Cifrado en reposo de access_token / refresh_token.
# Si no hay TOKEN_ENCRYPTION_KEY configurada, se guardan sin cifrar
# (igual que antes) -- no recomendado fuera de desarrollo local.
# Ver scripts/generar_encryption_key.py.
# ---------------------------------------------------------
_fernet = Fernet(TOKEN_ENCRYPTION_KEY) if TOKEN_ENCRYPTION_KEY else None


def _cifrar(valor: str | None) -> str | None:
    if valor is None or not _fernet:
        return valor
    return _fernet.encrypt(valor.encode("utf-8")).decode("utf-8")


def _descifrar(valor: str | None) -> str | None:
    if valor is None or not _fernet:
        return valor
    try:
        return _fernet.decrypt(valor.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logging.error(
            "No se pudo descifrar el token guardado: TOKEN_ENCRYPTION_KEY "
            "no coincide con la que se usó para guardarlo (¿cambió?), o el "
            "valor en la base de datos está sin cifrar todavía."
        )
        return None


def init_tabla_tokens():
    with db_connection() as conn:
        execute(conn, '''
            CREATE TABLE IF NOT EXISTS tokens_oauth (
                user_id TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                expires_at DATETIME,
                timestamp_actualizado DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')


def guardar_token(access_token: str, refresh_token: str, expires_in_seconds: int,
                   user_id: str = USUARIO_DEFAULT):
    expira = datetime.now(BOGOTA) + timedelta(seconds=expires_in_seconds)
    with db_connection() as conn:
        execute(conn, '''
            INSERT INTO tokens_oauth (user_id, access_token, refresh_token, expires_at, timestamp_actualizado)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                access_token=excluded.access_token,
                refresh_token=excluded.refresh_token,
                expires_at=excluded.expires_at,
                timestamp_actualizado=excluded.timestamp_actualizado
        ''', (user_id, _cifrar(access_token), _cifrar(refresh_token),
              expira.strftime("%Y-%m-%d %H:%M:%S"),
              datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S")))


def _refrescar_token(refresh_token: str, user_id: str) -> str | None:
    try:
        resp = requests.post(TICKTICK_TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": TICKTICK_CLIENT_ID,
            "client_secret": TICKTICK_CLIENT_SECRET,
        }, timeout=10)
        if resp.status_code != 200:
            logging.warning("No se pudo refrescar el token de TickTick: %s", resp.text)
            return None
        datos = resp.json()
        guardar_token(
            datos["access_token"],
            datos.get("refresh_token", refresh_token),  # algunos providers no rotan el refresh
            datos.get("expires_in", 2592000),
            user_id,
        )
        return datos["access_token"]
    except requests.exceptions.RequestException as e:
        logging.exception("Error de red refrescando token: %s", e)
        return None


def obtener_token(user_id: str = USUARIO_DEFAULT) -> str | None:
    try:
        with db_connection() as conn:
            cursor = execute(
                conn,
                "SELECT access_token, refresh_token, expires_at FROM tokens_oauth WHERE user_id = ?",
                (user_id,)
            )
            fila = cursor.fetchone()

        if not fila:
            return None

        access_token, refresh_token, expires_at_str = fila
        access_token = _descifrar(access_token)
        refresh_token = _descifrar(refresh_token)

        if expires_at_str:
            expira = (
                expires_at_str if isinstance(expires_at_str, datetime)
                else datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
            )
            expira = expira.replace(tzinfo=BOGOTA) if expira.tzinfo is None else expira
            # Margen de 5 minutos para no usar un token a punto de morir
            if datetime.now(BOGOTA) >= expira - timedelta(minutes=5):
                if not refresh_token:
                    logging.warning("Token expirado sin refresh_token disponible para %s", user_id)
                    return None
                return _refrescar_token(refresh_token, user_id)

        return access_token
    except Exception as e:
        logging.exception("Error obteniendo token: %s", e)
        return None