"""Convierte el logo del frontend en icono .ico cuadrado para el .exe y el instalador."""
from pathlib import Path
from PIL import Image

aqui = Path(__file__).resolve().parent
logo = aqui.parent / "frontend" / "img" / "logo-hrrg.png"
salida = aqui / "salida" / "icono.ico"
salida.parent.mkdir(parents=True, exist_ok=True)

img = Image.open(logo).convert("RGBA")
lado = max(img.size)
cuadrado = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
cuadrado.paste(img, ((lado - img.width) // 2, (lado - img.height) // 2))
cuadrado.resize((256, 256), Image.LANCZOS).save(
    salida, sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)]
)
print(f"[OK] Icono creado: {salida}")
