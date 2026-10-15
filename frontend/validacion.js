/* frontend/validacion.js · Controles técnicos del formulario (refleja C04 de Darío)
 *
 * Fuente de verdad: backend/src/validacion.py + backend/datos/esquemas/DatosTriage.json
 * Detalle de cada control: backend/docs/controles_validacion.md
 *
 * El frontend avisa ANTES de enviar; el backend vuelve a validar y es el control final.
 * Ningún control asigna gravedad clínica: solo tipos, rangos, opciones, coherencia y privacidad.
 *
 * Uso:
 *   const r = TriageDatos.validate(datos);              // todas las etapas
 *   const r = TriageDatos.validate(datos, 'ingreso');   // faltantes solo de esa etapa ('ingreso' | 'medicion')
 *   r.valid    true/false (los errores bloquean)
 *   r.errors   { campo: 'mensaje' }
 *   r.missing  obligatorios vacíos (NO bloquean: se informan)
 *   r.data     datos limpios con tipos correctos ('' -> null, '37,8' -> 37.8, 'sí/no' -> booleanos)
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.TriageDatos = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // 1–3 · Números: tipo, entero y rango de plausibilidad (no son umbrales clínicos)
  const numeric = {
    edad:                    { label: 'Edad',                    min: 0,  max: 120,   integer: true,  unit: 'años' },
    tiempo_evolucion_valor:  { label: 'Desde hace (valor)',      min: 0,  max: 10000, integer: false, unit: '' },
    ta_sistolica:            { label: 'TA sistólica',            min: 50, max: 260,   integer: true,  unit: 'mmHg' },
    ta_diastolica:           { label: 'TA diastólica',           min: 20, max: 160,   integer: true,  unit: 'mmHg' },
    frecuencia_cardiaca:     { label: 'Frecuencia cardíaca',     min: 20, max: 250,   integer: true,  unit: 'lpm' },
    frecuencia_respiratoria: { label: 'Frecuencia respiratoria', min: 4,  max: 60,    integer: true,  unit: 'rpm' },
    saturacion_o2:           { label: 'SpO₂',                    min: 50, max: 100,   integer: true,  unit: '%' },
    temperatura:             { label: 'Temperatura',             min: 30, max: 43,    integer: false, unit: '°C' },
    glucemia:                { label: 'Glucemia capilar',        min: 20, max: 800,   integer: true,  unit: 'mg/dL' },
    glasgow:                 { label: 'Glasgow',                 min: 3,  max: 15,    integer: true,  unit: 'puntos' },
    dolor_intensidad:        { label: 'Escala de dolor',         min: 0,  max: 10,    integer: true,  unit: '0–10' }
  };

  // 4 · Opciones cerradas
  const options = {
    sexo: ['Femenino', 'Masculino', 'No informado'],
    motivo_categoria: ['Dolor torácico', 'Dolor abdominal', 'Disnea', 'Trauma', 'Fiebre', 'Cefalea', 'Síntoma neurológico', 'Otro'],
    tiempo_evolucion_unidad: ['minutos', 'horas', 'días'],
    estado_conciencia: ['Alerta', 'Responde a la voz', 'Responde al dolor', 'No responde']
  };

  // Banderas rojas y antecedentes: sí/no (por defecto, no)
  const booleans = {
    br_sangrado: 'Sangrado evidente', br_convulsion: 'Convulsión activa',
    br_disnea: 'Dificultad para respirar', br_trauma: 'Mecanismo de trauma',
    ant_diabetes: 'Diabetes', ant_cardio: 'Cardiovascular', ant_resp: 'Respiratorio',
    ant_anticoag: 'Anticoagulación', ant_inmuno: 'Inmunosupresión',
    ant_embarazo: 'Embarazo', ant_medicacion: 'Medicación crítica'
  };

  // 6 · Textos libres: largo máximo y control de privacidad
  const texts = {
    motivo_consulta:       { label: 'Motivo de consulta',       max: 500 },
    dolor_localizacion:    { label: 'Localización del dolor',   max: 100 },
    sintomas_asociados:    { label: 'Síntomas asociados',       max: 300 },
    dolor_caracteristicas: { label: 'Características del dolor', max: 200 },
    alergias:              { label: 'Alergias',                 max: 200 },
    antecedentes_otros:    { label: 'Otros antecedentes',       max: 200 },
    aspecto_general:       { label: 'Aspecto general',          max: 200 }
  };

  // 8 · Códigos (no identifican a la persona). Ej.: PAC-DEMO-001, EPI-004818
  const codes = { codigo_paciente: 'Código de paciente', codigo_episodio: 'Código de episodio' };
  const CODE_RE = /^[A-Z]{2,4}-[A-Z0-9-]{3,20}$/;

  // Mismos patrones que PATRONES_PERSONALES en backend/src/esquemas.py (Ley 25.326)
  const PRIVACY = {
    'DNI': /\bdni\b|\bdocumento\b|\b\d{1,2}\.\d{3}\.\d{3}\b|\b\d{7,}\b/,
    'email': /[\w.+-]+@[\w.-]+\.[a-z]{2,}/,
    'teléfono': /\btel[eé]fono\b|\bcel(ular)?\b|\b\d{2,4}[- ]\d{6,8}\b/,
    'nombre': /\bme llamo\b|\bse llama\b|\bnombre\b|\bapellido\b/,
    'domicilio': /\bdomicilio\b|\bvive en\b|\bcalle\b|\bbarrio\b/
  };

  // 9 · Obligatorios por etapa: si faltan NO se bloquea, se informan
  const required = {
    ingreso: ['edad', 'sexo', 'motivo_categoria', 'tiempo_evolucion_valor', 'tiempo_evolucion_unidad', 'motivo_consulta', 'dolor_localizacion'],
    medicion: ['ta_sistolica', 'ta_diastolica', 'frecuencia_cardiaca', 'frecuencia_respiratoria', 'saturacion_o2', 'temperatura', 'dolor_intensidad']
  };

  const labels = Object.assign({},
    Object.fromEntries(Object.entries(numeric).map(([k, s]) => [k, s.label])),
    Object.fromEntries(Object.entries(texts).map(([k, s]) => [k, s.label])),
    booleans, codes,
    { sexo: 'Sexo', motivo_categoria: 'Categoría del motivo', tiempo_evolucion_unidad: 'Desde hace (unidad)', estado_conciencia: 'Estado de conciencia (AVDN)' });

  // Nombres viejos -> V2 (igual que traducir_alias() del backend), para datos guardados con el formulario anterior
  const ALIAS = { tas: 'ta_sistolica', tad: 'ta_diastolica', frec_cardiaca: 'frecuencia_cardiaca', fc: 'frecuencia_cardiaca',
    frec_respiratoria: 'frecuencia_respiratoria', fr: 'frecuencia_respiratoria', saturacion: 'saturacion_o2', spo2: 'saturacion_o2',
    dolor: 'dolor_intensidad', localizacion_dolor: 'dolor_localizacion' };
  const ALIAS_SEXO = { M: 'Masculino', F: 'Femenino', X: 'No informado' };
  const ALIAS_LISTAS = {
    banderas_rojas: { sangrado: 'br_sangrado', convulsion: 'br_convulsion', dificultad_respiratoria: 'br_disnea', trauma: 'br_trauma' },
    antecedentes: { diabetes: 'ant_diabetes', cardiaco: 'ant_cardio', medicacion_critica: 'ant_medicacion' } };
  function traducirAlias(raw) {
    const d = {};
    for (const [k, v] of Object.entries(raw || {})) if (k !== 'pam') d[ALIAS[k] || k] = v;
    for (const [lista, mapa] of Object.entries(ALIAS_LISTAS)) {
      const items = d[lista]; delete d[lista];
      if (Array.isArray(items)) for (const it of items) if (mapa[it]) d[mapa[it]] = true;
    }
    if (ALIAS_SEXO[d.sexo]) d.sexo = ALIAS_SEXO[d.sexo];
    return d;
  }

  // 10 · Vacío ≠ cero: '' o null = faltante; 0 es un valor real
  const empty = v => v === undefined || v === null || (typeof v === 'string' && v.trim() === '');

  function toBool(v) {
    if (v === true || v === false) return v;
    const s = String(v).trim().toLowerCase();
    if (['true', 'sí', 'si', '1', 'on'].includes(s)) return true;
    if (['false', 'no', '0', 'off', ''].includes(s)) return false;
    return null;
  }

  function privacyIssue(text) {
    const t = text.toLowerCase();
    for (const [tipo, re] of Object.entries(PRIVACY)) if (re.test(t)) return tipo;
    return null;
  }

  function validate(raw, etapa) {
    if (etapa !== undefined && etapa !== null && !required[etapa])
      throw new Error("etapa debe ser 'ingreso' o 'medicion'");
    raw = traducirAlias(raw);
    const data = {}, errors = {};

    for (const [k, s] of Object.entries(numeric)) {
      const v = raw[k];
      if (empty(v)) { data[k] = null; continue; }
      const txt = String(v).trim();
      if (!/^-?\d+(?:[.,]\d+)?$/.test(txt)) { data[k] = null; errors[k] = 'Ingresá solo un número, sin unidades ni símbolos.'; continue; }
      const n = Number(txt.replace(',', '.'));
      data[k] = n;
      if (s.integer && !Number.isInteger(n)) errors[k] = 'Ingresá un número entero.';
      else if (n < s.min || n > s.max) errors[k] = 'Rango del diccionario: ' + s.min + ' a ' + s.max + (s.unit ? ' ' + s.unit : '') + '. Revisá el dato; no lo ajustes solo para que pase.';
    }

    for (const [k, list] of Object.entries(options)) {
      const v = raw[k];
      data[k] = empty(v) ? null : String(v).trim();
      if (data[k] !== null && !list.includes(data[k])) errors[k] = 'Elegí una opción de la lista.';
    }

    for (const k of Object.keys(booleans)) {
      const b = empty(raw[k]) ? false : toBool(raw[k]);
      data[k] = b === null ? false : b;
      if (b === null) errors[k] = 'Marcá sí o no.';
    }

    for (const [k, s] of Object.entries(texts)) {
      const v = raw[k];
      data[k] = empty(v) ? null : String(v).trim();
      if (data[k] === null) continue;
      if (data[k].length > s.max) { errors[k] = 'Máximo ' + s.max + ' caracteres.'; continue; }
      const tipo = privacyIssue(data[k]);
      if (tipo) errors[k] = 'Posible dato personal (' + tipo + '). Quitalo: solo casos ficticios, sin nombres, documentos ni datos de contacto.';
    }

    for (const k of Object.keys(codes)) {
      const v = raw[k];
      data[k] = empty(v) ? null : String(v).trim().toUpperCase();
      if (data[k] !== null && !CODE_RE.test(data[k])) errors[k] = 'Formato: letras, guion y código (ej. PAC-DEMO-001).';
    }

    // 5 · Coherencia de la tensión arterial
    const s = data.ta_sistolica, d = data.ta_diastolica;
    if (!errors.ta_sistolica && !errors.ta_diastolica && s !== null && d !== null && d >= s)
      errors.ta_diastolica = 'La diastólica debe ser menor que la sistólica. Revisá ambas mediciones.';

    // PAM calculada (solo informativa, como en el backend)
    data.pam = (s !== null && d !== null && !errors.ta_sistolica && !errors.ta_diastolica)
      ? Math.round((s + 2 * d) / 3) : null;

    const etapas = etapa ? [etapa] : Object.keys(required);
    const missing = etapas.flatMap(e => required[e]).filter(k => data[k] === null);

    return { data, errors, missing, valid: Object.keys(errors).length === 0 };
  }

  return { numeric, options, booleans, texts, codes, required, labels, validate };
});
