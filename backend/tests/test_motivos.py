"""
D3 (Dario 29/10): motivos de consulta que lista el mail de Francisco Navoni.
La lista tiene que ser la MISMA en el esquema, en las reglas y en las dos pantallas del frontend.
MedGemma sigue con sus 8 categorías (subconjunto), para no cambiar la extracción ya evaluada.
Ejecutar desde backend:  python -m pytest -q tests/test_motivos.py
"""
import re
from pathlib import Path
from typing import get_args

from src.esquemas import Categoria
from src.reglas_hospital import CATEGORIAS, CAMPOS

RAIZ = Path(__file__).resolve().parent.parent.parent
NUEVOS = {"Alteración de conciencia", "Convulsiones", "Hemorragia", "Intoxicación",
          "Reacción alérgica", "Embarazo / obstétrico", "Salud mental"}


def _lista_js(archivo, patron):
    texto = (RAIZ / "frontend" / archivo).read_text(encoding="utf-8")
    bloque = re.search(patron, texto, re.S).group(1)
    return re.findall(r"'([^']+)'", bloque)


def test_misma_lista_en_todos_lados():
    esquema = list(get_args(Categoria))
    assert NUEVOS <= set(esquema) and esquema[-1] == "Otro"
    assert CATEGORIAS == esquema
    assert CAMPOS["motivo_categoria"]["opciones"] == esquema
    assert _lista_js("formulario.js", r"k:'motivo_categoria'.*?opts:\[(.*?)\]") == esquema
    assert _lista_js("validacion.js", r"motivo_categoria:\s*\[(.*?)\]") == esquema


def test_medgemma_propone_un_subconjunto():
    texto = (RAIZ / "backend" / "ia" / "medgemma.py").read_text(encoding="utf-8")
    bloque = re.search(r"^CATEGORIAS = \[(.*?)\]", texto, re.S | re.M).group(1)
    ia = re.findall(r'"([^"]+)"', bloque)
    assert len(ia) == 8 and set(ia) <= set(get_args(Categoria))
