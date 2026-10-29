# Imagen de la app IngenIA Salud – Triage (Flask + Whisper + RAG).
# Ollama corre en otro contenedor (ver docker-compose.yml).
# Se construye desde la raíz del repo:  docker compose build   (desde la carpeta docker/)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1) Dependencias (capa aparte: solo se reinstala si cambia requirements.txt)
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt waitress==3.0.2

# 2) Usuario sin privilegios y carpetas de datos (los volúmenes heredan estos permisos)
RUN useradd --create-home --uid 1000 ingenia \
 && mkdir -p /home/ingenia/.hrrg_pp2 /home/ingenia/.hrrg_pp2_claves /app/modelos \
 && chown -R ingenia:ingenia /home/ingenia /app

# 3) Modelo de voz dentro de la imagen: el contenedor funciona sin internet
USER ingenia
RUN python -c "from faster_whisper.utils import download_model; download_model('small', output_dir='/app/modelos/whisper-small')"

# 4) Código de la app (lo que más cambia, al final)
COPY --chown=ingenia:ingenia backend /app/backend
COPY --chown=ingenia:ingenia frontend /app/frontend
COPY --chown=ingenia:ingenia empaquetado/launcher.py /app/empaquetado/launcher.py

ENV HRRG_EN_DOCKER=1 \
    HRRG_HOST=0.0.0.0 \
    HRRG_PUERTO=5000 \
    HRRG_ABRIR_NAVEGADOR=0 \
    HRRG_MODO_EXTRACCION=ia \
    OLLAMA_HOST=http://ollama:11434 \
    WHISPER_MODELO=/app/modelos/whisper-small \
    HF_HUB_OFFLINE=1 \
    ANONYMIZED_TELEMETRY=False

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/', timeout=4)"

CMD ["python", "empaquetado/launcher.py"]
