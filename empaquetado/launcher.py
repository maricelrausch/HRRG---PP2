"""
Lanzador de IngenIA Salud – Triage (punto de entrada del .exe).

Al abrir el acceso directo:
  1. Si la app ya está corriendo, solo abre el navegador.
  2. Verifica Ollama y lo inicia si hace falta.
  3. Prepara la identificación cifrada (claves locales) la primera vez.
  4. Si no hay usuarios, pide crear la cuenta de administrador.
  5. Precarga Whisper y MedGemma, levanta Flask con waitress y abre el navegador.

Comandos de administración (desde una consola):
  IngenIA.exe crear-profesional
  IngenIA.exe cambiar-password
  IngenIA.exe asignar-rol
  IngenIA.exe crear-admin        (crea un usuario con rol admin)

Variables de entorno opcionales:
  HRRG_HOST    127.0.0.1 (por defecto, solo esta PC) | 0.0.0.0 (otras PCs de la red)
  HRRG_PUERTO  5000
"""
import os
import sys
import time
import socket
import shutil
import sqlite3
import threading
import subprocess
import traceback
import webbrowser
import urllib.request
from pathlib import Path

CONGELADO = getattr(sys, "frozen", False)
if CONGELADO:
    CARPETA_APP = Path(sys.executable).resolve().parent
else:
    # Modo desarrollo: python empaquetado/launcher.py
    CARPETA_APP = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(CARPETA_APP / "backend"))
    sys.path.insert(0, str(CARPETA_APP / "backend" / "scripts"))

CARPETA_MODELOS = CARPETA_APP / "modelos"
HOST = os.environ.get("HRRG_HOST", "127.0.0.1")
PUERTO = int(os.environ.get("HRRG_PUERTO", "5000"))
URL = f"http://localhost:{PUERTO}/"
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
MODELOS_OLLAMA = [
    os.environ.get("MEDGEMMA_MODELO", "medgemma:4b"),
    "qwen2.5:0.5b",
    "embeddinggemma",
]


# ------------------------------------------------------------ entorno
def configurar_entorno():
    whisper_local = CARPETA_MODELOS / "whisper-small"
    if whisper_local.is_dir():
        os.environ.setdefault("WHISPER_MODELO", str(whisper_local))
    # Todo offline: ni Hugging Face ni telemetría de ChromaDB.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    os.environ.setdefault("OLLAMA_HOST", OLLAMA)
    # Extracción real con MedGemma (la app por defecto usa casos simulados).
    os.environ.setdefault("HRRG_MODO_EXTRACCION", "ia")


def titulo_consola(texto):
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(texto)
        except Exception:
            pass


# ------------------------------------------------------------ utilidades
def puerto_ocupado(puerto):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def get_json(url, timeout=2):
    import json
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ollama_responde():
    try:
        get_json(f"{OLLAMA}/api/version")
        return True
    except Exception:
        return False


def buscar_ollama():
    candidatos = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        base = Path(local) / "Programs" / "Ollama"
        candidatos += [base / "ollama app.exe", base / "ollama.exe"]
    en_path = shutil.which("ollama")
    if en_path:
        candidatos.append(Path(en_path))
    return [c for c in candidatos if c.exists()]


# ------------------------------------------------------------ pasos
def asegurar_ollama():
    if ollama_responde():
        print("[OK] Ollama está corriendo.")
    else:
        ejecutables = buscar_ollama()
        if not ejecutables and os.environ.get("HRRG_EN_DOCKER") == "1":
            # En Docker, Ollama es otro contenedor: solo hay que esperarlo.
            print(f"[..] Esperando a Ollama en {OLLAMA}...")
            for _ in range(90):
                if ollama_responde():
                    break
                time.sleep(1)
            if not ollama_responde():
                print("[AVISO] Ollama no respondió. La app abre igual, pero sin IA.")
                return
            print("[OK] Ollama está corriendo.")
        elif not ejecutables:
            print("[AVISO] No se encontró Ollama. La app abre igual, pero sin IA.")
            print("        Reinstale IngenIA Salud – Triage o instale Ollama.")
            return
        exe = ejecutables[0]
        print(f"[..] Iniciando Ollama ({exe.name})...")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        args = [str(exe)] if exe.name == "ollama app.exe" else [str(exe), "serve"]
        subprocess.Popen(args, creationflags=flags,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            if ollama_responde():
                print("[OK] Ollama iniciado.")
                break
            time.sleep(1)
        else:
            print("[AVISO] Ollama no respondió en 60 s. La app abre igual, sin IA.")
            return

    try:
        instalados = {m["name"] for m in get_json(f"{OLLAMA}/api/tags").get("models", [])}
    except Exception:
        return
    normalizar = lambda n: n if ":" in n else n + ":latest"
    faltan = [m for m in MODELOS_OLLAMA if normalizar(m) not in instalados]
    if faltan:
        print("[AVISO] Faltan modelos en Ollama:", ", ".join(faltan))
    else:
        print("[OK] Modelos de IA disponibles.")


def preparar_identificacion():
    """Crea las claves locales la primera vez (idempotente)."""
    import preparar_identificacion as prep
    argv = sys.argv
    sys.argv = [argv[0]]
    try:
        prep.main()
    finally:
        sys.argv = argv


def ejecutar_cli(app, args, standalone=True):
    from flask.cli import ScriptInfo
    return app.cli.main(args=args, prog_name="IngenIA",
                        obj=ScriptInfo(create_app=lambda: app),
                        standalone_mode=standalone)


def asegurar_administrador(modulo_app, forzar=False):
    import click
    try:
        con = sqlite3.connect(modulo_app.BASE_USUARIOS)
        cantidad = con.execute("SELECT COUNT(*) FROM profesionales").fetchone()[0]
        con.close()
    except sqlite3.Error:
        cantidad = 0
    if cantidad and not forzar:
        return
    if not forzar and not (sys.stdin and sys.stdin.isatty()):
        print("[AVISO] No hay usuarios. Cree el administrador con:")
        print("        docker compose exec app python empaquetado/launcher.py crear-admin")
        print("        (o doble clic en crear_admin.bat)")
        return

    print()
    print("=" * 60)
    print(" Primera ejecución: cree la cuenta de ADMINISTRADOR")
    print(" (la contraseña debe tener al menos 12 caracteres)")
    print("=" * 60)
    while True:
        usuario = input("Usuario: ").strip()
        if not usuario:
            continue
        try:
            ejecutar_cli(modulo_app.app, ["crear-profesional", "--usuario", usuario], standalone=False)
            ejecutar_cli(modulo_app.app, ["asignar-rol", "--usuario", usuario, "--rol", "admin"], standalone=False)
            print(f"[OK] Administrador '{usuario}' creado.\n")
            return
        except click.ClickException as e:
            print("[ERROR]", e.format_message())
        except click.Abort:
            print("\nCancelado.")


def abrir_navegador_cuando_este_listo():
    if os.environ.get("HRRG_ABRIR_NAVEGADOR", "1") == "0":
        return
    def esperar():
        for _ in range(120):
            if puerto_ocupado(PUERTO):
                webbrowser.open(URL)
                return
            time.sleep(0.5)
    threading.Thread(target=esperar, daemon=True).start()


# ------------------------------------------------------------ main
def main():
    titulo_consola("IngenIA Salud – Triage - NO CERRAR esta ventana mientras use el sistema")
    configurar_entorno()
    comando = sys.argv[1:]

    if not comando and puerto_ocupado(PUERTO):
        print("IngenIA Salud – Triage ya está abierto. Abriendo el navegador...")
        webbrowser.open(URL)
        return

    print("IngenIA Salud – Triage - iniciando...\n")
    preparar_identificacion()

    import app as modulo_app   # importa Flask, rutas y bases locales

    if comando == ["crear-admin"]:   # alta del administrador (también en Docker)
        asegurar_administrador(modulo_app, forzar=True)
        return
    if comando:                # comandos de administración
        ejecutar_cli(modulo_app.app, comando)
        return

    asegurar_ollama()
    asegurar_administrador(modulo_app)

    from ia.chat import precargar_modelos
    precargar_modelos()

    from waitress import serve
    abrir_navegador_cuando_este_listo()
    print(f"\n[OK] Sistema disponible en {URL}")
    print("     Para cerrar el sistema, cierre esta ventana.\n")
    serve(modulo_app.app, host=HOST, port=PUERTO, threads=8)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc()
        print("\nOcurrió un error al iniciar IngenIA Salud – Triage.")
        try:
            input("Presione Enter para cerrar...")
        except Exception:
            pass
        sys.exit(1)
