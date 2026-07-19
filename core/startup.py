import logging

from services.auth_ticktick import init_tabla_tokens
from services.auth_service import init_tabla_sesiones

from core.feedback_discrepancia import init_tabla_feedback
from core.prediccion_vs_resultado import init_tabla_predicciones
from core.correccion_decisiones import init_tabla_correcciones
from core.gestion_horario_estricto import init_tabla_lock_horario_estricto


def inicializar_backend(init_db):
    """
    Inicializa todas las tablas y recursos necesarios del backend.
    """

    logging.info("Inicializando backend...")

    init_db()

    init_tabla_feedback()

    init_tabla_predicciones()

    init_tabla_correcciones()

    init_tabla_lock_horario_estricto()

    init_tabla_tokens()

    init_tabla_sesiones()

    logging.info("Backend inicializado correctamente.")