# services/prompt_service.py

def construir_prompt_desglose(
    titulo_tarea: str,
    motivo: str,
    nombre_intervencion: str,
    plantilla_psicologica: str,
    mejor_intervencion: str | None,
    peor_intervencion: str | None,
):
    """
    Construye el prompt enviado a Gemini.
    """

    instruccion_adaptativa = ""

    # Defensa extra: si por alguna razón mejor y peor coinciden (dato
    # ambiguo/contradictorio), no le mandamos a Gemini "replica esto" y
    # "evita esto" sobre la misma intervención en el mismo prompt.
    if mejor_intervencion and mejor_intervencion == peor_intervencion:
        peor_intervencion = None

    if mejor_intervencion:
        instruccion_adaptativa += (
            f"\n- LO QUE SI FUNCIONA: "
            f"El historial muestra que el usuario actúa cuando usas "
            f"'{mejor_intervencion}'. Replica esta estructura."
        )

    if peor_intervencion:
        instruccion_adaptativa += (
            f"\n- LO QUE LO BLOQUEA (EVITAR ESTO): "
            f"Cuando usas '{peor_intervencion}', el usuario se paraliza "
            f"o abandona. Aléjate completamente de ese enfoque."
        )

    return f"""
Eres un entrenador conductual.

El usuario está bloqueado.

Tarea:
"{titulo_tarea}"

Motivo:
"{motivo}"

INTERVENCIÓN BASE:
{nombre_intervencion}

Lógica:
{plantilla_psicologica}

=== APRENDIZAJE DEL SISTEMA ===
{instruccion_adaptativa}
===============================

INSTRUCCIÓN CLÍNICA:

1. Usa máximo UNA oración de contexto.
2. No hagas reflexión.
3. Da instrucciones físicas.
4. El paso 3 DEBE llamarse exactamente:

Accion de 30 segundos:

Devuelve EXACTAMENTE este JSON:

{{
  "pasos":[
    "...",
    "...",
    "Accion de 30 segundos: ..."
  ]
}}
"""