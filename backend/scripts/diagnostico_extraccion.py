"""backend/scripts/diagnostico_extraccion.py · Mide dónde se va el tiempo de la extracción.

Uso (desde la carpeta backend, con el venv activado y Ollama corriendo):
    python scripts\\diagnostico_extraccion.py

No modifica nada: solo mide el RAG, la llamada a MedGemma con RAG y sin RAG.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # carpeta backend

RELATO = ("Mujer de 45 años, diabética, dolor arriba de la panza hace 6 horas, "
          "con náuseas y me siento afiebrada.")


def medir(nombre, fn):
    t = time.time()
    try:
        r = fn()
        print(f"  {nombre:<38} {time.time() - t:6.1f} s")
        return r
    except Exception as e:
        print(f"  {nombre:<38} {time.time() - t:6.1f} s   FALLA: {type(e).__name__}: {str(e)[:120]}")
        return None


print("\n1) RAG (búsqueda en ChromaDB con embeddinggemma)")
rag = medir("importar src.rag (abre ChromaDB)", lambda: __import__("src.rag", fromlist=["buscar_informacion"]))
if rag:
    frag = medir("buscar_informacion (1.ª vez)", lambda: rag.buscar_informacion(RELATO, cantidad=3))
    medir("buscar_informacion (2.ª vez)", lambda: rag.buscar_informacion(RELATO, cantidad=3))
    if frag is not None:
        print(f"  fragmentos devueltos: {len(frag)} · origen: {sorted({str(f.get('fuente', f.get('origen', '?'))) for f in frag})}")

print("\n2) Extracción completa (src.extraccion.extraer_datos)")
from src.esquemas import ExtraccionIA  # noqa: E402
from src import extraccion as ex      # noqa: E402

for usar_rag in (True, False):
    ex.USAR_RAG = usar_rag
    for i in (1, 2):
        medir(f"extracción {'CON' if usar_rag else 'SIN'} RAG · intento {i}",
              lambda: ex.extraer_datos(RELATO, ExtraccionIA))

print("\nSi 'CON RAG' tarda bastante más que 'SIN RAG', la demora es el RAG.")
print("Si el import de src.rag FALLA, se reintenta en cada relato y suma segundos.\n")


# ---------------------------------------------------------------- 3) llamada directa a MedGemma
print("3) Llamada directa a MedGemma: qué genera y cuánto")
import json  # noqa: E402

esquema = ExtraccionIA.model_json_schema()
mensajes = ex._mensajes(RELATO, "")


def llamar(nombre, formato, opciones):
    t = time.time()
    try:
        r = ex._cli().chat(model=ex.LLM_MODEL, messages=mensajes, format=formato,
                           options=opciones, keep_alive="30m")
    except Exception as e:
        print(f"  {nombre:<38} FALLA: {e}")
        return
    seg = time.time() - t
    txt = r["message"]["content"]
    blancos = sum(c.isspace() for c in txt)
    tokens = r.get("eval_count")
    vel = (tokens / (r.get("eval_duration") or 1) * 1e9) if tokens else 0
    print(f"  {nombre:<38} {seg:6.1f} s · tokens generados {tokens} ({vel:.0f}/s) · "
          f"largo {len(txt)} caracteres, {blancos} en blanco")
    try:
        json.loads(txt)
    except Exception:
        print("     ⚠ JSON inválido")
    return txt


txt = llamar("esquema actual (Pydantic, 20 campos)", esquema, {"temperature": 0})
if txt:
    print("     primeros 300 caracteres:", repr(txt[:300]))
llamar("esquema actual + tope num_predict 400", esquema, {"temperature": 0, "num_predict": 400})
simple = {"type": "object", "properties": {k: {"type": ["string", "number", "boolean", "null"]}
                                           for k in esquema.get("properties", {})},
          "required": list(esquema.get("properties", {}))}
llamar("esquema simplificado (mismos campos)", simple, {"temperature": 0})
llamar("sin esquema (format='json')", "json", {"temperature": 0})
print()
