/* frontend/medgemma.js · Conecta el prototipo con MedGemma (Flask + Ollama).
 *
 * Se carga DESPUÉS de formulario.js y reemplaza las partes simuladas sin tocar ese archivo:
 *   - extracción: pisa los datos de ejemplo con lo que devolvió /api/analizar
 *   - sugerencia: medgemma() -> /api/sugerir  (las reglas de seguridad siguen fijando el piso)
 *   - chat:       preguntarIA() -> /api/consulta
 *   - indicador:  updOllama() -> /api/estado
 *   - modo sin IA: el chip de arriba prende/apaga la IA; si Ollama se cae, pasa solo a modo sin IA
 */
(function () {
  'use strict';

  /* Preferencia "IA apagada" del usuario (sobrevive a recargar la página) */
  const CLAVE_APAGADA = 'hrrg_ia_apagada';
  const leerApagada = () => { try { return localStorage.getItem(CLAVE_APAGADA) === '1'; } catch (e) { return false; } };
  const guardarApagada = v => { try { localStorage.setItem(CLAVE_APAGADA, v ? '1' : '0'); } catch (e) { /* sin storage */ } };

  const ia = {
    apagada: leerApagada(),
    disponible: false, modelo: null,
    sug: null, clave: null, claveFallida: null, cargando: false,
    ultimaExtraccion: null,
    historial: [], historialEp: null
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

  /* ---------- 1. Indicador de estado y modo sin IA ---------- */
  const activa = () => ia.disponible && !ia.apagada;
  const updOllamaOriginal = window.updOllama;
  const $id = id => document.getElementById(id);
  const textoExtraer = $id('extraer') ? $id('extraer').textContent.trim() : 'Extraer datos';

  function avisoRevision() {          // banner en la pantalla 2 cuando se trabaja sin IA
    let a = $id('avisoSinIA');
    const rev = $id('s-revision');
    if (!a && rev) {
      a = document.createElement('div');
      a.id = 'avisoSinIA'; a.className = 'banner'; a.style.marginBottom = '12px';
      rev.insertBefore(a, rev.firstChild);
    }
    return a;
  }

  function aplicarModo() {
    st.ollama = activa();
    try { updOllamaOriginal(); } catch (e) { /* pantalla sin esos elementos */ }
    const chip = $id('ollama');
    if (chip) {
      chip.innerHTML = activa() ? '<span class="dot"></span>IA: ' + (ia.modelo || 'MedGemma')
        : ia.apagada ? '<span class="dot off"></span>IA: apagada'
        : '<span class="dot off"></span>IA: no disponible';
      chip.title = activa() ? 'MedGemma conectado. Tocá para trabajar sin IA.'
        : ia.apagada ? 'Modo sin IA elegido. Tocá para volver a usar MedGemma.'
        : 'MedGemma no responde: se trabaja sin IA. Tocá para volver a verificar.';
    }
    const banner = $id('errBanner');
    if (banner && !activa()) {
      $id('errTitle').textContent = ia.apagada ? 'Modo sin IA. ' : 'MedGemma no responde: se trabaja sin IA. ';
      $id('errMsg').textContent = 'El relato se carga a mano en la pantalla 2 y la prioridad sale de las reglas de seguridad. '
        + 'El dictado por voz sigue funcionando.';
      $id('errCode').textContent = ia.apagada ? 'elegido por el usuario' : '503 · ollama_no_disponible';
    }
    const ext = $id('extraer');
    if (ext && !ext.disabled) ext.textContent = activa() ? textoExtraer : 'Continuar a medición';
    const conf = $id('confirmar');
    if (conf) conf.textContent = activa() ? 'Pedir sugerencia' : 'Ver prioridad sin IA';
    const av = avisoRevision();
    if (av) {
      av.hidden = activa();
      av.innerHTML = '<b>Modo sin IA.</b> <span>Completá a mano los datos del relato (categoría, motivo, desde hace). '
        + 'La prioridad sale de las reglas de seguridad y de los discriminadores que confirmes.</span>';
    }
  }
  window.updOllama = aplicarModo;      // formulario.js lo llama al cambiar de pantalla

  // formulario.js deshabilita "Pedir sugerencia" sin IA; en modo sin IA queda habilitado
  // (la prioridad sale de las reglas). Solo se bloquea si hay valores fuera de rango.
  const updControlOriginal = window.updControl;
  if (typeof updControlOriginal === 'function') {
    window.updControl = function () {
      const out = updControlOriginal.apply(this, arguments);
      const c = $id('confirmar');
      if (c && !activa()) c.disabled = FI.some(f => status(f) === 'bad');
      return out;
    };
  }

  async function chequearEstado() {
    try {
      const j = await fetch('/api/estado', { credentials: 'same-origin' }).then(r => r.json());
      ia.disponible = !!j.ia;
      ia.modelo = j.modelo || null;
    } catch (e) {
      ia.disponible = false;
    }
    aplicarModo();
  }

  /* El chip prende/apaga la IA (reemplaza el botón de demo que solo simulaba la caída) */
  const chipViejo = $id('ollama');
  if (chipViejo) {
    const chip = chipViejo.cloneNode(true);
    chipViejo.replaceWith(chip);
    chip.addEventListener('click', async () => {
      if (activa()) { ia.apagada = true; guardarApagada(true); aplicarModo(); return; }
      ia.apagada = false; guardarApagada(false);
      chip.innerHTML = '<span class="dot off"></span>IA: verificando…';
      await chequearEstado();                         // vuelve a probar si Ollama responde
    });
  }

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
    limpiarChat();                       // relato nuevo = conversación nueva
  }

  /* El chat arranca vacío con cada paciente nuevo (antes quedaban los mensajes del anterior) */
  function limpiarChat() {
    ia.historial = [];
    ia.historialEp = st.ep;
    try { chatEp = null; } catch (e) { /* formulario.js sin chat */ }
    const cm = document.getElementById('chatMsgs');
    if (cm) cm.innerHTML = '';
  }

  /* Datos insuficientes: misma regla que el botón "Pedir sugerencia", pero se aplica
     también si se llega a la pantalla 3 desde la pestaña de arriba */
  function sinDatosSuficientes() {
    return typeof CORE !== 'undefined' && CORE.filter(k => !st.rev[k]).length >= 3;
  }

  /* Sin IA: el relato pasa tal cual y los datos se cargan a mano. Relato nuevo = caso nuevo. */
  function prepararSinIA() {
    const caso = $id('caso');
    const relato = caso ? caso.value.trim() : '';
    if (window.HRRGTraza) window.HRRGTraza.evento('extraccion_sin_ia', { relato, modo: 'sin IA' }, true);
    if (relato !== ia.relatoSinIA) {
      ia.relatoSinIA = relato;
      if (typeof limpiarIA === 'function') limpiarIA();
      if (typeof init === 'function') st.rev = init();
      ia.sug = null; ia.clave = null; ia.claveFallida = null;
      limpiarChat();
    }
  }

  // Botón de la pantalla 1 en modo sin IA: "Continuar a medición"
  const btnExt = $id('extraer');
  if (btnExt) {
    btnExt.addEventListener('click', e => {
      if (activa()) return;
      e.stopImmediatePropagation(); e.preventDefault();
      st.extraccion = null;
      prepararSinIA();
      go('revision');
    }, true);
  }

  // Si MedGemma se cae durante la extracción, no se muestra un error: se pasa solo a modo sin IA
  const fetchOriginal = window.fetch.bind(window);
  window.fetch = async function (url, opciones) {
    const u = typeof url === 'string' ? url : (url && url.url) || '';
    if (!u.includes('/api/analizar')) return fetchOriginal(url, opciones);
    try {                                 // el pedido lleva el episodio para la trazabilidad
      if (window.HRRGTraza && opciones && typeof opciones.body === 'string') {
        const cuerpo = JSON.parse(opciones.body);
        cuerpo.traza = window.HRRGTraza.paraPedido(true);
        opciones = Object.assign({}, opciones, { body: JSON.stringify(cuerpo) });
      }
    } catch (e) { /* sin trazabilidad no se corta la extracción */ }
    let r = null;
    try { r = await fetchOriginal(url, opciones); } catch (e) { r = null; }
    if (r && (r.ok || (r.status !== 503 && r.status < 500))) return r;   // ok, o error del texto (400)
    ia.disponible = false;
    aplicarModo();
    return new Response(JSON.stringify({ _sinIA: true }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };

  const goOriginal = window.go;
  window.go = function (s) {
    if (s === 'revision' && st.extraccion && st.extraccion !== ia.ultimaExtraccion
        && st.extraccion._modelo) {
      ia.ultimaExtraccion = st.extraccion;
      aplicarExtraccion(st.extraccion);
    }
    if (s === 'revision' && st.extraccion && st.extraccion._sinIA && st.extraccion !== ia.ultimaExtraccion) {
      ia.ultimaExtraccion = st.extraccion;           // la IA se cayó en esta extracción
      ia.relatoSinIA = null;
      prepararSinIA();
    }
    if (s === 'resumen' && !st.manual) st.insuf = sinDatosSuficientes();
    return goOriginal.apply(this, arguments);
  };

  /* ---------- 3. Sugerencia de color ---------- */
  const medgemmaSimulada = window.medgemma;

  async function pedirSugerencia(clave) {
    ia.cargando = true;
    try {
      const caso = document.getElementById('caso');
      const j = await post('/api/sugerir', { datos: st.rev, relato: caso ? caso.value : '',
                                             traza: window.HRRGTraza ? window.HRRGTraza.paraPedido(false) : null });
      if (j.insuficiente) {                      // el backend tampoco tiene con qué sugerir
        st.insuf = true;
        ia.claveFallida = clave;
        if (st.screen === 'resumen' && typeof renderResumen === 'function') renderResumen();
        return;
      }
      ia.sug = {
        lv: Number.isInteger(j.nivel) ? j.nivel : 2,
        why: (j.motivos && j.motivos.length) ? j.motivos : ['MedGemma no detalló motivos'],
        fuentes: j.fuentes || [],
        color: j.color
      };
      ia.clave = clave;
    } catch (e) {
      console.warn('[MedGemma] sugerencia falló, paso a modo sin IA:', e.message);
      ia.claveFallida = clave;
      ia.disponible = false;
      aplicarModo();
    } finally {
      ia.cargando = false;
      if (st.screen === 'resumen') window.renderCard();
    }
  }

  window.medgemma = function () {
    const clave = JSON.stringify(st.rev);
    const sim = medgemmaSimulada();
    if (!activa()) { ia.fuente = 'sinIA'; return { lv: sim.lv, why: sim.why }; }
    if (ia.sug && ia.clave === clave) { ia.fuente = 'ia'; return ia.sug; }
    if (st.insuf) {                              // sin datos no se consulta al modelo
      ia.fuente = 'sim';
      return { lv: sim.lv, why: ['Datos insuficientes para sugerir un color'] };
    }
    if (!activa() || ia.claveFallida === clave) {   // sin IA: reglas de ejemplo, sin consultar al modelo
      ia.fuente = 'sinIA';
      return { lv: sim.lv, why: sim.why };
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

  /* Tema de un motivo, para no repetir lo que ya dice una regla ("Hipotensión (TA 85/50)" = "TA sistólica baja") */
  const TEMAS = [['ta', /\bta\b|tensi[oó]n|presi[oó]n|hipotens|hipertens/i], ['fc', /card[ií]aca|\bfc\b|taquicard|bradicard|pulso/i],
    ['fr', /respiratoria|\bfr\b|taquipne/i], ['sat', /satura|spo|ox[ií]geno/i], ['sangrado', /sangr|hemorrag/i],
    ['temp', /temperatura|fiebre|febr/i], ['conc', /conciencia|glasgow/i], ['dolor', /dolor/i],
    ['convulsion', /convuls/i], ['disnea', /disnea|respirar/i], ['trauma', /trauma/i]];
  const tema = t => { const x = TEMAS.find(([, rx]) => rx.test(t)); return x ? x[0] : null; };

  function etiquetarMotivos() {
    const ul = document.getElementById('tcWhy');
    if (!ul) return;
    const items = [...ul.querySelectorAll('li')].filter(li => li.querySelector('.src.ia'));
    const deIA = ia.fuente === 'ia' && ia.sug;
    // temas que ya cubren las reglas de seguridad y los discriminadores confirmados (formulario.js)
    const cubiertos = new Set([...ul.querySelectorAll('li')].filter(li => li.querySelector('.src.r, .src.g'))
      .map(li => tema(li.textContent)).filter(Boolean));
    items.forEach((li, i) => {
      const f = deIA ? (ia.sug.fuentes[i] || 'ia')
        : ia.fuente === 'sinIA' ? (/^Refiere/i.test(li.textContent.replace(/^\s*IA/, '').trim()) ? 'relato' : 'medido')
        : 'sim';
      const [cls, txt] = ETIQ[f] || ETIQ.ia;
      const tag = li.querySelector('.src');
      tag.className = 'src ' + cls;
      tag.textContent = txt;
      tag.title = { rel: 'Lo dijo el paciente en el relato', r: 'Criterio Manchester sobre los signos medidos',
                    ia: 'Criterio propio de MedGemma', sim: 'Simulación: reglas de ejemplo en el navegador' }[cls];
      if (deIA) {                                    // repetido: ya lo dice una regla u otro motivo
        const tm = tema(li.textContent);
        if (tm && cubiertos.has(tm)) li.remove(); else if (tm) cubiertos.add(tm);
      }
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
                  sinIA: 'Sin IA · reglas de seguridad y de ejemplo',
                  sim: 'Prioridad de ejemplo · simulada' }[ia.fuente] || 'Prioridad de ejemplo · simulada';
    if (ceja) ceja.innerHTML = txt + ' ' + n;
    etiquetarMotivos();
    if (origen && ia.fuente === 'sinIA') {
      origen.innerHTML = origen.innerHTML
        .replace('Simulación con reglas de ejemplo.', 'Sin IA: reglas de seguridad y reglas de ejemplo.')
        .replace('La simulación sugería', 'Las reglas de ejemplo sugerían');
    }
    if (origen && ia.fuente === 'ia') {
      origen.innerHTML = origen.innerHTML
        .replace('Simulación con reglas de ejemplo.', 'Sugerencia de MedGemma + reglas de seguridad.')
        .replace('La simulación sugería', 'MedGemma sugería');
    }
    return out;
  };

  /* ---------- 4. Chat ---------- */
  function origenTexto() {              // "Color fijado por regla de seguridad. MedGemma sugería…"
    const o = document.getElementById('tcOrigin');
    if (!o) return '';
    return [...o.childNodes].map(n => n.textContent.trim()).filter(t => t && !/^Reglas provisorias$/i.test(t)).join(' ');
  }

  function subirTexto() {               // el recuadro "Pasaría a X si se cumple alguno"
    const box = document.getElementById('subir');
    if (!box || box.hidden) return '';
    const titulo = box.querySelector('h4');
    const items = [...box.querySelectorAll('li .q, li')].map(x => x.querySelector ? (x.querySelector('.q') || x).textContent.trim() : '');
    const unicos = [...new Set(items.filter(Boolean))];
    return (titulo ? titulo.textContent.replace(/·.*$/, '').trim() + ': ' : '') + unicos.join('; ');
  }

  const preguntarSimulada = window.preguntarIA;
  window.preguntarIA = async function (q) {
    try {
      if (ia.historialEp !== st.ep) { ia.historial = []; ia.historialEp = st.ep; }
      const color = st.insuf ? 'sin sugerencia (datos insuficientes)'
        : (typeof LEVELS !== 'undefined' && typeof SUG !== 'undefined') ? LEVELS[SUG][0] : '';
      // contexto: los motivos que ve el profesional en "Por qué" y los datos que faltan
      const motivos = [...document.querySelectorAll('#tcWhy li')].map(li => {
        const tag = li.querySelector('.src'); const t = li.textContent.trim();
        return tag ? '[' + tag.textContent.trim() + '] ' + t.slice(tag.textContent.trim().length).trim() : t;
      });
      const faltan = (typeof missing === 'function' && typeof ml === 'function') ? missing().map(ml) : [];
      const caso = document.getElementById('caso');
      const j = await post('/api/consulta', {
        pregunta: q, episodio: st.ep, datos: st.rev, sugerencia: color,
        contexto: { motivos, faltan, subir: subirTexto(), origen: origenTexto() }, historial: ia.historial.slice(-4),
        relato: caso ? caso.value : '', sin_ia: !activa(),
        traza: window.HRRGTraza ? window.HRRGTraza.paraPedido(false) : null
      });
      ia.historial.push({ pregunta: q, respuesta: j.respuesta });
      const aviso = (typeof AVISO !== 'undefined') ? AVISO : '';
      return j.respuesta + aviso;
    } catch (e) {
      console.warn('[MedGemma] chat falló, uso simulación:', e.message);
      return preguntarSimulada(q);
    }
  };

  /* ---------- 5. Mensaje de "Datos extraídos" viejo mientras se procesa uno nuevo ---------- */
  const hint = document.getElementById('hint');
  const hintInicial = hint ? hint.textContent : '';
  const btnExtraer = document.getElementById('extraer');
  if (btnExtraer && hint) {
    btnExtraer.addEventListener('click', () => { hint.textContent = hintInicial; hint.classList.remove('err'); }, true);
  }

  aplicarModo();
  chequearEstado();
})();
