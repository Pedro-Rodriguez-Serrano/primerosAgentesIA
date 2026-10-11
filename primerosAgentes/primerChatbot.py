"""
Este chatbot recuerda la conversación mientras el programa esté abierto.
"""
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

MODELO = "gemini-3.8-flash"

client = genai.Client()

# El "system_instruction" define la personalidad y las reglas del chatbot
chat = client.chats.create(
    model=MODELO,
    config=types.GenerateContentConfig(
        system_instruction=(
            "Eres un viejo amigo del usuario con el que te comunicas"
            "Explica con ejemplos sencillos y responde en español."
            "Tienes interes por conocer a la persona"
            "Te llamas 'ChatboyBuddy', presentate al pricipio"
        ),
    ),
)


def enviar(mensaje: str) -> str:
    """Envía un mensaje al chat; reintenta si Google está saturado (503)."""
    for intento in range(5):
        try:
            return chat.send_message(mensaje).text
        except errors.ServerError:
            espera = 2 ** intento
            print(f"   (servidor ocupado, reintento en {espera}s)")
            time.sleep(espera)
    return "Google sigue saturado, prueba más tarde."


print("Chatbot listo. Escribe 'salir' para terminar.\n")

while True:
    texto = input("Tú: ").strip()
    if texto.lower() in ("salir", "exit", "quit"):
        print("¡Hasta luego!")
        break
    if not texto:
        continue
    print(f"Bot: {enviar(texto)}\n")