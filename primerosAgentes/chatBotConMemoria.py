"""
Chatbot con memoria permanente y despedida inteligente.

- Guarda la conversación en 'conversacion.json' y la recupera al volver a abrirlo.
- Si te despides (con cualquier palabra), la IA se despide y el programa termina.
- 'salir' también cierra el programa de forma inmediata.
"""
import json
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

MODELO = "gemini-3.8-flash"        # si da 404, copia el nombre exacto desde AI Studio
ARCHIVO = "conversacion.json"
MAX_MENSAJES = 40                  # cuántos mensajes antiguos recuerda (ahorra tokens)
MARCA_FIN = "[FIN]"

INSTRUCCION = (
    "Eres un tutor amable que ayuda a un estudiante. "
    "Explica con ejemplos sencillos y responde en español. "
    "Si el usuario se despide (adiós, chao, hasta luego, me voy, buenas noches, "
    "gracias por todo, etc.), responde con una despedida breve y cálida y termina "
    f"tu mensaje con {MARCA_FIN}. No uses {MARCA_FIN} en ningún otro caso."
)

client = genai.Client()


# --------- Memoria en archivo ---------
def cargar() -> list:
    if os.path.exists(ARCHIVO):
        try:
            with open(ARCHIVO, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            print("No pude leer el historial, empiezo de cero.")
    return []


def guardar(mensajes: list) -> None:
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(mensajes, f, ensure_ascii=False, indent=2)


mensajes = cargar()   # Datos de conversaciones viejas: {"role": "user" | "model", "text": "..."}

# Reconstruimos el historial para que el modelo "recuerde" sesiones anteriores
historial = [
    types.Content(role=m["role"], parts=[types.Part(text=m["text"])])
    for m in mensajes[-MAX_MENSAJES:]
]

chat = client.chats.create(
    model=MODELO,
    history=historial,
    config=types.GenerateContentConfig(system_instruction=INSTRUCCION),
)


# --------- Envío con reintentos ---------
def enviar(texto: str):
    for intento in range(5):
        try:
            return chat.send_message(texto).text
        except errors.ServerError:
            espera = 2 ** intento
            print(f"   (servidor ocupado, reintento en {espera}s)")
            time.sleep(espera)
    return None


# --------- Bucle principal ---------
if mensajes:
    print(f"Recuerdo nuestra conversación anterior ({len(mensajes)} mensajes).")
print("Chatbot listo. Despídete cuando quieras.\n")

while True:
    texto = input("Tú: ").strip()
    if not texto:
        continue
    if texto.lower() in ("salir", "exit", "quit"):
        print("Bot: ¡Hasta luego!")
        break

    respuesta = enviar(texto)
    if respuesta is None:
        print("Bot: Google sigue saturado, prueba de nuevo en un rato.\n")
        continue

    termina = MARCA_FIN in respuesta
    respuesta = respuesta.replace(MARCA_FIN, "").strip()

    # Solo guardamos el intercambio si salió bien
    mensajes.append({"role": "user", "text": texto})
    mensajes.append({"role": "model", "text": respuesta})
    guardar(mensajes)

    print(f"Bot: {respuesta}\n")
    if termina:
        break