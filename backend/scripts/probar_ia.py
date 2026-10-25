"""backend/scripts/probar_ia.py · Prueba MedGemma sin levantar Flask.
Uso (desde backend):  python scripts/probar_ia.py
"""
import json
import time

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # carpeta backend
from ia import medgemma as ia

RELATO = ("Mujer de 45 años, diabética, consulta por dolor abdominal arriba de la panza "
          "hace 6 horas, intensidad 8/10, con náuseas. TA 130/80, FC 95, temp 38.2.")

print("Modelo:", ia.MODELO, "| disponible:", ia.disponible())

t = time.time()
datos = ia.extraer(RELATO)
print(f"\n1) EXTRACCIÓN ({time.time() - t:.1f}s)")
print(json.dumps(datos, ensure_ascii=False, indent=2))

t = time.time()
sug = ia.sugerir(datos)
print(f"\n2) SUGERENCIA ({time.time() - t:.1f}s)")
print(json.dumps(sug, ensure_ascii=False, indent=2))

t = time.time()
resp = ia.consultar("¿Por qué ese color?", datos, sug["color"])
print(f"\n3) CHAT ({time.time() - t:.1f}s)\n{resp}")
