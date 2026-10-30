/* frontend/js/reglas.js · Pantalla de reglas del hospital (propuesta Barby 28/10).
   Jefatura de Guardia: crea reglas (borrador), las prueba con un caso de ejemplo, las activa,
   desactiva o edita. Auditoría: solo lectura con historial. Todo se guarda en el servidor
   (/api/reglas, backend/src/reglas_hospital.py) y cada cambio queda registrado. */
(function () {
  'use strict';
  const api = window.TriageAPI;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const COLOR_VAR = { ROJO: ['--m-rojo', '#FFFFFF'], NARANJA: ['--m-naranja', '#1A1D26'], AMARILLO: ['--m-amarillo', '#1A1D26'], VERDE: ['--m-verde', '#FFFFFF'] };
  const ESTADO = { activa: 'Activa · interviene', borrador: 'Borrador · no interviene', inactiva: 'Inactiva' };
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
    reglas = r.datos.reglas || [];
    pintar();
  }

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

  /* ---------- Lista ---------- */
  function pintar() {
    const n = (e) => reglas.filter((r) => r.estado === e).length;
    $('rgResumen').innerHTML = '<div><span>Activas</span><b>' + n('activa') + '</b></div><div><span>Borradores</span><b>' + n('borrador') +
      '</b></div><div><span>Inactivas</span><b>' + n('inactiva') + '</b></div>';

    if (!reglas.length) {
      $('rgLista').innerHTML = '<div class="rg-vacio">Todavía no hay reglas del hospital.' + (soloLectura ? '' : ' Tocá <b>Nueva regla</b> para cargar la primera.') + '</div>';
      return;
    }
    const orden = { activa: 0, borrador: 1, inactiva: 2 };
    const lista = reglas.slice().sort((a, b) => orden[a.estado] - orden[b.estado] || a.id - b.id);
    $('rgLista').innerHTML = lista.map(tarjeta).join('');
  }

  function tarjeta(r) {
    const conds = r.condiciones.map((c) => '<li>' + esc(describir(c)) + '</li>').join('');
    const b = (accion, txt, cls) => '<button type="button" class="btn sm' + (cls ? ' ' + cls : '') + '" data-acc="' + accion + '" data-id="' + r.id + '">' + txt + '</button>';
    const conf = (accion) => pendiente === accion + ':' + r.id;
    let acciones = '';
    if (!soloLectura) {
      acciones += b('editar', 'Editar');
      if (r.estado === 'activa') acciones += b('desactivar', conf('desactivar') ? 'Confirmar: desactivar' : 'Desactivar', conf('desactivar') ? 'danger' : '');
      else acciones += b('activar', conf('activar') ? 'Confirmar: activar' : 'Activar', 'primary');
      if (r.estado === 'borrador' && !r.fue_activada) acciones += b('eliminar', conf('eliminar') ? 'Confirmar: eliminar' : 'Eliminar', conf('eliminar') ? 'danger' : 'cancelar');
    }
    acciones += '<button type="button" class="linkbtn" data-acc="historial" data-id="' + r.id + '">' + (abiertos.has(r.id) ? 'Ocultar historial' : 'Ver historial') + '</button>';
    const hist = abiertos.has(r.id) ? '<ul class="rg-hist">' + (r.historial || []).map((h) => '<li>' + esc(fecha(h.fecha)) + ' · <b>' + esc(h.accion) + '</b>' +
      (h.version ? ' · v' + h.version : '') + ' · ' + esc(h.usuario) + '</li>').join('') + '</ul>' : '';
    return '<article class="rg-card ' + r.estado + '" style="--c:var(' + (COLOR_VAR[r.color] || ['--line'])[0] + ')">' +
      '<header><span class="rg-cod">' + esc(r.codigo) + '</span><b>' + esc(r.nombre) + '</b>' + chipColor(r.color, 'al menos ' + r.color) +
      '<span class="rg-est ' + r.estado + '">' + esc(ESTADO[r.estado]) + '</span>' +
      '<span class="rg-org ' + esc(r.origen) + '">' + esc(textoOrigen(r.origen)) + ' · ' + (r.validada_por ? 'validada por ' + esc(r.validada_por) + (r.validada_en ? ' el ' + esc(fecha(r.validada_en)) : '') : 'sin validar') + '</span>' +
      '<span class="hint">v' + r.version + ' · ' + esc(r.actualizada_por) + ', ' + esc(fecha(r.actualizada_en)) + '</span></header>' +
      '<div class="rg-si">' + (r.condiciones.length > 1 ? (r.combinacion === 'todas' ? 'Si se cumplen <b>todas</b> estas condiciones' : 'Si se cumple <b>alguna</b> de estas condiciones') : 'Si se cumple esta condición') + ':<ul>' + conds + '</ul></div>' +
      (r.discriminador ? '<div class="hint">Discriminador / criterio: ' + esc(r.discriminador) + '</div>' : '') +
      '<div class="rg-pq"><span class="src h' + (r.origen === 'provisoria' ? ' prov' : '') + '">' + esc(MotorReglas.etiqueta(r.origen, r.validada_por)) + '</span> <span>' + esc(r.explicacion) + '</span> <span class="hint">(así se ve en el «Por qué»)</span></div>' +
      (r.estado === 'activa' && !soloLectura ? '<div class="hint">Si la editás, vuelve a borrador y deja de intervenir hasta que la actives de nuevo.</div>' : '') +
      '<footer>' + acciones + '</footer>' + hist + '</article>';
  }

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
      (editor.estado === 'activa' ? '<div class="banner"><b>Esta regla está activa.</b><span>Al guardar los cambios vuelve a borrador y deja de intervenir hasta que la actives de nuevo.</span></div>' : '') +
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
      '<div class="row"><button type="button" class="btn primary" id="edGuardar">Guardar como borrador</button><button type="button" class="btn" id="edCancelar">Cancelar</button>' +
      '<span class="hint">Después de guardarla, tocá <b>Activar</b> para que empiece a intervenir.</span></div>';
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
  /* Activar, desactivar y eliminar piden un segundo toque para confirmar. */
  $('rgLista').addEventListener('click', async (e) => {
    const b = e.target.closest('[data-acc]'); if (!b) return;
    const id = +b.dataset.id, acc = b.dataset.acc, r = reglas.find((x) => x.id === id);
    if (acc === 'historial') { abiertos.has(id) ? abiertos.delete(id) : abiertos.add(id); return pintar(); }
    if (acc === 'editar') { pendiente = null; return abrirEditor(r); }
    if (pendiente !== acc + ':' + id) { pendiente = acc + ':' + id; return pintar(); }
    pendiente = null; b.disabled = true;
    const res = await llamar('/api/reglas/' + id + '/' + acc, {});
    if (!res.ok) error(res.datos.mensaje || 'No se pudo completar la acción.');
    await cargar();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && pendiente) { pendiente = null; pintar(); } });

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
  })();
})();
