import json


def preparar_intervencion(
    carpeta: str,
    titulo_tarea: str,
    etiquetas: list[str],
    motivo: str,
    patron_historico: str | None = None,
):
    """
    Analiza la tarea y decide cuál es la intervención psicológica
    más adecuada.
    """

    motivo = motivo.lower()
    carpeta = carpeta.lower()
    titulo = titulo_tarea.lower()

    etiquetas_texto = " ".join(
        t.lower()
        for t in etiquetas
    )

    score_salud = 0
    score_burocracia = 0
    score_social = 0

    # ---------- Carpetas ----------

    if any(c in carpeta for c in ("health", "salud")):
        score_salud += 2

    if any(c in carpeta for c in ("finanzas", "banco")):
        score_burocracia += 2

    # ---------- Etiquetas ----------

    if "medicina" in etiquetas_texto:
        score_salud += 5

    if "ansiedad" in etiquetas_texto:
        score_social += 3

    if "pago" in etiquetas_texto:
        score_burocracia += 3

    # ---------- Palabras del título ----------

    if any(w in titulo for w in (
        "pastilla",
        "medico",
        "meds",
        "cita medica",
    )):
        score_salud += 4

    if any(w in titulo for w in (
        "pagar",
        "transferir",
        "impuesto",
        "tramite",
    )):
        score_burocracia += 4

    if any(w in titulo for w in (
        "llamar",
        "escribir a",
        "responder",
        "correo a",
        "mensaje",
    )):
        score_social += 3

    if any(w in titulo for w in (
        "aprender",
        "curso",
        "leer",
        "estudiar",
    )):
        score_burocracia -= 5
        score_social -= 5

    es_salud = score_salud >= 4
    es_burocracia = score_burocracia >= 4
    es_ansiedad_social = score_social >= 3

    if es_salud:

        nombre = "Intervencion de Salud Fisica"

        plantilla = (
            "Paso 1: Pon el elemento (vaso/pastilla/telefono) frente a ti. "
            "Paso 2: Ejecuta el movimiento fisico basico sin pensarlo. "
            "Paso 3: Marca como completado."
        )

    elif es_burocracia:

        nombre = "Reduccion de Incertidumbre Financiera"

        plantilla = (
            "Paso 1: Abre la pestaña/app del banco o documento. "
            "Paso 2: Mira el monto exacto o la informacion que falta. "
            "Paso 3: Cierra la app o mantenla abierta."
        )

    elif es_ansiedad_social:

        nombre = "Exposicion Segura de Comunicacion"

        plantilla = (
            "Paso 1: Abre una app de notas."
            " Paso 2: Escribe un borrador horrible."
            " Paso 3: Copialo y acercate al chat."
        )

    elif "perfecto" in motivo or "listo" in motivo:

        nombre = "Ruptura de Perfeccionismo"

        plantilla = (
            "Paso 1: Crea una version desordenada."
            " Paso 2: Identifica el requisito minimo."
            " Paso 3: Haz la peor version posible."
        )

    elif any(x in motivo for x in (
        "empezar",
        "abruma",
        "grande",
    )):

        nombre = "Reduccion de Sobrecarga (Inercia)"

        plantilla = (
            "Paso 1: Sientate frente a la tarea."
            " Paso 2: Haz una accion absurda."
            " Paso 3: Trabaja una micro-unidad."
        )

    elif any(x in motivo for x in (
        "ansiedad",
        "miedo",
    )):

        nombre = "Exposicion Conductual"

        plantilla = (
            "Paso 1: Observa la tarea."
            " Paso 2: Di en voz alta qué incomoda."
            " Paso 3: Acércate un poco."
        )

    elif any(x in motivo for x in (
        "agotado",
        "energia",
    )):

        historial = (
            patron_historico.lower()
            if patron_historico
            else ""
        )

        if (
            "ansiedad" in historial
            or "miedo" in historial
        ):

            nombre = "Intervencion de Activacion Amigdalina"

            plantilla = (
                "Paso 1: Reconoce que la tensión parece cansancio."
                " Paso 2: Estírate 5 segundos."
                " Paso 3: Toca el objeto."
            )

        else:

            nombre = "Acomodacion a Friccion Fisica"

            plantilla = (
                "Paso 1: Hazlo desde donde estás."
                " Paso 2: Hazlo al 10%."
                " Paso 3: Decide tras dos minutos."
            )

    elif (
        "entiendo" in motivo
        or "claridad" in motivo
    ):

        nombre = "Despeje de Incertidumbre"

        plantilla = (
            "Paso 1: Localiza la duda."
            " Paso 2: Escríbela."
            " Paso 3: Busca quién la responde."
        )

    else:

        nombre = "Activacion Estandar"

        plantilla = (
            "Paso 1: Abre los recursos."
            " Paso 2: Haz un movimiento."
            " Paso 3: Para a los dos minutos."
        )

    return {
        "nombre_intervencion": nombre,
        "plantilla_psicologica": plantilla,
        "score_salud": score_salud,
        "score_burocracia": score_burocracia,
        "score_social": score_social,
    }


def construir_metadata(intervencion: dict) -> str:
    """
    Convierte los scores clínicos a JSON para almacenarlos.
    """

    return json.dumps({
        "score_salud": intervencion["score_salud"],
        "score_buro": intervencion["score_burocracia"],
        "score_social": intervencion["score_social"],
    })