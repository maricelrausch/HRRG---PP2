"""Descarga el modelo de voz para incluirlo en el instalador (se usa una sola vez, con internet)."""
import os
import sys
from pathlib import Path

from faster_whisper.utils import download_model

TAMANO = os.environ.get("WHISPER_MODELO_EMPAQUETAR", "small")
destino = Path(__file__).resolve().parent / "salida" / "modelos" / "whisper-small"
destino.mkdir(parents=True, exist_ok=True)
download_model(TAMANO, output_dir=str(destino))
print(f"[OK] Whisper '{TAMANO}' descargado en {destino}")
sys.exit(0)
