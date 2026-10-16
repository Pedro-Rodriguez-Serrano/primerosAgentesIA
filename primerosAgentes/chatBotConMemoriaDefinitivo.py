"""
Este chatbot recuerda la conversación mientras el programa esté abierto.
Al arrancar, lee el informe de sesiones anteriores (si existe) para recordar al usuario.
Cuando el usuario se despide (con cualquier frase), el propio chatbot lo detecta,
se despide, actualiza el informe con lo que ha aprendido y cierra el programa.
"""
import json
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

MODELO = "gemini-3.8-flash"
INFORME = "informe_usuario.json"
MARCA_FIN = "[FIN]"   # señal que el chatbot añade al final de su mensaje de despedida

client = genai.Client()

INSTRUCCIONES = (
    "Eres un viejo amigo del usuario con el que te comunicas. "
    "Explica con ejemplos sencillos y responde en español. "
    "Tienes interés por conocer a la persona. "
    "Te llamas 'ChatBot'. "
    "Si el usuario se despide, con cualquier expresión (adiós, chao, me voy a dormir, no quiero seguir hablando, "
    "hablamos mañana, etc.), responde con una despedida breve y cálida "
    f"y termina tu mensaje con {MARCA_FIN}. No uses {MARCA_FIN} en ningún otro caso."
)

PROMPT_INFORME = (
    "Con la conversación anterior, elabora un informe SOLO con datos sobre el usuario; "
    "no resumas la conversación. Devuelve únicamente un JSON con estas claves: "
    '"nombre" (texto o null), '
    '"datos" (lista de datos personales: edad, ciudad, estudios, trabajo...), '
    '"intereses" (lista), '
    '"temas_pendientes" (lista de temas de los que quedó por hablar). '
    "No inventes nada: incluye solo lo que el usuario haya dicho. "
    "Ignora los avisos del sistema entre corchetes. "
    "Si hay un informe previo, actualízalo conservando lo que siga siendo válido "
    "y quitando los temas pendientes que ya se hayan tratado.\n"
    "Informe previo: {previo}"
)


def cargar_informe() -> dict:
    """Lee el informe de sesiones anteriores; devuelve {} si no existe o está dañado."""
    if os.path.exists(INFORME):
        try:
            with open(INFORME, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def construir_instrucciones() -> str:
    """Añade al comportamiento del bot lo que sabe del usuario, si ya lo conoce."""
    informe = cargar_informe()
    if not informe:
        return INSTRUCCIONES + " Es la primera vez que hablas con esta persona: preséntate."
    return INSTRUCCIONES + (
        " Ya conoces a esta persona de conversaciones anteriores, así que no te presentes "
        "como si fuera la primera vez. Esto es lo que sabes de ella; úsalo con naturalidad, "
        "sin recitarlo como una lista, y pregunta por los temas pendientes si encaja: "
        + json.dumps(informe, ensure_ascii=False)
    )


# El "system_instruction" define la personalidad y las reglas del chatbot
chat = client.chats.create(
    model=MODELO,
    config=types.GenerateContentConfig(system_instruction=construir_instrucciones()),
)


def con_reintentos(funcion, *args, **kwargs):
    """Ejecuta una llamada a Gemini; reintenta hasta 5 veces si Google está saturado (503)."""
    for intento in range(5):
        try:
            return funcion(*args, **kwargs)
        except errors.ServerError:
            espera = 2 ** intento
            print(f"   (servidor ocupado, reintento en {espera}s)")
            time.sleep(espera)
    return None


def enviar(mensaje: str):
    """Envía un mensaje al chat. Devuelve el texto de respuesta o None si falla."""
    resp = con_reintentos(chat.send_message, mensaje)
    return (resp.text or None) if resp else None


def guardar_informe() -> None:
    """Pide a Gemini un informe con datos del usuario y lo guarda en un JSON."""
    previo = json.dumps(cargar_informe(), ensure_ascii=False)
    peticion = types.Content(
        role="user",
        parts=[types.Part(text=PROMPT_INFORME.format(previo=previo))],
    )
    resp = con_reintentos(
        client.models.generate_content,
        model=MODELO,
        contents=chat.get_history() + [peticion],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    if resp is None:
        print("No pude generar el informe porque Google está saturado.")
        return
    try:
        informe = json.loads(resp.text)
    except (json.JSONDecodeError, TypeError):
        print("No pude interpretar el informe; no se guardó.")
        return
    with open(INFORME, "w", encoding="utf-8") as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)
    print(f"(Informe guardado en {INFORME})")


print("Chatbot listo. Despídete cuando quieras terminar.\n")

try:
    # El bot habla primero, para que se note que te recuerda (o se presente si es la primera vez)
    saludo = enviar("[Aviso del sistema: el usuario acaba de abrir el chat. Salúdalo tú primero.]")
    if saludo:
        print(f"Bot: {saludo.replace(MARCA_FIN, '').strip()}\n")

    while True:
        texto = input("Tú: ").strip()
        if not texto:
            continue

        respuesta = enviar(texto)
        if not respuesta:
            print("Bot: Google sigue saturado, prueba de nuevo en un rato.\n")
            continue

        termina = MARCA_FIN in respuesta
        print(f"Bot: {respuesta.replace(MARCA_FIN, '').strip()}\n")

        if termina:   # el chatbot ha detectado la despedida
            guardar_informe()
            break
except (KeyboardInterrupt, EOFError):
    print("\nPrograma cerrado sin despedida: no se ha guardado el informe.")