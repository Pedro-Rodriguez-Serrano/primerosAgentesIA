import time
from datetime import datetime
from google import genai
from google.genai import types
from google.genai import errors

client = genai.Client()  # lee GEMINI_API_KEY del entorno

def hora_actual() -> str:
    """Devuelve la fecha y hora actuales."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def sumar(a: float, b: float) -> float:
    """Suma dos números."""
    return a + b

def pedir(pregunta):
    for intento in range(5):
        try:
            return client.models.generate_content(
                model="gemini-3.8-flash",
                contents=pregunta,
                config=types.GenerateContentConfig(tools=[hora_actual, sumar]),
            )
        except errors.ServerError as e:
            espera = 2 ** intento   # 1, 2, 4, 8, 16 segundos
            print(f"Servidor ocupado, reintentando en {espera}s...")
            time.sleep(espera)
    raise RuntimeError("Google sigue saturado, prueba más tarde.")

resp = pedir("¿Qué hora es y cuánto es 1234 + 5678?")
print(resp.text)