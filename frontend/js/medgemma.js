/* frontend/medgemma.js · Conecta el prototipo con MedGemma (Flask + Ollama).
 *
 * Se carga DESPUÉS de formulario.js y reemplaza las partes simuladas sin tocar ese archivo:
 *   - extracción: pisa los datos de ejemplo con lo que devolvió /api/analizar
 *   - sugerencia: medgemma() -> /api/sugerir  (las reglas de seguridad siguen fijando el piso)
 *   - chat:       preguntarIA() -> /api/consulta
 *   - indicador:  updOllama() -> /api/estado
 * Si el backend o Ollama no responden, vuelve solo a la simulación.
 */
(function () {
  'use strict';

  const ia = {
    disponible: false, modelo: null,
    sug: null, clave: null, claveFallida: null, cargando: false,
    ultimaExtraccion: null
  };

  async function post(ruta, cuerpo) {
    const r = await fetch(ruta, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(cuerpo)
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
    return j;
  }

  /* ---------- 1. Indicador de estado ---------- */
  function pintarEstado() {
    const b = document.getElementById('ollama');
    if (!b) return;
    b.innerHTML = ia.disponible
      ? '<span class="dot"></span>IA: ' + (ia.modelo || 'MedGemma')
      : '<span class="dot off"></span>IA: no disponible (simulado)';
    b.title = ia.disponible ? 'MedGemma conectado vía Ollama. Tocá para volver a verificar.'
                            : 'No responde Ollama. Tocá para volver a verificar.';
  }
  async function chequearEstado() {
    try {
      const j = await fetch('/api/estado', { credentials: 'same-origin' }).then(r => r.json());
      ia.disponible = !!j.ia;
      ia.modelo = j.modelo || null;
    } catch (e) {
      ia.disponible = false;
    }
    st.ollama = ia.disponible;
    pintarEstado();
  }
  window.updOllama = chequearEstado;   // el click del chip ahora re-verifica

  /* ---------- 2. Extracción: reemplazar TODOS los datos de ejemplo ---------- */
  const TEXTOS = {
    sexo: 'sexo', motivo_categoria: 'motivo_categoria', motivo_consulta: 'motivo_consulta',
    localizacion_dolor: 'dolor_localizacion', sintomas_asociados: 'sintomas_asociados',
    tiempo_evolucion_unidad: 'tiempo_evolucion_unidad'
  };
  const NUMEROS = {
    edad: 'edad', tiempo_evolucion_valor: 'tiempo_evolucion_valor',
    tas: 'ta_sistolica', tad: 'ta_diastolica', pam: 'pam',
    frec_cardiaca: 'frecuencia_cardiaca', frec_respiratoria: 'frecuencia_respiratoria',
    saturacion: 'saturacion_o2', temperatura: 'temperatura', glasgow: 'glasgow',
    dolor: 'dolor_intensidad'
  };
  const ANTECEDENTES = ['ant_diabetes', 'ant_cardio', 'ant_resp', 'ant_anticoag',
                        'ant_inmuno', 'ant_embarazo', 'ant_medicacion'];

  function aplicarExtraccion(x) {
    const r = st.rev;
    Object.entries(TEXTOS).forEach(([o, d]) => { r[d] = x[o] == null ? '' : String(x[o]); });
    Object.entries(NUMEROS).forEach(([o, d]) => {
      r[d] = x[o] == null ? '' : String(x[o]);
      if (o !== d) delete r[o];          // limpia las claves duplicadas que copia formulario.js
    });
    ANTECEDENTES.forEach(k => { r[k] = !!x[k]; });
    r.dolor_caracteristicas = r.dolor_caracteristicas || '';
    // lo que extrajo MedGemma queda como valor de origen "IA" (badges, correcciones y "restaurar")
    FI.forEach(f => {
      if (f.src === 'med' || f.t === 'calc') return;
      const v = r[f.k];
      if (f.t === 'chk') f.ia = !!v; else f.ia = (v === '' || v == null) ? null : v;
      if ('hce' in f) f.hce = null;
    });
    ia.sug = null; ia.clave = null; ia.claveFallida = null;
  }

  const goOriginal = window.go;
  window.go = function (s) {
    if (s === 'revision' && st.extraccion && st.extraccion !== ia.ultimaExtraccion
        && st.extraccion._modelo) {
      ia.ultimaExtraccion = st.extraccion;
      aplicarExtraccion(st.extraccion);
    }
    return goOriginal.apply(this, arguments);
  };

  /* ---------- 3. Sugerencia de color ---------- */
  const medgemmaSimulada = window.medgemma;

  async function pedirSugerencia(clave) {
    ia.cargando = true;
    try {
      const caso = document.getElementById('caso');
      const j = await post('/api/sugerir', { datos: st.rev, relato: caso ? caso.value : '' });
      ia.sug = {
        lv: Number.isInteger(j.nivel) ? j.nivel : 2,
        why: (j.motivos && j.motivos.length) ? j.motivos : ['MedGemma no detalló motivos'],
        fuentes: j.fuentes || [],
        color: j.color
      };
      ia.clave = clave;
    } catch (e) {
      console.warn('[MedGemma] sugerencia falló, uso simulación:', e.message);
      ia.claveFallida = clave;
    } finally {
      ia.cargando = false;
      if (st.screen === 'resumen') window.renderCard();
    }
  }

  window.medgemma = function () {
    const clave = JSON.stringify(st.rev);
    if (ia.sug && ia.clave === clave) { ia.fuente = 'ia'; return ia.sug; }
    const sim = medgemmaSimulada();
    if (!ia.disponible || ia.claveFallida === clave) {
      ia.fuente = 'sim';
      return { lv: sim.lv, why: ['(simulado: MedGemma no disponible)'].concat(sim.why) };
    }
    if (!ia.cargando) pedirSugerencia(clave);
    ia.fuente = 'cargando';
    return { lv: sim.lv, why: ['(provisorio: consultando a MedGemma…)'].concat(sim.why) };
  };

  /* Etiqueta cada motivo por su ORIGEN real: RELATO (lo dijo el paciente), MEDIDO (lo cargó enfermería),
     IA (criterio propio del modelo) o SIM (simulación). REGLA y GUÍA las pone formulario.js. */
  const estilo = document.createElement('style');
  estilo.textContent = '.src.rel{background:var(--panel-2);color:var(--ink);border:1px solid var(--line)}'
    + '.src.med{background:transparent;color:var(--ink);border:1px solid var(--line)}'
    + '.src.sim{background:var(--panel-2);color:var(--muted);border:1px dashed var(--line)}';
  document.head.appendChild(estilo);
  const ETIQ = { relato: ['rel', 'RELATO'], medido: ['r', 'REGLA'], ia: ['ia', 'IA'], sim: ['sim', 'SIM'] };

  function etiquetarMotivos() {
    const ul = document.getElementById('tcWhy');
    if (!ul) return;
    const items = [...ul.querySelectorAll('li')].filter(li => li.querySelector('.src.ia'));
    const deIA = ia.fuente === 'ia' && ia.sug;
    items.forEach((li, i) => {
      const f = deIA ? (ia.sug.fuentes[i] || 'ia') : 'sim';
      const [cls, txt] = ETIQ[f] || ETIQ.ia;
      const tag = li.querySelector('.src');
      tag.className = 'src ' + cls;
      tag.textContent = txt;
      tag.title = { rel: 'Lo dijo el paciente en el relato', r: 'Criterio Manchester sobre los signos medidos',
                    ia: 'Criterio propio de MedGemma', sim: 'Simulación: reglas de ejemplo en el navegador' }[cls];
    });
    if (deIA && ia.sug.color) {      // lo que sí aporta la IA: el juicio sobre el color
      const li = document.createElement('li');
      li.innerHTML = '<span class="src ia" title="Criterio propio de MedGemma">IA</span><span>MedGemma estima '
        + ia.sug.color + ' con estos datos</span>';
      ul.insertBefore(li, items[0] || null);
    }
  }

  /* Textos de la tarjeta según de dónde salió el color */
  const renderCardOriginal = window.renderCard;
  window.renderCard = function () {
    const out = renderCardOriginal.apply(this, arguments);
    const ceja = document.querySelector('#triageCard .eyebrow');
    const origen = document.getElementById('tcOrigin');
    const n = ceja && ceja.querySelector('.n') ? ceja.querySelector('.n').outerHTML : '';
    const txt = { ia: 'Prioridad sugerida · MedGemma', cargando: 'Consultando a MedGemma… · provisoria',
                  sim: 'Prioridad de ejemplo · simulada' }[ia.fuente] || 'Prioridad de ejemplo · simulada';
    if (ceja) ceja.innerHTML = txt + ' ' + n;
    etiquetarMotivos();
    if (origen && ia.fuente === 'ia') {
      origen.innerHTML = origen.innerHTML
        .replace('Simulación con reglas de ejemplo.', 'Sugerencia de MedGemma + reglas de seguridad.')
        .replace('La simulación sugería', 'MedGemma sugería');
    }
    return out;
  };

  /* ---------- 4. Chat ---------- */
  const preguntarSimulada = window.preguntarIA;
  window.preguntarIA = async function (q) {
    if (!ia.disponible) return preguntarSimulada(q);
    try {
      const color = (typeof LEVELS !== 'undefined' && typeof SUG !== 'undefined') ? LEVELS[SUG][0] : '';
      const j = await post('/api/consulta', { pregunta: q, episodio: st.ep, datos: st.rev, sugerencia: color });
      const aviso = (typeof AVISO !== 'undefined') ? AVISO : '';
      return j.respuesta + aviso;
    } catch (e) {
      console.warn('[MedGemma] chat falló, uso simulación:', e.message);
      return preguntarSimulada(q);
    }
  };

  chequearEstado();
})();
