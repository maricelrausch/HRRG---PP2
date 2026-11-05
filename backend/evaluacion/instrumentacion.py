"""backend/evaluacion/instrumentacion.py · Rendimiento técnico durante la evaluación (sin tocar la app).

1. MedidorOllama: mientras está activo, anota lo que Ollama devuelve en CADA llamada a un modelo
   (tokens de entrada y salida, tiempos de carga, lectura y generación). Envuelve ollama.Client.chat
   y ollama.Client.generate solo durante la evaluación: src/extraccion.py e ia/medgemma.py no cambian.
   En las llamadas a chat pide además las probabilidades de cada token (logprobs), que no cambian la
   respuesta, para calcular la perplejidad. Si el servidor de Ollama no las acepta, sigue sin ellas.

2. MonitorRecursos: un hilo que toma una muestra por segundo de la GPU NVIDIA (nvidia-smi: estado de
   energía, uso, memoria, reloj, consumo) y, si está psutil, de la CPU y la RAM del sistema.
   Si la PC no tiene NVIDIA (como la de la guardia), informa solo CPU y RAM.

Uso:
    with MedidorOllama() as med, MonitorRecursos() as mon:
        med.etapa = "extraccion"
        ...                                     # llamadas normales a la app
    med.resumen(), mon.resumen()
"""
from __future__ import annotations

import math
import shutil
import subprocess
import threading
import time

from . import metricas as M

NS = 1e9


def _campo(r, nombre):
    """Las respuestas de ollama 0.6 aceptan r.campo y r["campo"]; se prueba de las dos formas."""
    v = getattr(r, nombre, None)
    if v is None:
        try:
            v = r[nombre]
        except Exception:
            v = None
    return v


# ================================================================= 1. tokens y tiempos por llamada

class MedidorOllama:
    def __init__(self, pedir_logprobs: bool = True):
        self.llamadas: list[dict] = []
        self.etapa = "general"
        self._originales = {}
        self.logprobs = pedir_logprobs          # pasa a False si el servidor no las acepta

    def _envolver(self, nombre):
        import ollama
        original = getattr(ollama.Client, nombre)
        medidor = self

        def envuelta(cliente, *args, **kwargs):
            t0 = time.perf_counter()
            if nombre == "chat" and medidor.logprobs and "logprobs" not in kwargs and not kwargs.get("stream"):
                try:
                    r = original(cliente, *args, logprobs=True, **kwargs)
                except Exception as e:
                    if "logprob" not in str(e).lower() and not isinstance(e, TypeError):
                        raise
                    medidor.logprobs = False            # versión sin soporte: se sigue sin pedirlas
                    r = original(cliente, *args, **kwargs)
            else:
                r = original(cliente, *args, **kwargs)
            if not kwargs.get("stream"):
                medidor._anotar(r, kwargs.get("model"), time.perf_counter() - t0)
            return r

        self._originales[nombre] = original
        setattr(ollama.Client, nombre, envuelta)

    def _anotar(self, r, modelo, segundos):
        ns = lambda k: (_campo(r, k) or 0) / NS          # noqa: E731
        entrada, salida = _campo(r, "prompt_eval_count") or 0, _campo(r, "eval_count") or 0
        t_lectura, t_gen = ns("prompt_eval_duration"), ns("eval_duration")
        lps = []
        for x in _campo(r, "logprobs") or []:
            v = _campo(x, "logprob")
            if isinstance(v, (int, float)) and math.isfinite(v):
                lps.append(v)
        media_lp = sum(lps) / len(lps) if lps else None
        self.llamadas.append({
            "etapa": self.etapa, "modelo": modelo or _campo(r, "model"),
            "tokens_entrada": entrada, "tokens_salida": salida,
            "carga_s": ns("load_duration"), "lectura_s": t_lectura, "generacion_s": t_gen,
            "total_s": ns("total_duration") or segundos,
            "tok_s_generacion": salida / t_gen if t_gen > 0 and salida else None,
            "tok_s_lectura": entrada / t_lectura if t_lectura > 0 and entrada else None,
            # hasta el primer token = cargar el modelo (si hizo falta) + leer el prompt
            "primer_token_s": ns("load_duration") + t_lectura,
            # perplejidad = exp(-promedio del log de la probabilidad de cada token): 1 = totalmente seguro
            "perplejidad": math.exp(-media_lp) if media_lp is not None else None,
            "prob_media_token": math.exp(media_lp) if media_lp is not None else None,
        })

    def __enter__(self):
        try:
            for n in ("chat", "generate"):
                self._envolver(n)
        except ImportError:
            pass
        return self

    def __exit__(self, *exc):
        try:
            import ollama
            for n, f in self._originales.items():
                setattr(ollama.Client, n, f)
        except ImportError:
            pass
        return False

    def resumen(self) -> dict:
        out = {}
        for etapa in dict.fromkeys(c["etapa"] for c in self.llamadas):
            cs = [c for c in self.llamadas if c["etapa"] == etapa]
            prom = lambda k: sum(c[k] for c in cs) / len(cs)          # noqa: E731
            gen = [c["tok_s_generacion"] for c in cs if c["tok_s_generacion"]]
            lec = [c["tok_s_lectura"] for c in cs if c["tok_s_lectura"]]
            # recarga = la llamada tuvo que volver a cargar el modelo en memoria (> 1 s de carga)
            recargas = sum(1 for c in cs[1:] if c["carga_s"] > 1)
            ppl = [c["perplejidad"] for c in cs if c.get("perplejidad")]
            prob = [c["prob_media_token"] for c in cs if c.get("prob_media_token")]
            total = sum(c["total_s"] for c in cs)
            out[etapa] = {
                "llamadas": len(cs), "modelos": sorted({str(c["modelo"]) for c in cs}),
                "tokens_entrada_media": prom("tokens_entrada"), "tokens_salida_media": prom("tokens_salida"),
                "tokens_totales": sum(c["tokens_entrada"] + c["tokens_salida"] for c in cs),
                "tok_s_generacion_p50": M.percentil(gen, 50), "tok_s_generacion_min": min(gen) if gen else None,
                "tok_s_lectura_p50": M.percentil(lec, 50),
                "carga_max_s": max(c["carga_s"] for c in cs), "recargas": recargas,
                "generacion_media_s": prom("generacion_s"), "lectura_media_s": prom("lectura_s"),
                "primer_token_p50_s": M.percentil([c["primer_token_s"] for c in cs], 50),
                "primer_token_p95_s": M.percentil([c["primer_token_s"] for c in cs], 95),
                # una solicitud a la vez, como en la guardia (Ollama atiende de a una: OLLAMA_NUM_PARALLEL=1)
                "solicitudes_por_minuto": 60 * len(cs) / total if total > 0 else None,
                "perplejidad_p50": M.percentil(ppl, 50), "perplejidad_max": max(ppl) if ppl else None,
                "prob_media_token": sum(prob) / len(prob) if prob else None,
                "llamadas_con_logprobs": len(ppl),
            }
        return out


# ================================================================= 2. GPU, CPU y RAM

CAMPOS_GPU = ["pstate", "utilization.gpu", "memory.used", "memory.total", "clocks.gr", "power.draw", "name"]


def leer_gpu():
    """Una muestra de cada GPU NVIDIA, o [] si no hay nvidia-smi."""
    if not shutil.which("nvidia-smi"):
        return []
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=" + ",".join(CAMPOS_GPU),
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
    except Exception:
        return []
    out = []
    for linea in r.stdout.strip().splitlines():
        v = [x.strip() for x in linea.split(",")]
        if len(v) < len(CAMPOS_GPU):
            continue
        out.append({"pstate": v[0], "uso": M.a_numero(v[1]), "vram_mb": M.a_numero(v[2]),
                    "vram_total_mb": M.a_numero(v[3]), "reloj_mhz": M.a_numero(v[4]),
                    "consumo_w": M.a_numero(v[5]), "nombre": ",".join(v[6:])})
    return out


class MonitorRecursos:
    def __init__(self, intervalo: float = 1.0):
        self.intervalo = intervalo
        self.muestras: list[dict] = []
        self._fin = threading.Event()
        self._hilo = None
        try:
            import psutil
            self._psutil = psutil
            psutil.cpu_percent(None)                     # la primera lectura siempre da 0
        except ImportError:
            self._psutil = None

    def _bucle(self):
        while not self._fin.is_set():
            m = {"t": time.time(), "gpus": leer_gpu()}
            if self._psutil:
                m["cpu"] = self._psutil.cpu_percent(None)
                vm = self._psutil.virtual_memory()
                m["ram_gb"] = vm.used / 2**30
                m["ram_total_gb"] = vm.total / 2**30
            self.muestras.append(m)
            self._fin.wait(self.intervalo)

    def __enter__(self):
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._hilo.start()
        return self

    def __exit__(self, *exc):
        self._fin.set()
        if self._hilo:
            self._hilo.join(timeout=5)
        return False

    def resumen(self) -> dict:
        ms = self.muestras
        out = {"muestras": len(ms), "psutil": bool(self._psutil)}
        cpu = [m["cpu"] for m in ms if "cpu" in m]
        ram = [m["ram_gb"] for m in ms if "ram_gb" in m]
        if cpu:
            out["cpu_media"], out["cpu_max"] = sum(cpu) / len(cpu), max(cpu)
        if ram:
            out["ram_max_gb"], out["ram_total_gb"] = max(ram), ms[-1].get("ram_total_gb")
        gpus = {}
        for m in ms:
            for i, g in enumerate(m["gpus"]):
                gpus.setdefault(i, []).append(g)
        out["gpus"] = []
        for i, gs in gpus.items():
            uso = [g["uso"] for g in gs if g["uso"] is not None]
            estados = {}
            for g in gs:
                estados[g["pstate"]] = estados.get(g["pstate"], 0) + 1
            activa = [g for g in gs if (g["uso"] or 0) >= 5]
            out["gpus"].append({
                "nombre": gs[0]["nombre"], "vram_total_mb": gs[0]["vram_total_mb"],
                "vram_max_mb": max((g["vram_mb"] or 0) for g in gs),
                "uso_media": sum(uso) / len(uso) if uso else None, "uso_max": max(uso) if uso else None,
                "reloj_max_mhz": max((g["reloj_mhz"] or 0) for g in gs),
                "consumo_max_w": max((g["consumo_w"] or 0) for g in gs),
                "estados": estados, "muestras_activa": len(activa),
            })
        return out


def alerta_gpu(recursos: dict, rendimiento: dict) -> str | None:
    """Detecta el caso del 26/10: la GPU tiene el modelo cargado pero no trabaja (P8, uso ~0 %)
    y la generación es lentísima. Devuelve un texto de aviso o None."""
    gen = [e["tok_s_generacion_p50"] for e in rendimiento.values() if e.get("tok_s_generacion_p50")]
    for g in recursos.get("gpus", []):
        if (g["vram_max_mb"] or 0) > 1000 and (g["uso_max"] or 0) < 10 and gen and min(gen) < 10:
            return (f"La GPU {g['nombre']} tiene el modelo en memoria pero casi no trabajó "
                    f"(uso máximo {g['uso_max']:.0f} %, estados {g['estados']}) y la generación fue de "
                    f"{min(gen):.1f} tokens/s. Revisar la librería CUDA de Ollama (OLLAMA_LLM_LIBRARY=cuda_v12) "
                    "y el modo de energía.")
    return None
