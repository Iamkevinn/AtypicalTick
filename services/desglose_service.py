# services/desglose_service.py

import logging

from core.discrepancia_emocional import detectar_discrepancia_motivo
from core.efectividad_historica_v2 import obtener_efectividad_historica

from services.gemini_service import generar_desglose
from services.intervenciones_service import preparar_intervencion, construir_metadata
from services.prompt_service import construir_prompt_desglose
from db.interacciones import registrar_interaccion


def generar_desglose_completo(peticion):
    """
    Orquesta todo el proceso de generación del desglose IA.

    Flujo:

    1. Analiza el contexto psicológico.
    2. Registra la interacción.
    3. Consulta aprendizaje histórico.
    4. Construye el prompt.
    5. Consulta Gemini.
    6. Devuelve el resultado enriquecido.
    """

    contexto = preparar_intervencion(
        carpeta=peticion.carpeta,
        titulo_tarea=peticion.titulo_tarea,
        etiquetas=peticion.etiquetas,
        motivo=peticion.motivo,
        patron_historico=peticion.patron_historico,
    )

    registrar_interaccion(
        tarea_id=peticion.tarea_id,
        tarea_nombre=peticion.titulo_tarea,
        energia=peticion.energia,
        accion="afronto_ansiedad",
        emocion=peticion.motivo,
        carpeta=peticion.carpeta,
        metadata_ia=construir_metadata(contexto),
    )

    insight_discrepancia = detectar_discrepancia_motivo(
        peticion.motivo,
        peticion.energia,
    )

    (
        mejor_intervencion,
        peor_intervencion,
    ) = obtener_efectividad_historica(
        peticion.motivo,
        peticion.energia,
    )

    prompt = construir_prompt_desglose(
        titulo_tarea=peticion.titulo_tarea,
        motivo=peticion.motivo,
        nombre_intervencion=contexto["nombre_intervencion"],
        plantilla_psicologica=contexto["plantilla_psicologica"],
        mejor_intervencion=mejor_intervencion,
        peor_intervencion=peor_intervencion,
    )

    try:

        resultado = generar_desglose(prompt)

        resultado["insight_discrepancia"] = insight_discrepancia
        resultado["nombre_intervencion"] = contexto["nombre_intervencion"]

        return resultado

    except Exception:

        logging.exception(
            "Error consultando Gemini"
        )

        return {
            "pasos": [
                "Abre la aplicación o documento correspondiente.",
                "Lee la primera línea u observa el entorno.",
                "Detente a los 2 minutos y decide si continuar.",
            ],
            "insight_discrepancia": insight_discrepancia,
            "nombre_intervencion": contexto["nombre_intervencion"],
        }