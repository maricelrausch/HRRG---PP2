# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: genera salida/dist/IngenIA/ (IngenIA.exe + _internal/).
# Se ejecuta desde construir.bat.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

EMPAQUETADO = Path(SPECPATH)
RAIZ = EMPAQUETADO.parent
BACK = RAIZ / "backend"

# Módulos que NO van al instalador (entrenamiento de BETO, usan torch/transformers).
EXCLUIR_SRC = {
    "src.entrenar_nlp",
    "src.preparar_entrenamiento",
    "src.datos_entrenamiento",
    "src.procesamiento_nlp",
}

datas = [
    (str(BACK / "datos"), "datos"),
    (str(BACK / "src" / "base_conocimiento"), "src/base_conocimiento"),
]
binaries = []
def modulos_locales(paquete):
    """Lista todos los .py del paquete, incluidas subcarpetas (src no tiene __init__.py).
    Los archivos nuevos se incluyen solos al recompilar."""
    nombres = []
    for py in (BACK / paquete).rglob("*.py"):
        if "__pycache__" in py.parts or "tests" in py.parts:
            continue
        partes = list(py.relative_to(BACK).with_suffix("").parts)
        if partes[-1] == "__init__":
            partes = partes[:-1]
        nombre = ".".join(partes)
        if nombre not in EXCLUIR_SRC:
            nombres.append(nombre)
    return nombres

hiddenimports = (
    ["app", "preparar_identificacion", "waitress"]
    + modulos_locales("src")
    + modulos_locales("ia")
)

# numpy 2.x: se recolecta completo (si no, falta numpy._core._exceptions y Whisper no carga)
for paquete in ("numpy", "chromadb", "chromadb_rust_bindings", "faster_whisper",
                "ctranslate2", "av", "tokenizers", "onnxruntime"):
    try:
        d, b, h = collect_all(paquete)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as e:
        print(f"[spec] no se pudo recolectar {paquete}: {e}")

a = Analysis(
    [str(EMPAQUETADO / "launcher.py")],
    pathex=[str(BACK), str(BACK / "scripts")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["torch", "transformers", "tensorflow", "matplotlib",
              "IPython", "jupyter", "pytest", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="IngenIA",
    console=True,                       # la ventana muestra el estado; cerrarla apaga el sistema
    icon=str(EMPAQUETADO / "salida" / "icono.ico"),
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="IngenIA",
    upx=False,
)
