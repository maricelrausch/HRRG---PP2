/* frontend/js/admin.js · Pantalla de administración de cuentas (perfil admin).
   Usa las rutas /api/admin/... de backend/src/admin_usuarios.py a través de TriageAPI. */
(function () {
  'use strict';
  const api = window.TriageAPI;
  const $ = (id) => document.getElementById(id);
  const ETIQUETAS = { enfermeria: 'Enfermería (triage)', medico: 'Médico/a de guardia', auditor: 'Auditoría (solo lectura)', jefatura: 'Jefatura de Guardia (reglas)', admin: 'Administrador' };
  const CLASE_ESTADO = { 'Activa': '', 'Vencida': 'venc', 'Bloqueada': 'bloq', 'Cambio pendiente': 'fix', 'Desactivada': 'off' };
  let usuarios = [];
  let roles = [];
  let sel = null;

  const etiqueta = (rol) => ETIQUETAS[rol] || rol;
  const mensaje = (texto) => { $('msg').textContent = texto || ''; };

  function opciones(select, conTodos) {
    select.replaceChildren();
    if (conTodos) select.add(new Option('Todos', ''));
    roles.forEach((r) => select.add(new Option(etiqueta(r), r)));
  }

  function insignia(estado) {
    const s = document.createElement('span');
    s.className = ('st ' + (CLASE_ESTADO[estado] || '')).trim();
    s.textContent = estado;
    return s;
  }

  function celda(tr, contenido) {
    const td = document.createElement('td');
    if (contenido instanceof Node) td.appendChild(contenido); else td.textContent = contenido;
    tr.appendChild(td);
    return td;
  }

  function pintarTabla() {
    const q = $('q').value.trim().toLowerCase();
    const rol = $('f-rol').value;
    const est = $('f-estado').value;
    const cuenta = (e) => usuarios.filter((u) => u.estado === e).length;
    $('c-total').textContent = usuarios.filter((u) => u.estado !== 'Desactivada').length;
    $('c-venc').textContent = cuenta('Vencida');
    $('c-bloq').textContent = cuenta('Bloqueada');
    $('c-pend').textContent = cuenta('Cambio pendiente');

    const tb = $('tabla');
    tb.replaceChildren();
    usuarios
      .filter((u) => (!q || (u.nombre + ' ' + u.usuario).toLowerCase().includes(q)) && (!rol || u.rol === rol) && (!est || u.estado === est))
      .forEach((u) => {
        const tr = document.createElement('tr');
        if (sel && sel.id === u.id) tr.className = 'sel';
        const nombre = document.createElement('div');
        nombre.className = 'nom';
        nombre.textContent = u.nombre;
        const usr = document.createElement('div');
        usr.className = 'code';
        usr.textContent = u.usuario;
        const td = celda(tr, nombre);
        td.appendChild(usr);
        celda(tr, etiqueta(u.rol));
        celda(tr, u.dias_desde_cambio == null ? '—' : u.dias_desde_cambio === 0 ? 'hoy' : 'hace ' + u.dias_desde_cambio + ' días').className = 'mono';
        celda(tr, insignia(u.estado));
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'btn sm';
        b.textContent = 'Gestionar';
        b.addEventListener('click', () => { sel = u; ocultarTemporal(); pintarTabla(); pintarDetalle(); });
        celda(tr, b).style.textAlign = 'right';
        tb.appendChild(tr);
      });
  }

  function pintarDetalle() {
    mensaje('');
    $('vacio').hidden = !!sel;
    $('detalle').hidden = !sel;
    if (!sel) return;
    $('d-nombre').textContent = sel.nombre;
    const usr = document.createElement('span');
    usr.className = 'code';
    usr.textContent = sel.usuario;
    $('d-sub').replaceChildren(etiqueta(sel.rol) + ' · ', usr);
    const ins = insignia(sel.estado);
    $('d-estado').className = ins.className;
    $('d-estado').textContent = sel.estado;
    $('d-bloq').hidden = sel.estado !== 'Bloqueada';
    const off = sel.estado === 'Desactivada';
    $('generar').disabled = off;
    $('horas').disabled = off;
    $('d-otras').hidden = sel.propia;
    $('d-propia').hidden = !sel.propia;
    $('d-rol').value = sel.rol;
    $('activar').textContent = off ? 'Reactivar cuenta' : 'Desactivar cuenta';
    $('activar').className = off ? 'btn' : 'btn danger';
  }

  function mostrarTemporal(datos) {
    $('t-clave').textContent = datos.temporal;
    $('t-vence').textContent = 'Entregala en persona. Vence en ' + datos.vence_horas + ' h y el profesional la cambia al ingresar.';
    $('temp').hidden = false;
  }
  function ocultarTemporal() { $('t-clave').textContent = ''; $('temp').hidden = true; }

  async function llamar(ruta, cuerpo) {
    const r = await api.pedir(ruta, cuerpo === undefined
      ? { method: 'GET', cache: 'no-store' }
      : { method: 'POST', body: JSON.stringify(cuerpo) });
    if (r.estado === 401) { location.href = 'index.html'; throw new Error('Sesión vencida.'); }
    if (r.estado === 403 && r.datos.codigo === 'CAMBIO_PASSWORD_REQUERIDO') { location.href = 'cambiar_password.html'; throw new Error(r.datos.mensaje); }
    if (!r.ok) throw new Error(r.datos.mensaje || 'No se pudo completar la operación.');
    return r.datos;
  }

  async function cargar() {
    const datos = await llamar('/api/admin/usuarios');
    usuarios = datos.usuarios;
    if (!roles.length) {
      roles = datos.roles;
      opciones($('f-rol'), true);
      opciones($('d-rol'), false);
      opciones($('n-rol'), false);
    }
    if (sel) sel = usuarios.find((u) => u.id === sel.id) || null;
    pintarTabla();
    pintarDetalle();
    cargarAuditoria();
  }

  async function cargarAuditoria() {
    try {
      const datos = await llamar('/api/admin/auditoria');
      const caja = $('aud');
      caja.replaceChildren();
      if (!datos.eventos.length) { caja.textContent = 'Sin acciones registradas.'; return; }
      datos.eventos.forEach((e) => {
        const linea = document.createElement('div');
        linea.textContent = e.fecha.replace('T', ' ') + ' · ' + e.actor + ' · ' + e.accion + (e.cuenta ? ' · ' + e.cuenta : '');
        caja.appendChild(linea);
      });
    } catch (e) { /* la auditoría es complementaria */ }
  }

  async function accion(fn) {
    mensaje('');
    try { await fn(); } catch (e) { mensaje(e.message); }
  }

  $('generar').addEventListener('click', () => accion(async () => {
    const datos = await llamar('/api/admin/usuarios/' + sel.id + '/restablecer', { horas: Number($('horas').value) });
    mostrarTemporal(datos);
    await cargar();
  }));

  $('desbloquear').addEventListener('click', () => accion(async () => {
    await llamar('/api/admin/usuarios/' + sel.id + '/desbloquear', {});
    await cargar();
  }));

  $('d-rol').addEventListener('change', () => accion(async () => {
    try { await llamar('/api/admin/usuarios/' + sel.id + '/rol', { rol: $('d-rol').value }); }
    finally { await cargar(); }
  }));

  $('activar').addEventListener('click', () => accion(async () => {
    const activar = sel.estado === 'Desactivada';
    if (!activar && !confirm('¿Desactivar la cuenta de ' + sel.nombre + '? No va a poder ingresar.')) return;
    await llamar('/api/admin/usuarios/' + sel.id + '/activo', { activo: activar });
    await cargar();
  }));

  /* Copia la clave y avisa si funcionó. Si el navegador bloquea el portapapeles
     (p. ej. http que no es 127.0.0.1/localhost), deja la clave seleccionada para copiarla a mano. */
  $('copiar').addEventListener('click', async () => {
    const clave = $('t-clave').textContent;
    let ok = false;
    try { await navigator.clipboard.writeText(clave); ok = true; } catch (e) { /* sin permiso */ }
    if (!ok) {
      const rango = document.createRange();
      rango.selectNodeContents($('t-clave'));
      const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(rango);
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    }
    $('copiar').textContent = ok ? 'Copiada ✓' : 'Copiala a mano (Ctrl+C)';
    setTimeout(() => { $('copiar').textContent = 'Copiar'; }, 2500);
  });
  $('listo').addEventListener('click', ocultarTemporal);

  $('nuevo').addEventListener('click', () => { $('dlg-msg').textContent = ''; $('f-nuevo').reset(); $('dlg').showModal(); });
  $('cancelar').addEventListener('click', () => $('dlg').close());
  $('f-nuevo').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const datos = Object.fromEntries(new FormData(ev.target));
    try {
      const r = await llamar('/api/admin/usuarios', datos);
      $('dlg').close();
      await cargar();
      sel = usuarios.find((u) => u.usuario === datos.usuario.trim()) || null;
      pintarTabla();
      pintarDetalle();
      mostrarTemporal(r);
    } catch (e) { $('dlg-msg').textContent = e.message; }
  });

  ['q', 'f-rol', 'f-estado'].forEach((id) => $(id).addEventListener('input', pintarTabla));

  async function salir() {
    try { await api.logout(); } catch (e) { /* igual vuelve al ingreso */ }
    location.href = 'index.html';
  }

  (async function iniciar() {
    if (!api.MODO_REAL) { $('sinServidor').hidden = false; $('chipSim').hidden = false; $('nuevo').disabled = true; return; }
    const u = await api.sesion();
    if (!u) { location.href = 'index.html'; return; }
    if (u.debeCambiar) { location.href = 'cambiar_password.html'; return; }
    if (u.rol !== 'admin') { location.href = 'formulario.html'; return; }
    const chip = $('userChip');
    chip.hidden = false;
    const punto = document.createElement('span');
    punto.className = 'dot';
    const salirBtn = document.createElement('button');
    salirBtn.type = 'button';
    salirBtn.textContent = 'Salir';
    salirBtn.addEventListener('click', salir);
    chip.title = u.nom;
    chip.append(punto, 'Sesión: ' + u.u, salirBtn);
    cargar().catch((e) => mensaje(e.message));
  })();
})();
