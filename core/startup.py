import logging
import subprocess
import sys


def inicializar_backend(init_db=None):
    """
    Inicializa el schema de la base de datos corriendo las migraciones
    de Alembic ("alembic upgrade head").

    NOTA (Fase 2 - migración Supabase/Render):
    Antes, esta función llamaba una por una a 7 funciones init_tabla_*()
    repartidas en distintos archivos (main.py, auth_service.py,
    auth_ticktick.py, y en core/: feedback_discrepancia.py,
    prediccion_vs_resultado.py, correccion_decisiones.py,
    gestion_horario_estricto.py). Cada una hacía su propio
    "CREATE TABLE IF NOT EXISTS", sin versionado ni forma de hacer
    rollback si algo salía mal.

    Ahora todo ese schema vive en alembic/versions/ como migraciones
    versionadas (ver alembic/versions/542826e5466e_esquema_inicial.py
    para el estado inicial). Este archivo ya NO llama a init_tabla_*();
    esas funciones se mantienen en su lugar de origen únicamente por si
    algún otro código las importa todavía, pero no deberían usarse para
    crear tablas nunca más -- usar "alembic revision" + "alembic upgrade
    head" para cualquier cambio de schema futuro.

    El parámetro init_db se mantiene por compatibilidad con el código
    que llama a inicializar_backend(init_db) desde main.py, pero ya no
    se usa (init_db() en main.py también quedará obsoleto una vez se
    confirme que todo corre bien con Alembic).
    """

    logging.info("Inicializando backend (alembic upgrade head)...")

    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )

    if resultado.returncode != 0:
        logging.error(
            "Error corriendo migraciones de Alembic:\nSTDOUT: %s\nSTDERR: %s",
            resultado.stdout,
            resultado.stderr,
        )
        raise RuntimeError("No se pudieron aplicar las migraciones de Alembic al iniciar el backend.")

    logging.info("Backend inicializado correctamente (schema al día segun Alembic).")