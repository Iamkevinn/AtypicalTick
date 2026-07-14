from datetime import datetime, timedelta

from config import BOGOTA


def hace_n_dias_bogota(n: int) -> str:
    return (
        datetime.now(BOGOTA) - timedelta(days=n)
    ).strftime("%Y-%m-%d %H:%M:%S")


def hoy_bogota_str() -> str:
    return datetime.now(BOGOTA).strftime("%Y-%m-%d")