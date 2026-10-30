/* frontend/js/reglas.js · Pantalla de reglas del hospital (propuesta Barby 28/10; pantalla nueva Dario 30/10).
   Pestañas: Reglas (lista agrupada por color, filtros, búsqueda, interruptor Activa/Inactiva) · Tiempos por color ·
   Historial de cambios · Cómo funcionan. Jefatura de Guardia: crea, edita, prueba con un caso, activa y desactiva.
   Auditoría: solo lectura. Todo se guarda en el servidor (/api/reglas, backend/src/reglas_hospital.py) y cada
   cambio queda registrado. En pantalla hay solo dos estados: Activa e Inactiva (las nuevas arrancan inactivas). */
(function () {
  'use strict';
  const api = window.TriageAPI;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const COLOR_VAR = { ROJO: ['--m-rojo', '#FFFFFF'], NARANJA: ['--m-naranja', '#1A1D26'], AMARILLO: ['--m-amarillo', '#1A1D26'], VERDE: ['--m-verde', '#FFFFFF'] };
  const GRUPOS = [
    ['Signos vitales', ['ta_sistolica', 'ta_diastolica', 'pam', 'frecuencia_cardiaca', 'frecuencia_respiratoria', 'saturacion_o2', 'temperatura', 'glucemia']],
    ['Conciencia y dolor', ['estado_conciencia', 'glasgow', 'dolor_intensidad']],
    ['Paciente y motivo', ['edad', 'grupo_etario', 'sexo', 'motivo_categoria']],
    ['Banderas rojas', ['br_sangrado', 'br_convulsion', 'br_disnea', 'br_trauma']],
    ['Antecedentes', ['ant_diabetes', 'ant_cardio', 'ant_resp', 'ant_anticoag', 'ant_inmuno', 'ant_embarazo', 'ant_medicacion']]
  ];

  let yo = null, soloLectura = true, CAT = {}, OPS = {}, MAX = 8;
  /* [Dario 29/10] Origen de la regla (lo manda el servidor en /api/reglas/campos). */
  let ORIG = [['manchester', 'Sistema Manchester'], ['local', 'Adaptación local HRRG'], ['provisoria', 'Provisoria / en revisión']];
  const textoOrigen = (o) => (ORIG.find((x) => x[0] === o) || [o, o])[1];
  let reglas = [];
  let editor = null, pendiente = null, abiertos = new Set(), cargando = false;
  /* [Dario 29/10 · Etapa C] Tiempos objetivo por color (minutos). */
  let tiempos = null, tiemposRef = null, tiemposConf = false, tiemposAct = null, tiemposMsg = null;

  const chipColor = (c, txt) => {
    const v = COLOR_VAR[c] || ['--line', 'inherit'];
    return '<span class="chipc" style="background:var(' + v[0] + ');color:' + v[1] + '">' + esc(txt || c) + '</span>';
  };
  const fecha = (iso) => { try { return new Date(iso).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' }); } catch (e) { return iso; } };
  const describir = (c) => MotorReglas.describir(c, CAT);
  function error(msg) { const b = $('rgErr'); b.hidden = !msg; if (msg) b.querySelector('b').textContent = msg; }

  async function llamar(ruta, cuerpo) {
    const r = await api.pedir(ruta, cuerpo === undefined ? { method: 'GET', cache: 'no-store' } : { method: 'POST', body: JSON.stringify(cuerpo) });
    if (r.estado === 401) { location.href = 'index.html'; throw new Error('sesión'); }
    return r;
  }

  async function cargar() {
    cargando = true;
    const r = await llamar('/api/reglas');
    cargando = false;
    if (!r.ok) { error(r.datos.mensaje || 'No se pudieron leer las reglas.'); return; }
    error(null);
    reglas = r.datos.reglas || []; historialGeneral = r.datos.historial_general || [];
    pintar();
    if (pestana === 'historial') pintarHistorial();
  }

  /* ---------- Signos vitales (Dario 30/10 · tabla parametros_signos) ---------- */
  let signos = [], sgGrupos = ['Adulto'], sgGrupo = 'Adulto', sgHist = [], sgMsg = {};
  async function cargarSignos() {
    const r = await llamar('/api/signos');
    if (!r.ok) { $('sgTabla').innerHTML = '<div class="werr">' + esc(r.datos.mensaje || 'No se pudieron leer los rangos.') + '</div>'; return; }
    signos = r.datos.parametros || []; sgGrupos = r.datos.grupos || sgGrupos; sgHist = r.datos.historial || [];
    pintarSignos();
  }
  const nro = (v) => (v === null || v === undefined ? '' : String(v).replace('.', ','));
  function pintarSignos() {
    $('sgGrupos').innerHTML = sgGrupos.map((g) => {
      const propias = signos.filter((p) => p.grupo_etario === g).length;
      return '<button type="button" class="rg-f" data-g="' + esc(g) + '" aria-pressed="' + (g === sgGrupo) + '">' + esc(g) +
        (g === 'Adulto' ? '' : ' · ' + (propias ? propias + ' propios' : 'usa Adulto')) + '</button>';
    }).join('');
    const base = signos.filter((p) => p.grupo_etario === 'Adulto');
    const filas = base.map((b) => {
      const p = signos.find((x) => x.campo === b.campo && x.grupo_etario === sgGrupo) || null, v = p || b;
      const hereda = !p, dis = soloLectura || hereda ? ' disabled' : '', k = esc(b.campo);
      const inp = (n, w) => '<input data-sg="' + n + '" value="' + esc(n.startsWith('texto') ? v[n] : nro(v[n])) + '"' + dis + ' style="width:' + (w || 60) + 'px"' + (n.startsWith('texto') ? '' : ' inputmode="decimal"') + '>';
      let acc = '';
      if (!soloLectura) acc = hereda ? '<button type="button" class="btn ghost" data-sgacc="crear">Usar valores propios</button>'
        : '<button type="button" class="btn" data-sgacc="guardar">Guardar</button>' + (sgGrupo === 'Adulto' ? '' : ' <button type="button" class="linkbtn" data-sgacc="quitar">volver a Adulto</button>');
      return '<tr data-campo="' + k + '"' + (hereda ? ' class="rg-hereda"' : '') + '><td><b>' + esc(v.nombre) + '</b><div class="hint">' + esc(v.unidad) + (hereda ? ' · valores de Adulto' : ' · v' + v.version) + '</div></td>' +
        '<td>' + inp('normal_min') + ' – ' + inp('normal_max') + '</td><td>' + inp('minimo_posible') + ' – ' + inp('maximo_posible') + '</td>' +
        '<td>' + inp('texto_bajo', 130) + '</td><td>' + inp('texto_alto', 130) + '</td>' +
        '<td><input type="checkbox" data-sg="obligatorio"' + (v.obligatorio ? ' checked' : '') + dis + '></td><td>' + acc +
        (sgMsg[b.campo] ? '<div class="' + (sgMsg[b.campo].ok ? 'hint' : 'werr') + '">' + esc(sgMsg[b.campo].t) + '</div>' : '') + '</td></tr>';
    }).join('');
    $('sgTabla').innerHTML = base.length
      ? '<table class="rg-tabla rg-sgtabla"><thead><tr><th>Signo</th><th>Normal</th><th>Posible</th><th>Texto si está bajo</th><th>Texto si está alto</th><th>Oblig.</th><th></th></tr></thead><tbody>' + filas + '</tbody></table>'
      : '<div class="rg-vacio">No hay rangos cargados.</div>';
  }
  function datosFila(tr, origen) {
    const d = Object.assign({}, origen);
    ['id', 'version', 'creada_por', 'creada_en', 'actualizada_por', 'actualizada_en', 'validada_en'].forEach((k) => delete d[k]);
    tr.querySelectorAll('[data-sg]').forEach((i) => { d[i.dataset.sg] = i.type === 'checkbox' ? i.checked : i.value.trim(); });
    d.grupo_etario = sgGrupo;
    return d;
  }
  $('sgGrupos').addEventListener('click', (e) => { const b = e.target.closest('[data-g]'); if (b) { sgGrupo = b.dataset.g; sgMsg = {}; pintarSignos(); } });
  $('sgTabla').addEventListener('click', async (e) => {
    const b = e.target.closest('[data-sgacc]'); if (!b) return;
    const tr = b.closest('tr'), campo = tr.dataset.campo;
    const adulto = signos.find((x) => x.campo === campo && x.grupo_etario === 'Adulto');
    const propio = signos.find((x) => x.campo === campo && x.grupo_etario === sgGrupo);
    let r;
    if (b.dataset.sgacc === 'crear') r = await llamar('/api/signos', datosFila(tr, adulto));            /* copia los de Adulto */
    else if (b.dataset.sgacc === 'guardar') r = await llamar('/api/signos', datosFila(tr, propio));
    else {
      if (!confirm('¿Quitar los valores propios de ' + sgGrupo + ' para «' + propio.nombre + '»? Se vuelven a usar los de Adulto.')) return;
      r = await llamar('/api/signos/' + propio.id + '/eliminar', {});
    }
    sgMsg = { [campo]: r.ok ? { ok: true, t: r.datos.sin_cambios ? 'No había cambios.' : 'Guardado.' } : { ok: false, t: r.datos.mensaje || 'No se pudo guardar.' } };
    if (r.ok) await cargarSignos(); else pintarSignos();
  });

  /* ---------- Tiempos objetivo por color (Etapa C) ---------- */
  async function cargarTiempos() {
    const r = await llamar('/api/reglas/tiempos');
    if (!r.ok) { tiemposMsg = r.datos.mensaje || 'No se pudieron leer los tiempos.'; return pintarTiempos(); }
    tiempos = r.datos.tiempos; tiemposRef = r.datos.por_defecto; tiemposConf = !!r.datos.confirmados; tiemposAct = r.datos.actualizado;
    pintarTiempos();
  }
  function pintarTiempos() {
    const box = $('rgTiempos'); if (!box) return;
    if (!tiempos) { box.innerHTML = '<div class="hint">' + esc(tiemposMsg || 'Cargando tiempos…') + '</div>'; return; }
    const estado = tiemposConf
      ? 'Guardados por ' + esc(tiemposAct.por) + ', ' + esc(fecha(tiemposAct.en))
      : 'Son los de <b>referencia del Sistema Manchester</b>: todavía no fueron confirmados por la Guardia del HRRG.';
    box.innerHTML = '<div><b>Tiempo objetivo máximo de atención por color</b> (minutos). Lo usan la pantalla En espera, la sala de espera y la API del hospital. ' + estado + '</div>' +
      '<div class="rg-tgrid">' + Object.keys(COLOR_VAR).map((c) => '<label>' + chipColor(c) + '<input data-t="' + c + '" inputmode="numeric" value="' + esc(tiempos[c]) + '"' +
        (soloLectura ? ' disabled' : '') + '><span class="hint">min' + (tiemposRef && tiemposRef[c] !== tiempos[c] ? ' (ref. ' + tiemposRef[c] + ')' : '') + '</span></label>').join('') + '</div>' +
      (tiemposMsg ? '<div class="werr">' + esc(tiemposMsg) + '</div>' : '') +
      (soloLectura ? '' : '<div class="row"><button type="button" class="btn" id="tGuardar">' + (tiemposConf ? 'Guardar cambios' : 'Confirmar o guardar tiempos') + '</button></div>');
  }
  async function guardarTiempos() {
    const cuerpo = {};
    document.querySelectorAll('#rgTiempos input[data-t]').forEach((i) => { cuerpo[i.dataset.t] = i.value.trim(); });
    const res = await llamar('/api/reglas/tiempos', cuerpo);
    tiemposMsg = res.ok ? null : (res.datos.mensaje || 'No se pudieron guardar los tiempos.');
    if (res.ok) await cargarTiempos(); else pintarTiempos();
  }
  $('rgTiempos').addEventListener('click', (e) => { if (e.target.id === 'tGuardar') guardarTiempos(); });

  /* ---------- Pestañas [Dario 30/10: pantalla nueva] ---------- */
  let pestana = 'reglas';
  function mostrarPestana(p) {
    pestana = p;
    document.querySelectorAll('#rgTabs [data-tab]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === p)));
    ['reglas', 'tiempos', 'signos', 'historial', 'ayuda'].forEach((k) => { $('tab-' + k).hidden = k !== p; });
    if (p === 'historial') pintarHistorial();
    try { localStorage.setItem('hrrg_reglas_tab', p); } catch (e) { /* sin almacenamiento: no importa */ }
  }
  $('rgTabs').addEventListener('click', (e) => { const b = e.target.closest('[data-tab]'); if (b) mostrarPestana(b.dataset.tab); });

  /* ---------- Lista ---------- */
  /* En pantalla solo hay dos estados: ACTIVA (interviene) e INACTIVA (no interviene; incluye las recién creadas). */
  const activa = (r) => r.estado === 'activa';
  const ORDEN_COLOR = ['ROJO', 'NARANJA', 'AMARILLO', 'VERDE'];
  const TITULO_COLOR = { ROJO: 'ROJO · atención inmediata', NARANJA: 'NARANJA · muy urgente', AMARILLO: 'AMARILLO · urgente', VERDE: 'VERDE · estándar' };
  let fEstado = 'todas', fOrigen = null, busqueda = '', historialGeneral = [];

  function fraseRegla(r) {
    const cs = r.condiciones.map((c) => esc(describir(c)));
    return 'Si ' + cs.join(r.combinacion === 'alguna' ? ' <b>o</b> ' : ' <b>y</b> ');
  }
  function pasaFiltros(r) {
    if (fEstado === 'activa' && !activa(r)) return false;
    if (fEstado === 'inactiva' && activa(r)) return false;
    if (fOrigen === 'sinvalidar' && r.validada_por) return false;
    if (fOrigen && fOrigen !== 'sinvalidar' && r.origen !== fOrigen) return false;
    if (busqueda) {
      const texto = (r.codigo + ' ' + r.nombre + ' ' + r.explicacion + ' ' + r.discriminador + ' ' +
        r.condiciones.map((c) => describir(c)).join(' ')).toLowerCase();
      if (!texto.includes(busqueda)) return false;
    }
    return true;
  }
  function pintar() {
    const act = reglas.filter(activa).length, sinVal = reglas.filter((r) => !r.validada_por).length;
    $('rgResumen').innerHTML =
      '<div><span>Activas · intervienen</span><b>' + act + '</b></div>' +
      '<div><span>Inactivas · no intervienen</span><b>' + (reglas.length - act) + '</b></div>' +
      '<div class="' + (sinVal ? 'alerta' : '') + '"><span>Sin validar por la Guardia</span><b>' + sinVal + '</b>' + (sinVal ? '<small>Revisar con Enfermería y Guardia</small>' : '') + '</div>' +
      '<div><span>Total de reglas</span><b>' + reglas.length + '</b></div>';
    document.querySelectorAll('#rgFiltros [data-f]').forEach((b) => {
      const [tipo, val] = b.dataset.f.split(':');
      b.setAttribute('aria-pressed', String(tipo === 'e' ? fEstado === val : fOrigen === val));
    });
    if (!reglas.length) {
      $('rgLista').innerHTML = '<div class="rg-vacio">Todavía no hay reglas.' + (soloLectura ? '' : ' Tocá <b>+ Nueva regla</b> para cargar la primera.') + '</div>';
      return;
    }
    const visibles = reglas.filter(pasaFiltros);
    if (!visibles.length) { $('rgLista').innerHTML = '<div class="rg-vacio">Ninguna regla coincide con los filtros.</div>'; return; }
    let html = '<table class="rg-tabla"><thead><tr><th></th><th>Regla</th><th>Sube a</th><th>Origen</th><th>Validación</th><th>Estado</th><th></th></tr></thead><tbody>';
    ORDEN_COLOR.forEach((color) => {
      const grupo = visibles.filter((r) => r.color === color).sort((a, b) => Number(activa(b)) - Number(activa(a)) || a.id - b.id);
      if (!grupo.length) return;
      html += '<tr class="rg-grupo"><td colspan="7">' + esc(TITULO_COLOR[color]) + '</td></tr>' + grupo.map(fila).join('');
    });
    $('rgLista').innerHTML = html + '</tbody></table>';
  }
  function fila(r) {
    const v = COLOR_VAR[r.color] || ['--line', 'inherit'], on = activa(r), id = r.id;
    const confirma = pendiente === 'desactivar:' + id, confElim = pendiente === 'eliminar:' + id;
    const interruptor = '<button type="button" class="rg-sw' + (on ? ' on' : '') + '" role="switch" aria-checked="' + on + '" data-acc="interruptor" data-id="' + id + '"' +
      (soloLectura ? ' disabled' : '') + ' title="' + (soloLectura ? 'Solo lectura' : on ? 'Desactivar' : 'Activar') + '"><i></i><span>' + (on ? 'Activa' : 'Inactiva') + '</span></button>';
    let acciones = '<button type="button" class="linkbtn" data-acc="detalle" data-id="' + id + '">' + (abiertos.has(id) ? 'Ocultar' : 'Detalle') + '</button>';
    if (!soloLectura) {
      acciones = '<button type="button" class="linkbtn" data-acc="editar" data-id="' + id + '">Editar</button> · ' + acciones;
      if (!on && !r.fue_activada) acciones += ' · <button type="button" class="linkbtn rg-elim" data-acc="eliminar" data-id="' + id + '">' + (confElim ? 'Confirmar: eliminar' : 'Eliminar') + '</button>';
    }
    let html = '<tr class="rg-fila' + (on ? '' : ' off') + '">' +
      '<td class="rg-cb"><div style="background:var(' + v[0] + ')"></div></td>' +
      '<td><span class="rg-cod">' + esc(r.codigo) + '</span> <b class="rg-nom">' + esc(r.nombre) + '</b><div class="rg-frase-c">' + fraseRegla(r) + '</div></td>' +
      '<td>' + chipColor(r.color) + '</td>' +
      '<td><span class="src h' + (r.origen === 'provisoria' ? ' prov' : '') + '">' + esc(MotorReglas.etiqueta(r.origen)) + '</span></td>' +
      '<td>' + (r.validada_por ? '<span class="rg-val ok">✔ ' + esc(r.validada_por) + (r.validada_en ? ' · ' + esc(fecha(r.validada_en).split(',')[0]) : '') + '</span>' : '<span class="rg-val no">● Sin validar</span>') + '</td>' +
      '<td>' + interruptor + '</td><td class="rg-acc">' + acciones + '</td></tr>';
    if (confirma) {
      html += '<tr class="rg-conf"><td></td><td colspan="6"><b>¿Desactivar esta regla ROJA?</b> Deja de intervenir desde el próximo paciente. ' +
        '<button type="button" class="btn sm danger" data-acc="desactivar" data-id="' + id + '">Sí, desactivar</button> ' +
        '<button type="button" class="btn sm" data-acc="cancelar" data-id="' + id + '">Cancelar</button></td></tr>';
    }
    if (abiertos.has(id)) {
      html += '<tr class="rg-det"><td></td><td colspan="6">' +
        '<div class="rg-pq"><span class="src h' + (r.origen === 'provisoria' ? ' prov' : '') + '">' + esc(MotorReglas.etiqueta(r.origen)) + '</span> <span>' + esc(r.explicacion) + '</span> <span class="hint">(así se ve en el «Por qué»)</span></div>' +
        '<div class="hint">' + esc(textoOrigen(r.origen)) + (r.discriminador ? ' · Discriminador / criterio: ' + esc(r.discriminador) : '') +
        ' · Versión ' + r.version + ' · último cambio: ' + esc(r.actualizada_por) + ', ' + esc(fecha(r.actualizada_en)) + '</div>' +
        '<ul class="rg-hist">' + (r.historial || []).slice().reverse().map((h) => '<li>' + esc(fecha(h.fecha)) + ' · <b>' + esc(textoAccion(h.accion)) + '</b>' +
          (h.version ? ' · v' + h.version : '') + ' · ' + esc(h.usuario) + '</li>').join('') + '</ul></td></tr>';
    }
    return html;
  }
  /* El historial guarda el texto original; en pantalla «borrador» se lee como «inactiva». */
  const textoAccion = (a) => String(a || '').replace(/pasó a borrador/g, 'quedó inactiva').replace(/borrador/g, 'inactiva');

  function pintarHistorial() {
    const filas = [];
    reglas.forEach((r) => (r.historial || []).forEach((h) => filas.push(Object.assign({ regla: r.codigo + ' ' + r.nombre }, h))));
    historialGeneral.forEach((h) => filas.push(Object.assign({ regla: '— (configuración)' }, h)));
    sgHist.forEach((h) => filas.push(Object.assign({}, h, { regla: 'Signo vital: ' + (h.campo ? h.campo + ' · ' + h.grupo_etario : '—'), accion: 'Rango ' + String(h.accion || '').toLowerCase() })));
    filas.sort((a, b) => (a.fecha < b.fecha ? 1 : -1));
    $('rgHistorial').innerHTML = filas.length
      ? '<table class="rg-tabla rg-htabla"><thead><tr><th>Fecha</th><th>Usuario</th><th>Regla</th><th>Qué pasó</th><th>Versión</th></tr></thead><tbody>' +
        filas.map((h) => '<tr><td>' + esc(fecha(h.fecha)) + '</td><td>' + esc(h.usuario) + '</td><td>' + esc(h.regla) + '</td><td>' + esc(textoAccion(h.accion)) + '</td><td>' + (h.version ? 'v' + h.version : '—') + '</td></tr>').join('') +
        '</tbody></table>'
      : '<div class="rg-vacio">Todavía no hay cambios registrados.</div>';
  }

  $('rgFiltros').addEventListener('click', (e) => {
    const b = e.target.closest('[data-f]'); if (!b) return;
    const [tipo, val] = b.dataset.f.split(':');
    if (tipo === 'e') fEstado = val; else fOrigen = fOrigen === val ? null : val;
    pintar();
  });
  $('rgBuscar').addEventListener('input', (e) => { busqueda = e.target.value.trim().toLowerCase(); pintar(); });

  /* Interruptor: activar es inmediato; desactivar una regla ROJA pide confirmación. Eliminar, también. */
  $('rgLista').addEventListener('click', async (e) => {
    const b = e.target.closest('[data-acc]'); if (!b || b.disabled) return;
    const id = +b.dataset.id, acc = b.dataset.acc, r = reglas.find((x) => x.id === id);
    if (!r) return;
    if (acc === 'detalle') { abiertos.has(id) ? abiertos.delete(id) : abiertos.add(id); return pintar(); }
    if (acc === 'editar') { pendiente = null; return abrirEditor(r); }
    if (acc === 'cancelar') { pendiente = null; return pintar(); }
    let ruta = null;
    if (acc === 'interruptor') {
      if (!activa(r)) ruta = 'activar';
      else if (r.color === 'ROJO') { pendiente = 'desactivar:' + id; return pintar(); }
      else ruta = 'desactivar';
    } else if (acc === 'desactivar') ruta = 'desactivar';
    else if (acc === 'eliminar') {
      if (pendiente !== 'eliminar:' + id) { pendiente = 'eliminar:' + id; return pintar(); }
      ruta = 'eliminar';
    }
    if (!ruta) return;
    pendiente = null; b.disabled = true;
    const res = await llamar('/api/reglas/' + id + '/' + ruta, {});
    if (!res.ok) error(res.datos.mensaje || 'No se pudo completar la acción.');
    await cargar();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && pendiente) { pendiente = null; pintar(); } });

  /* ---------- Editor ---------- */
  function condVacia() { return { campo: 'saturacion_o2', operador: '<', valor: '' }; }
  function abrirEditor(r) {
    editor = r ? { id: r.id, codigo: r.codigo, estado: r.estado, nombre: r.nombre, explicacion: r.explicacion, color: r.color, combinacion: r.combinacion,
      origen: r.origen || 'provisoria', validada_por: r.validada_por || '', discriminador: r.discriminador || '',
      condiciones: r.condiciones.map((c) => ({ campo: c.campo, operador: c.operador, valor: c.valor == null ? '' : String(c.valor).replace('.', ',') })), prueba: {}, error: null }
      : { id: null, nombre: '', explicacion: '', color: 'NARANJA', combinacion: 'todas', origen: 'provisoria', validada_por: '', discriminador: '', condiciones: [condVacia()], prueba: {}, error: null };
    pintarEditor();
    $('rgEditor').scrollIntoView({ behavior: 'smooth', block: 'start' });
    const i = $('edNombre'); if (i) i.focus();
  }
  function cerrarEditor() { editor = null; $('rgEditor').hidden = true; $('rgEditor').innerHTML = ''; $('rgNueva').hidden = soloLectura; }

  function opcionesCampo(sel) {
    return GRUPOS.map(([g, ks]) => '<optgroup label="' + esc(g) + '">' + ks.filter((k) => CAT[k]).map((k) =>
      '<option value="' + k + '"' + (k === sel ? ' selected' : '') + '>' + esc(CAT[k].etiqueta) + '</option>').join('') + '</optgroup>').join('');
  }
  function filaCond(c, i) {
    const info = CAT[c.campo] || { tipo: 'num' }, ops = OPS[info.tipo] || [];
    let valor = '';
    if (info.tipo === 'num') valor = '<input data-cv="' + i + '" inputmode="decimal" value="' + esc(c.valor) + '" placeholder="' + info.min + '–' + info.max + '"><span class="hint">' + esc(info.unidad || '') + '</span>';
    else if (info.tipo === 'opcion') valor = '<select data-cv="' + i + '"><option value="">Elegir…</option>' + info.opciones.map((o) => '<option' + (o === c.valor ? ' selected' : '') + '>' + esc(o) + '</option>').join('') + '</select>';
    return '<div class="rg-cond"><select data-cc="' + i + '" aria-label="Dato">' + opcionesCampo(c.campo) + '</select>' +
      '<select data-co="' + i + '" aria-label="Condición">' + ops.map(([k, t]) => '<option value="' + k + '"' + (k === c.operador ? ' selected' : '') + '>' + esc(t) + '</option>').join('') + '</select>' +
      valor + (editor.condiciones.length > 1 ? '<button type="button" class="linkbtn" data-cq="' + i + '">Quitar</button>' : '') +
      (info.ayuda ? '<span class="hint">' + esc(info.ayuda) + '</span>' : '') + '</div>';
  }
  function reglaDelEditor() {
    return { codigo: editor.codigo || 'nueva', nombre: editor.nombre, version: 0, color: editor.color, combinacion: editor.combinacion,
      origen: editor.origen, validada_por: editor.validada_por, discriminador: editor.discriminador,
      explicacion: editor.explicacion, condiciones: editor.condiciones.map((c) => ({ campo: c.campo, operador: c.operador, valor: (CAT[c.campo] || {}).tipo === 'bool' ? null : c.valor })) };
  }
  function frase() {
    const cs = editor.condiciones.map((c) => describir({ campo: c.campo, operador: c.operador, valor: c.valor === '' ? '…' : c.valor }));
    return 'Si ' + cs.join(editor.combinacion === 'todas' ? ' <b>y</b> ' : ' <b>o</b> ') + ' → la sugerencia es como mínimo ' + chipColor(editor.color) + '.';
  }
  function pintarPrueba() {
    const box = $('edPrueba'); if (!box || !editor) return;
    const campos = [...new Set(editor.condiciones.map((c) => c.campo))];
    const res = MotorReglas.evaluar([reglaDelEditor()], editor.prueba);
    box.querySelector('.rg-res').innerHTML = res.length
      ? '<span class="rg-si-ok">✔ Con estos datos la regla <b>se cumple</b>: la sugerencia sería como mínimo ' + chipColor(editor.color) + '.</span>'
      : '<span class="rg-no">✘ Con estos datos la regla <b>no se cumple</b>' + (campos.some((k) => editor.prueba[k] === undefined || editor.prueba[k] === '') ? ' (un dato vacío nunca cumple una condición)' : '') + '.</span>';
  }
  function pintarEditor() {
    const ed = $('rgEditor'); if (!editor) { ed.hidden = true; return; }
    $('rgNueva').hidden = true;
    const campos = [...new Set(editor.condiciones.map((c) => c.campo))];
    ed.innerHTML = '<h3>' + (editor.id ? 'Editar ' + esc(editor.codigo) : 'Nueva regla') + '</h3>' +
      (editor.estado === 'activa' ? '<div class="banner"><b>Esta regla está activa.</b><span>Los cambios se aplican desde el próximo paciente. Para que deje de intervenir, usá el interruptor.</span></div>' : '') +
      '<div class="rg-grid"><label>Nombre corto <input id="edNombre" maxlength="80" value="' + esc(editor.nombre) + '" placeholder="Ej.: Hipoxemia"></label>' +
      '<div class="rg-colores" role="radiogroup" aria-label="Color mínimo"><span class="lbl">Color mínimo</span>' + Object.keys(COLOR_VAR).map((c) =>
        '<button type="button" class="lvl" data-col="' + c + '" aria-pressed="' + (c === editor.color) + '" style="background:var(' + COLOR_VAR[c][0] + ');color:' + COLOR_VAR[c][1] + '">' + c + '</button>').join('') + '</div></div>' +
      '<div class="rg-grid"><label>Origen de la regla <select id="edOrigen">' + ORIG.map(([k, t]) => '<option value="' + k + '"' + (k === editor.origen ? ' selected' : '') + '>' + esc(t) + '</option>').join('') + '</select></label>' +
      '<label>Validada por <span class="hint">(profesional o servicio; vacío = sin validar; la fecha se registra sola)</span><input id="edValidada" maxlength="120" value="' + esc(editor.validada_por) + '" placeholder="Ej.: Jefatura de Enfermería de Guardia"></label></div>' +
      '<label class="rg-expl">Discriminador Manchester o criterio clínico que respalda la regla <span class="hint">(opcional; queda en la matriz, no cambia el cálculo)</span>' +
      '<input id="edDiscr" maxlength="200" value="' + esc(editor.discriminador) + '" placeholder="Ej.: Dolor de características cardíacas (diagrama Dolor torácico)"></label>' +
      '<div class="rg-conds"><span class="lbl">Condiciones</span>' +
      (editor.condiciones.length > 1 ? '<div class="rg-comb"><label><input type="radio" name="edComb" value="todas"' + (editor.combinacion === 'todas' ? ' checked' : '') + '> Se tienen que cumplir <b>todas</b></label>' +
        '<label><input type="radio" name="edComb" value="alguna"' + (editor.combinacion === 'alguna' ? ' checked' : '') + '> Alcanza con que se cumpla <b>alguna</b></label></div>' : '') +
      editor.condiciones.map(filaCond).join('') +
      (editor.condiciones.length < MAX ? '<button type="button" class="linkbtn" id="edMas">+ Agregar condición</button>' : '') + '</div>' +
      '<label class="rg-expl">Explicación para el profesional (aparece en el «Por qué» de la sugerencia)<textarea id="edExpl" maxlength="300" rows="2" placeholder="Ej.: SpO₂ menor a 92 %: posible compromiso respiratorio">' + esc(editor.explicacion) + '</textarea></label>' +
      '<div class="rg-frase" id="edFrase">' + frase() + '</div>' +
      '<div class="rg-prueba" id="edPrueba"><span class="lbl">Probar con un caso de ejemplo</span><div class="rg-pcampos">' + campos.map((k) => {
        const info = CAT[k] || {}, v = editor.prueba[k];
        if (info.tipo === 'bool') return '<label class="rg-pchk"><input type="checkbox" data-pv="' + k + '"' + (v === true ? ' checked' : '') + '> ' + esc(info.etiqueta) + '</label>';
        if (info.tipo === 'opcion') return '<label>' + esc(info.etiqueta) + '<select data-pv="' + k + '"><option value="">(sin dato)</option>' + info.opciones.map((o) => '<option' + (o === v ? ' selected' : '') + '>' + esc(o) + '</option>').join('') + '</select></label>';
        return '<label>' + esc(info.etiqueta) + ' <span class="hint">' + esc(info.unidad || '') + '</span><input data-pv="' + k + '" inputmode="decimal" value="' + esc(v ?? '') + '" placeholder="(sin dato)"></label>';
      }).join('') + '</div><div class="rg-res"></div></div>' +
      (editor.error ? '<div class="werr">' + esc(editor.error) + '</div>' : '') +
      '<div class="row"><button type="button" class="btn primary" id="edGuardar">Guardar</button><button type="button" class="btn" id="edCancelar">Cancelar</button>' +
      (editor.id ? '' : '<span class="hint">Se guarda <b>inactiva</b>: cuando esté lista, activala con el interruptor.</span>') + '</div>';
    ed.hidden = false;
    pintarPrueba();
  }
  async function guardar() {
    sincronizarTextos();
    const r = reglaDelEditor(), cuerpo = { nombre: r.nombre, explicacion: r.explicacion, color: r.color, combinacion: r.combinacion, condiciones: r.condiciones,
      origen: r.origen, validada_por: r.validada_por, discriminador: r.discriminador };
    if (cuerpo.condiciones.length === 1) cuerpo.combinacion = 'todas';
    const btn = $('edGuardar'); btn.disabled = true; btn.textContent = 'Guardando…';
    const res = await llamar(editor.id ? '/api/reglas/' + editor.id : '/api/reglas', cuerpo);
    if (!res.ok) { editor.error = res.datos.mensaje || 'No se pudo guardar.'; pintarEditor(); return; }
    cerrarEditor(); await cargar();
  }

  /* ---------- Eventos ---------- */
  $('rgNueva').addEventListener('click', () => abrirEditor(null));
  $('rgEditor').addEventListener('click', (e) => {
    const t = e.target;
    if (t.id === 'edCancelar') return cerrarEditor();
    if (t.id === 'edGuardar') return guardar();
    if (t.id === 'edMas') { sincronizarTextos(); editor.condiciones.push(condVacia()); return pintarEditor(); }
    if (t.dataset.cq !== undefined) { sincronizarTextos(); editor.condiciones.splice(+t.dataset.cq, 1); return pintarEditor(); }
    const col = t.closest('[data-col]'); if (col) { sincronizarTextos(); editor.color = col.dataset.col; return pintarEditor(); }
  });
  function sincronizarTextos() {
    const n = $('edNombre'), x = $('edExpl'), o = $('edOrigen'), v = $('edValidada'), d = $('edDiscr');
    if (n) editor.nombre = n.value; if (x) editor.explicacion = x.value;
    if (o) editor.origen = o.value; if (v) editor.validada_por = v.value; if (d) editor.discriminador = d.value;
  }
  $('rgEditor').addEventListener('change', (e) => {
    const t = e.target;
    if (t.name === 'edComb') { sincronizarTextos(); editor.combinacion = t.value; return pintarEditor(); }
    if (t.dataset.cc !== undefined) {
      sincronizarTextos();
      const c = editor.condiciones[+t.dataset.cc], tipo = CAT[t.value].tipo;
      c.campo = t.value; c.operador = OPS[tipo][0][0]; c.valor = '';
      return pintarEditor();
    }
    if (t.dataset.co !== undefined) { editor.condiciones[+t.dataset.co].operador = t.value; $('edFrase').innerHTML = frase(); return pintarPrueba(); }
    if (t.dataset.cv !== undefined && t.tagName === 'SELECT') { editor.condiciones[+t.dataset.cv].valor = t.value; $('edFrase').innerHTML = frase(); return pintarPrueba(); }
    if (t.dataset.pv !== undefined) { editor.prueba[t.dataset.pv] = t.type === 'checkbox' ? t.checked : t.value; return pintarPrueba(); }
  });
  $('rgEditor').addEventListener('input', (e) => {
    const t = e.target;
    if (t.dataset.cv !== undefined && t.tagName === 'INPUT') { editor.condiciones[+t.dataset.cv].valor = t.value; $('edFrase').innerHTML = frase(); pintarPrueba(); }
    if (t.dataset.pv !== undefined && t.type !== 'checkbox') { editor.prueba[t.dataset.pv] = t.value; pintarPrueba(); }
  });
  /* ---------- Inicio ---------- */
  (async function iniciar() {
    if (!api.MODO_REAL) { $('rgLista').innerHTML = '<div class="rg-vacio">Esta pantalla necesita el servidor. Abrila desde Flask: http://127.0.0.1:5000/reglas.html</div>'; return; }
    yo = await api.sesion();
    if (!yo) { location.href = 'index.html'; return; }
    if (yo.debeCambiar) { location.href = 'cambiar_password.html'; return; }
    if (yo.rol !== 'jefatura' && yo.rol !== 'auditor') { location.href = yo.rol === 'admin' ? 'admin.html' : 'formulario.html'; return; }
    soloLectura = yo.rol !== 'jefatura';
    const chip = $('userChip'); chip.hidden = false;
    chip.innerHTML = '<b>' + esc(yo.u) + '</b> · ' + esc(yo.nom) + ' · ' + (soloLectura ? 'Auditoría (solo lectura)' : 'Jefatura de Guardia') +
      (soloLectura ? ' · <a href="formulario.html">Volver</a>' : '') + ' <button type="button" class="linkbtn" id="salir">Salir</button>';
    chip.addEventListener('click', async (e) => { if (e.target.id === 'salir') { try { await api.logout(); } catch (x) {} location.href = 'index.html'; } });
    $('rgNueva').hidden = soloLectura;
    const c = await llamar('/api/reglas/campos');
    if (!c.ok) { error(c.datos.mensaje || 'No se pudo leer el catálogo de datos.'); return; }
    CAT = c.datos.campos; OPS = c.datos.operadores; MAX = c.datos.max_condiciones || 8;
    if (Array.isArray(c.datos.origenes) && c.datos.origenes.length) ORIG = c.datos.origenes;
    await cargar();
    await cargarTiempos();
    await cargarSignos();
    let guardada = 'reglas';
    try { guardada = localStorage.getItem('hrrg_reglas_tab') || 'reglas'; } catch (e) { /* sin almacenamiento */ }
    mostrarPestana(['reglas', 'tiempos', 'signos', 'historial', 'ayuda'].includes(guardada) ? guardada : 'reglas');
  })();
})();
