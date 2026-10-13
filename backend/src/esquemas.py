"""
Esquemas Pydantic — FUENTE ÚNICA de nombres, tipos, unidades y rangos (Diccionario V2).
Los nombres son los del maquetado v33 (frontend). Los nombres viejos se aceptan como alias.

  Identificacion        -> edad, sexo (vienen de la HCE)
  ExtraccionIA          -> lo que MedGemma extrae del relato (Tomás)
  Mediciones            -> signos vitales y escalas (los toma enfermería)
  DatosTriage           -> Identificacion + ExtraccionIA + Mediciones (lo que recibe la API)
  SalidaModelo          -> sugerencia de color que devuelve MedGemma
  ResultadoHospital     -> SalidaModelo + campos que agrega Python
  DecisionProfesional   -> aceptar / modificar / descartar (revisión humana)

Regenerar JSON Schema + tabla de control:   python -m src.esquemas
"""
import json
import re
from pathlib import Path
from typing import Literal, Optional, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

Color = Literal["Rojo", "Naranja", "Amarillo", "Verde", "Azul"]
Sexo = Literal["Femenino", "Masculino", "No informado"]
Categoria = Literal["Dolor torácico", "Dolor abdominal", "Disnea", "Trauma", "Fiebre",
                    "Cefalea", "Síntoma neurológico", "Otro"]
UnidadTiempo = Literal["minutos", "horas", "días"]
Conciencia = Literal["Alerta", "Responde a la voz", "Responde al dolor", "No responde"]

# ---------- Alias: nombre viejo -> nombre V2 ----------
ALIAS = {
    "tas": "ta_sistolica", "tad": "ta_diastolica",
    "frec_cardiaca": "frecuencia_cardiaca", "fc": "frecuencia_cardiaca",
    "frec_respiratoria": "frecuencia_respiratoria", "fr": "frecuencia_respiratoria",
    "saturacion": "saturacion_o2", "spo2": "saturacion_o2",
    "dolor": "dolor_intensidad", "localizacion_dolor": "dolor_localizacion",
}
ALIAS_SEXO = {"M": "Masculino", "F": "Femenino", "X": "No informado"}
ALIAS_BANDERAS = {"sangrado": "br_sangrado", "convulsion": "br_convulsion",
                  "dificultad_respiratoria": "br_disnea", "trauma": "br_trauma"}
ALIAS_ANTECEDENTES = {"diabetes": "ant_diabetes", "cardiaco": "ant_cardio",
                      "medicacion_critica": "ant_medicacion"}

# Datos personales prohibidos en textos libres (Ley 25.326)
PATRONES_PERSONALES = {
    "DNI": r"\bdni\b|\b\d{1,2}\.\d{3}\.\d{3}\b|\b\d{7,8}\b",
    "teléfono": r"\btel[eé]fono\b|\bcel(ular)?\b|\b\d{2,4}[- ]\d{6,8}\b",
    "nombre": r"\bme llamo\b|\bse llama\b|\bnombre\b|\bapellido\b",
    "domicilio": r"\bdomicilio\b|\bvive en\b|\bcalle\b|\bbarrio\b",
}

# Obligatoriedad por etapa: si faltan NO se rechaza; se informan como missing_data
OBLIGATORIOS = {
    "ingreso": ["edad", "sexo", "motivo_categoria", "tiempo_evolucion_valor",
                "tiempo_evolucion_unidad", "motivo_consulta", "dolor_localizacion"],
    "medicion": ["ta_sistolica", "ta_diastolica", "frecuencia_cardiaca",
                 "frecuencia_respiratoria", "saturacion_o2", "temperatura", "dolor_intensidad"],
}


def _f(default=None, *, desc, origen, unidad=None, **kw):
    """Field con metadatos del diccionario (unidad y origen)."""
    extra = {"origen": origen}
    if unidad:
        extra["unidad"] = unidad
    return Field(default, description=desc, json_schema_extra=extra, **kw)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def limpiar(cls, v):
        if v == "":
            return None                                   # campo vacío = dato faltante (≠ 0)
        if isinstance(v, str) and re.fullmatch(r"-?\d+,\d+", v.strip()):
            return v.strip().replace(",", ".")            # "37,8" -> "37.8"
        return v


class Identificacion(_Base):
    edad: Optional[int] = _f(desc="Edad", origen="HCE", unidad="años", ge=0, le=120)
    sexo: Optional[Sexo] = _f(desc="Sexo", origen="HCE")


class ExtraccionIA(_Base):
    """Campos que MedGemma extrae del relato. Todo opcional: lo que no se dice queda null."""
    motivo_categoria: Optional[Categoria] = _f(desc="Categoría del motivo", origen="IA")
    tiempo_evolucion_valor: Optional[float] = _f(desc="Desde hace (valor)", origen="IA", ge=0, le=10000)
    tiempo_evolucion_unidad: Optional[UnidadTiempo] = _f(desc="Desde hace (unidad)", origen="IA")
    motivo_consulta: Optional[str] = _f(desc="Motivo (resumen del relato)", origen="IA", max_length=500)
    dolor_localizacion: Optional[str] = _f(desc="Dónde le duele", origen="IA", max_length=100)
    sintomas_asociados: Optional[str] = _f(desc="Síntomas que refiere", origen="IA", max_length=300)
    dolor_caracteristicas: Optional[str] = _f(desc="Cómo es el dolor", origen="IA", max_length=200)
    br_sangrado: bool = _f(False, desc="Sangrado evidente", origen="IA")
    br_convulsion: bool = _f(False, desc="Convulsión activa", origen="IA")
    br_disnea: bool = _f(False, desc="Dificultad para respirar", origen="IA")
    br_trauma: bool = _f(False, desc="Mecanismo de trauma", origen="IA")
    ant_diabetes: bool = _f(False, desc="Diabetes", origen="IA")
    ant_cardio: bool = _f(False, desc="Cardiovascular", origen="IA")
    ant_resp: bool = _f(False, desc="Respiratorio", origen="IA")
    ant_anticoag: bool = _f(False, desc="Anticoagulación", origen="IA")
    ant_inmuno: bool = _f(False, desc="Inmunosupresión", origen="IA")
    ant_embarazo: bool = _f(False, desc="Embarazo", origen="IA")
    ant_medicacion: bool = _f(False, desc="Medicación crítica", origen="IA")
    alergias: Optional[str] = _f(desc="Alergias", origen="IA", max_length=200)
    antecedentes_otros: Optional[str] = _f(desc="Otros antecedentes", origen="IA", max_length=200)

    @field_validator("motivo_consulta", "dolor_localizacion", "sintomas_asociados",
                     "dolor_caracteristicas", "alergias", "antecedentes_otros")
    @classmethod
    def sin_datos_personales(cls, v):
        if v:
            for tipo, patron in PATRONES_PERSONALES.items():
                if re.search(patron, v.lower()):
                    raise ValueError(f"posible dato personal ({tipo}); quitarlo")
        return v


class Mediciones(_Base):
    """Rangos de PLAUSIBILIDAD (cortan errores de tipeo), no umbrales clínicos."""
    ta_sistolica: Optional[int] = _f(desc="TA sistólica", origen="medición", unidad="mmHg", ge=50, le=260)
    ta_diastolica: Optional[int] = _f(desc="TA diastólica", origen="medición", unidad="mmHg", ge=20, le=160)
    frecuencia_cardiaca: Optional[int] = _f(desc="Frec. cardíaca", origen="medición", unidad="lpm", ge=20, le=250)
    frecuencia_respiratoria: Optional[int] = _f(desc="Frec. respiratoria", origen="medición", unidad="rpm", ge=4, le=60)
    saturacion_o2: Optional[int] = _f(desc="SpO₂", origen="medición", unidad="%", ge=50, le=100)
    temperatura: Optional[float] = _f(desc="Temperatura", origen="medición", unidad="°C", ge=30, le=43)
    glucemia: Optional[int] = _f(desc="Glucemia capilar", origen="medición", unidad="mg/dL", ge=20, le=800)
    estado_conciencia: Optional[Conciencia] = _f(desc="Estado de conciencia (AVDN)", origen="medición")
    glasgow: Optional[int] = _f(desc="Glasgow", origen="medición", unidad="3–15", ge=3, le=15)
    dolor_intensidad: Optional[int] = _f(desc="Escala de dolor", origen="medición", unidad="0–10", ge=0, le=10)
    aspecto_general: Optional[str] = _f(desc="Aspecto general", origen="medición", max_length=200)

    @model_validator(mode="after")
    def tension_coherente(self):
        s, d = self.ta_sistolica, self.ta_diastolica
        if s is not None and d is not None and d >= s:
            raise ValueError(f"diastólica ({d}) mayor o igual a sistólica ({s})")
        return self

    @computed_field(description="PAM calculada = (sistólica + 2·diastólica) / 3, mmHg")
    @property
    def pam(self) -> Optional[int]:
        if self.ta_sistolica is None or self.ta_diastolica is None:
            return None
        return round((self.ta_sistolica + 2 * self.ta_diastolica) / 3)


class DatosTriage(Mediciones, ExtraccionIA, Identificacion):
    """Todo lo que recibe la API para pedir una sugerencia."""
    codigo_paciente: Optional[str] = _f(desc="Código interno del paciente (no identifica a la persona)",
                                        origen="sistema", pattern=r"^[A-Z]{2,4}-[A-Z0-9-]{3,20}$")
    codigo_episodio: Optional[str] = _f(desc="Código de una atención concreta",
                                        origen="sistema", pattern=r"^[A-Z]{2,4}-[A-Z0-9-]{3,20}$")

    @model_validator(mode="before")
    @classmethod
    def traducir_alias(cls, datos):
        """Acepta los nombres viejos (tas, saturacion, banderas_rojas[...], sexo 'M'...)."""
        if not isinstance(datos, dict):
            return datos
        d = {ALIAS.get(k, k): v for k, v in datos.items() if k != "pam"}   # pam se calcula
        for lista, mapa in (("banderas_rojas", ALIAS_BANDERAS), ("antecedentes", ALIAS_ANTECEDENTES)):
            for item in d.pop(lista, None) or []:
                d[mapa.get(item, f"{lista}:{item}")] = True        # desconocido -> error 'campo no permitido'
        if d.get("sexo") in ALIAS_SEXO:
            d["sexo"] = ALIAS_SEXO[d["sexo"]]
        return d

    def faltantes(self, etapa: Optional[str] = None) -> list[str]:
        etapas = [etapa] if etapa else list(OBLIGATORIOS)
        return [c for e in etapas for c in OBLIGATORIOS[e] if getattr(self, c) is None]


# ---------- Salidas ----------
class SalidaModelo(BaseModel):
    """Lo que MedGemma debe devolver. Se pasa a Ollama como `format` (salida estructurada)."""
    model_config = ConfigDict(extra="ignore")

    color: Color
    confidence: float = Field(ge=0, le=1)
    red_flags: list[str] = Field(description="signos o síntomas de alarma presentes, nunca enfermedades")
    possible_discriminators: list[str] = Field(description="discriminadores de la guía que se cumplen")
    rationale: str = Field(min_length=10, description="justificación breve citando valores del paciente")


class ResultadoHospital(BaseModel):
    """Formato final del hospital. color=None significa 'Información insuficiente'."""
    color: Optional[Color]
    confidence: float = Field(ge=0, le=1)
    red_flags: list[str]
    possible_discriminators: list[str]
    missing_data: list[str]                       # lo calcula Python, no el modelo
    rationale: str
    human_validation_required: Literal[True] = True


class DecisionProfesional(BaseModel):
    codigo_episodio: str
    id_profesional: str = Field(min_length=1)
    decision: Literal["aceptar", "modificar", "descartar"]
    color_final: Optional[Color] = None
    motivo_discrepancia: Optional[str] = None

    @model_validator(mode="after")
    def motivo_si_no_acepta(self):
        if self.decision != "aceptar" and not (self.motivo_discrepancia or "").strip():
            raise ValueError("falta el motivo de la discrepancia")
        if self.decision != "descartar" and self.color_final is None:
            raise ValueError("falta el color final")
        return self


def errores_en_espanol(e) -> list[str]:
    """Convierte los errores de Pydantic (en inglés) a mensajes cortos para el formulario."""
    salida = []
    for err in e.errors():
        campo = ".".join(str(x) for x in err["loc"]) or "datos"
        valor, tipo, ctx = err.get("input"), err["type"], err.get("ctx", {})
        if tipo in ("greater_than_equal", "less_than_equal"):
            salida.append(f"{campo}: {valor} fuera de rango")
        elif tipo in ("int_parsing", "float_parsing", "int_from_float", "int_type", "float_type", "bool_parsing"):
            salida.append(f"{campo}: '{valor}' no es un valor válido")
        elif tipo == "literal_error":
            opciones = str(ctx.get("expected")).replace(" or ", ", ")
            salida.append(f"{campo}: '{valor}' no es válido (opciones: {opciones})")
        elif tipo == "extra_forbidden":
            salida.append(f"{campo}: campo no permitido")
        elif tipo == "missing":
            salida.append(f"{campo}: falta")
        elif tipo == "string_too_long":
            salida.append(f"{campo}: texto demasiado largo")
        elif tipo == "string_pattern_mismatch":
            salida.append(f"{campo}: formato inválido")
        elif tipo == "value_error":
            salida.append(f"{campo}: {ctx.get('error', err['msg'])}".replace("datos: ", ""))
        else:
            salida.append(f"{campo}: {err['msg']}")
    return salida


# ---------- Documentación generada desde el esquema ----------
def _tipo(info) -> str:
    a = info.annotation
    args = [x for x in get_args(a) if x is not type(None)]
    if type(None) in get_args(a):
        a = args[0]
    if get_origin(a) is Literal:
        return "opción: " + " / ".join(get_args(a))
    return {int: "entero", float: "decimal", str: "texto", bool: "sí/no"}.get(a, str(a))


def diccionario_markdown() -> str:
    oblig = {c: e for e, campos in OBLIGATORIOS.items() for c in campos}
    inv = {}
    for viejo, nuevo in {**ALIAS, **{f"banderas_rojas[{k}]": v for k, v in ALIAS_BANDERAS.items()},
                         **{f"antecedentes[{k}]": v for k, v in ALIAS_ANTECEDENTES.items()}}.items():
        inv.setdefault(nuevo, []).append(viejo)
    filas = []
    for nombre, info in DatosTriage.model_fields.items():
        extra = info.json_schema_extra or {}
        rango = [str(m.ge) for m in info.metadata if hasattr(m, "ge")] + \
                [str(m.le) for m in info.metadata if hasattr(m, "le")]
        filas.append(f"| `{nombre}` | {info.description} | {_tipo(info)} | {extra.get('unidad', '')} | "
                     f"{'–'.join(rango)} | {extra.get('origen', '')} | {oblig.get(nombre, 'no')} | "
                     f"{', '.join(f'`{a}`' for a in inv.get(nombre, []))} |")
    filas.append("| `pam` | PAM calculada (sistólica + 2·diastólica) / 3 | entero | mmHg |  | "
                 "calculado | no |  |")
    return "\n".join([
        "# Diccionario de datos V2 — Triage asistido HRRG",
        "",
        "Tabla de control generada desde `src/esquemas.py`. El documento del equipo es `diccionario_datos_v2.md`.",
        "",
        "- Nombres = maquetado v33. Un mismo campo se llama igual en frontend, IA y API.",
        "- Campo vacío (`\"\"` o `null`) = **faltante**. `0` es un valor real y se valida contra su rango.",
        "- Decimales con coma o punto (`37,8` = `37.8`).",
        "- Obligatorio por etapa: si falta no bloquea; se informa en `missing_data`.",
        "- Rangos de plausibilidad (errores de tipeo), **no** umbrales clínicos.",
        "",
        "| Campo | Descripción | Tipo | Unidad | Rango | Origen | Obligatorio (etapa) | Alias aceptados |",
        "|---|---|---|---|---|---|---|---|",
        *filas,
        "",
        "## Controles técnicos (backend `src/validacion.py`; reflejar en `frontend/validacion.js`)",
        "",
        "1. Tipo y rango de cada campo numérico según la tabla.",
        "2. Opciones cerradas: solo los valores listados.",
        "3. TA diastólica menor que sistólica.",
        "4. Sin datos personales en textos libres (DNI, teléfono, nombre, domicilio) — Ley 25.326.",
        "5. Campos desconocidos se rechazan.",
        "6. Faltantes por etapa (`ingreso`, `medicion`) se listan, no bloquean.",
        "7. `codigo_paciente` y `codigo_episodio` con formato `XXX-XXXX` (ej.: PAC-DEMO-001, EPI-DEMO-001).",
        "",
    ])


if __name__ == "__main__":
    raiz = Path(__file__).resolve().parent.parent
    carpeta = raiz / "datos" / "esquemas"
    carpeta.mkdir(parents=True, exist_ok=True)
    for modelo in (DatosTriage, ExtraccionIA, Mediciones, SalidaModelo, ResultadoHospital, DecisionProfesional):
        (carpeta / f"{modelo.__name__}.json").write_text(
            json.dumps(modelo.model_json_schema(mode="serialization"), indent=2, ensure_ascii=False),
            encoding="utf-8")
    (raiz / "docs").mkdir(exist_ok=True)
    (raiz / "docs" / "diccionario_tabla_generada.md").write_text(diccionario_markdown(), encoding="utf-8")
    print("Generados: datos/esquemas/*.json y docs/diccionario_tabla_generada.md "
          "(control; el documento del equipo es docs/diccionario_datos_v2.md)")
