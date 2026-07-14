# services/gemini_service.py
import json
import logging
import os

import requests


def generar_desglose(prompt: str):
    """
    Envía el prompt a Gemini y devuelve el JSON generado.

    Lanza excepción si ocurre cualquier error para que
    el endpoint decida cómo responder.
    """

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("No existe GEMINI_API_KEY")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    respuesta = requests.post(
        url,
        headers={
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=15,
    )

    respuesta.raise_for_status()

    texto = (
        respuesta.json()["candidates"][0]
        ["content"]["parts"][0]["text"]
    )

    return json.loads(texto)