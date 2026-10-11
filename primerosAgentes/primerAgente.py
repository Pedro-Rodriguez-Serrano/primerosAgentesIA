"""
Agente de apuntes: lee los archivos de la carpeta 'apuntes' y guarda un resumen.

Pasos para ejecución:
    1. Crea una carpeta 'apuntes' junto a este archivo con algunos .txt dentro.
    2. Guarda tu clave en un archivo .env:  GEMINI_API_KEY=tu-clave
    3. Ejecutar: python agente_apuntes.py
"""
import os
import time

from google import genai
from google.genai import errors, types

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MODELO = "gemini-3.8-flash"
CARPETA_APUNTES = "apuntes"
CARPETA_RESUMENES = "resumenes"
MAX_PASOS = 10                # límite de seguridad: evita bucles infinitos

client = genai.Client()


# ---------------------------------------------------------------
# 1) HERRAMIENTAS: lo que el agente puede hacer en tu ordenador
# ---------------------------------------------------------------
def listar_archivos() -> str:
    """Lista los archivos de texto disponibles en la carpeta de apuntes."""
    if not os.path.isdir(CARPETA_APUNTES):
        return f"Error: no existe la carpeta '{CARPETA_APUNTES}'."
    archivos = sorted(f for f in os.listdir(CARPETA_APUNTES) if f.endswith(".txt"))
    return "\n".join(archivos) if archivos else "La carpeta está vacía."


def leer_archivo(nombre: str) -> str:
    """Lee y devuelve el contenido de un archivo de apuntes.

    Args:
        nombre: nombre del archivo, tal como aparece en listar_archivos.
    """
    nombre = os.path.basename(nombre)  # seguridad: solo archivos de esa carpeta
    ruta = os.path.join(CARPETA_APUNTES, nombre)
    try:
        with open(ruta, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        return f"Error al leer '{nombre}': {e}"


def guardar_resumen(nombre: str, texto: str) -> str:
    """Guarda un resumen en un archivo dentro de la carpeta de resúmenes.

    Args:
        nombre: nombre del archivo de salida, por ejemplo 'resumen_general.txt'.
        texto: contenido del resumen.
    """
    os.makedirs(CARPETA_RESUMENES, exist_ok=True)
    nombre = os.path.basename(nombre)
    ruta = os.path.join(CARPETA_RESUMENES, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(texto)
    return f"Resumen guardado en {ruta}"


FUNCIONES = {f.__name__: f for f in (listar_archivos, leer_archivo, guardar_resumen)}

CONFIG = types.GenerateContentConfig(
    tools=list(FUNCIONES.values()),
    # Desactivamos el bucle automático del SDK para escribirlo nosotros y verlo
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    system_instruction=(
        "Eres un asistente de estudio. Trabajas con archivos de apuntes usando "
        "tus herramientas. No inventes contenido: lee siempre los archivos antes "
        "de resumirlos. Cuando termines, explica brevemente qué hiciste."
    ),
)


# ---------------------------------------------------------------
# 2) LLAMADA AL MODELO, con reintentos si Google está saturado (503)
# ---------------------------------------------------------------
def llamar_modelo(contenidos):
    for intento in range(5):
        try:
            return client.models.generate_content(
                model=MODELO, contents=contenidos, config=CONFIG
            )
        except errors.ServerError:
            espera = 2 ** intento
            print(f"   (servidor ocupado, reintento en {espera}s)")
            time.sleep(espera)
    raise RuntimeError("Google sigue saturado, prueba más tarde.")


# ---------------------------------------------------------------
# 3) EL AGENTE: el bucle que decide, actúa, observa y repite
# ---------------------------------------------------------------
def agente(objetivo: str) -> str:
    contenidos = [types.Content(role="user", parts=[types.Part(text=objetivo)])]

    for paso in range(1, MAX_PASOS + 1):
        resp = llamar_modelo(contenidos)
        contenidos.append(resp.candidates[0].content)   # guarda lo que dijo el modelo

        llamadas = resp.function_calls
        if not llamadas:                 # no pide más herramientas: ha terminado
            return resp.text

        resultados = []
        for llamada in llamadas:
            args = dict(llamada.args or {})
            print(f"[paso {paso}] Herramienta: {llamada.name}({args})")
            try:
                salida = FUNCIONES[llamada.name](**args)
            except Exception as e:       # si falla, se lo contamos al modelo
                salida = f"Error ejecutando la herramienta: {e}"
            resultados.append(
                types.Part.from_function_response(
                    name=llamada.name, response={"result": salida}
                )
            )
        contenidos.append(types.Content(role="user", parts=resultados))

    return "Se alcanzó el límite de pasos sin terminar la tarea."


if __name__ == "__main__":
    respuesta = agente(
        "Resume mis apuntes: revisa qué archivos hay, léelos y guarda un "
        "resumen general en 'resumen_general.txt'."
    )
    print("\n=== RESPUESTA FINAL ===")
    print(respuesta)