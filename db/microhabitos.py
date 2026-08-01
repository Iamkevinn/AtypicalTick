# db/microhabitos.py
import logging
from datetime import datetime, timedelta

from config import BOGOTA
from repositories.db_repository import db_connection, execute, fetch_one, fetch_all


def _parsear_timestamp(valor):
    """
    Mismo patrón que estadisticas_service.py::calcular_dias_ausente():
    Postgres devuelve un datetime ya parseado; SQLite devuelve el
    string tal cual se guardó. Se normaliza a datetime con tz Bogotá.
    """

    if valor is None:
        return None

    fecha = (
        valor if isinstance(valor, datetime)
        else datetime.strptime(valor, "%Y-%m-%d %H:%M:%S")
    )

    return fecha.replace(tzinfo=BOGOTA) if fecha.tzinfo is None else fecha


def obtener_estado(categoria: str):
    """
    Devuelve {"ultima_vez": datetime|None, "snooze_hasta": datetime|None}.
    Si la categoría nunca se ha tocado, ambos quedan en None.
    """

    try:
        with db_connection() as conn:
            fila = fetch_one(
                conn,
                "SELECT ultima_vez, snooze_hasta FROM microhabitos_estado WHERE categoria = ?",
                (categoria,),
            )

        if not fila:
            return {"ultima_vez": None, "snooze_hasta": None}

        return {
            "ultima_vez": _parsear_timestamp(fila["ultima_vez"]),
            "snooze_hasta": _parsear_timestamp(fila["snooze_hasta"]),
        }

    except Exception:
        logging.exception(
            "Error obteniendo estado de microhábito %s",
            categoria,
        )
        return {"ultima_vez": None, "snooze_hasta": None}


def marcar_categoria(categoria: str, *, tocar_ultima_vez: bool, snooze_hasta=None):
    """
    Upsert del estado de una categoría.

    - tocar_ultima_vez=True ("hecho" o "ignorado"): se actualiza
      ultima_vez=ahora y se limpia cualquier snooze pendiente. Ambos
      casos cuentan como "ya se le mostró" -- lo que cambia es si lo
      hizo, que se registra aparte en el historial.
    - tocar_ultima_vez=False ("pospuesto"): NO se toca ultima_vez, solo
      se guarda snooze_hasta (~5 min). Así, al pasar el snooze, la
      categoría vuelve a estar vencida de inmediato en vez de esperar
      un intervalo completo de nuevo.
    """

    ahora_str = datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S")
    snooze_str = snooze_hasta.strftime("%Y-%m-%d %H:%M:%S") if snooze_hasta else None

    try:
        with db_connection() as conn:
            if tocar_ultima_vez:
                execute(
                    conn,
                    """
                    INSERT INTO microhabitos_estado (categoria, ultima_vez, snooze_hasta)
                    VALUES (?, ?, NULL)
                    ON CONFLICT (categoria) DO UPDATE SET
                        ultima_vez = excluded.ultima_vez,
                        snooze_hasta = NULL
                    """,
                    (categoria, ahora_str),
                )
            else:
                execute(
                    conn,
                    """
                    INSERT INTO microhabitos_estado (categoria, ultima_vez, snooze_hasta)
                    VALUES (?, NULL, ?)
                    ON CONFLICT (categoria) DO UPDATE SET
                        snooze_hasta = excluded.snooze_hasta
                    """,
                    (categoria, snooze_str),
                )

    except Exception:
        logging.exception(
            "Error actualizando estado de microhábito %s",
            categoria,
        )


def registrar_historial(categoria: str, accion: str):
    ahora = datetime.now(BOGOTA)

    try:
        with db_connection() as conn:
            execute(
                conn,
                """
                INSERT INTO microhabitos_historial (
                    categoria, hora, dia_semana, accion, timestamp
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    categoria,
                    ahora.hour,
                    ahora.weekday(),
                    accion,
                    ahora.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )

    except Exception:
        logging.exception(
            "Error registrando historial de microhábito %s",
            categoria,
        )


def contar_resultados_en_hora(categoria: str, hora: int, dias_atras: int = 14):
    """
    Cuenta hecho/ignorado/pospuesto para esta categoría en una franja
    horaria cercana (hora-1, hora, hora+1, con wraparound de 24h) en
    los últimos `dias_atras` días. Es la base para que la app aprenda
    qué horarios evitar.
    """

    horas = [(hora - 1) % 24, hora, (hora + 1) % 24]
    desde = (datetime.now(BOGOTA) - timedelta(days=dias_atras)).strftime("%Y-%m-%d %H:%M:%S")

    conteos = {"hecho": 0, "ignorado": 0, "pospuesto": 0}

    try:
        with db_connection() as conn:
            placeholders = ", ".join(["?"] * len(horas))

            filas = fetch_all(
                conn,
                f"""
                SELECT accion, COUNT(*) as total
                FROM microhabitos_historial
                WHERE categoria = ?
                AND hora IN ({placeholders})
                AND timestamp >= ?
                GROUP BY accion
                """,
                (categoria, *horas, desde),
            )

        for fila in filas:
            if fila["accion"] in conteos:
                conteos[fila["accion"]] = fila["total"]

        return conteos

    except Exception:
        logging.exception(
            "Error contando historial de microhábito %s",
            categoria,
        )
        return conteos