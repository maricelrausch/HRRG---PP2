/* frontend/js/auditoria.js · Lista de episodios registrados, línea de tiempo, constancia y CSV. */
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const COLORES = { ROJO: '#c62828', NARANJA: '#ef6c00', AMARILLO: '#f9a825', VERDE: '#2e7d32', AZUL: '#1565c0' };
  const DECISION = { aceptar: 'Aceptó', modificar: 'Modificó', rechazar: 'Rechazó', manual: 'Manual' };
  let todos = [];

  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const chip = c => COLORES[c] ? `<span class="chip" style="background:${COLORES[c]}">${esc(c)}</span>` : '<span class="q">—</span>';
  const hora = iso => { try { return new Date(iso).toLocaleString('es-AR'); } catch (e) { return iso || ''; } };
  const sn = v => v === 'sí' ? '<span class="si">sí</span>' : v === 'no' ? '<span class="no">no</span>' : '<span class="q">—</span>';

  function kpis(lista) {
    const dec = lista.filter(e => e.decision);
    const conIA = dec.filter(e => e.color_ia);
    const acuerdo = conIA.filter(e => e.concordancia_ia === 'sí').length;
    const acept = dec.filter(e => e.concordancia_sugerencia === 'sí').length;
    const alter = lista.filter(e => e.integridad !== 'OK').length;
    const bloq = lista.reduce((a, e) => a + (e.chat_bloqueadas || 0), 0);
    const pct = (a, b) => b ? Math.round(100 * a / b) + '%' : '—';
    $('kpis').innerHTML = [
      [lista.length, 'episodios registrados'],
      [dec.length, 'con decisión del profesional'],
      [pct(acuerdo, conIA.length), `MedGemma coincidió con la decisión final (${acuerdo}/${conIA.length})`],
      [pct(acept, dec.length), `se mantuvo el color sugerido (${acept}/${dec.length})`],
      [bloq, 'respuestas del chat bloqueadas por seguridad'],
      [alter, alter ? 'episodios con registro ALTERADO' : 'registros alterados']
    ].map(([n, t]) => `<div class="kpi"><b>${esc(n)}</b><span>${esc(t)}</span></div>`).join('');
  }

  function pintar() {
    const f = $('buscar').value.trim().toLowerCase();
    const lista = todos.filter(e => !f || JSON.stringify(e).toLowerCase().includes(f));
    kpis(lista);
    $('filas').innerHTML = lista.length ? lista.map(e => `<tr class="fila" data-id="${esc(e.episodio)}">
      <td>${esc(hora(e.inicio))}</td><td>${esc(e.codigo)}</td><td>${esc(e.usuario)}</td><td>${esc(e.modo || '—')}</td>
      <td>${chip(e.color_ia)}</td><td>${chip(e.color_mostrado)}</td><td>${chip(e.color_final)}</td>
      <td>${esc(DECISION[e.decision] || 'pendiente')}</td><td>${sn(e.concordancia_ia)}</td>
      <td>${esc(e.correcciones)}</td><td>${esc(e.consultas_chat)}${e.chat_bloqueadas ? ' (' + esc(e.chat_bloqueadas) + ' bloq.)' : ''}</td>
      <td>${e.integridad === 'OK' ? '<span class="si">íntegro</span>' : '<span class="no">ALTERADO</span>'}</td>
      <td><a class="btn" target="_blank" href="/api/traza/constancia/${encodeURIComponent(e.episodio)}">Constancia</a></td></tr>`).join('')
      : '<tr><td colspan="13" class="vacio">Todavía no hay episodios registrados. Hacé un triage completo y volvé.</td></tr>';
  }

  async function cargar() {
    try {
      const r = await fetch('/api/traza/episodios', { credentials: 'same-origin' });
      todos = (await r.json()).episodios || [];
    } catch (e) {
      todos = [];
      $('filas').innerHTML = '<tr><td colspan="13" class="vacio">No se pudo leer el registro. ¿Está corriendo Flask?</td></tr>';
      return;
    }
    pintar();
  }

  async function detalle(id) {
    document.querySelectorAll('tr.fila').forEach(tr => tr.classList.toggle('sel', tr.dataset.id === id));
    const d = $('detalle');
    d.hidden = false; d.innerHTML = 'Cargando…';
    const j = await fetch('/api/traza/episodio/' + encodeURIComponent(id), { credentials: 'same-origin' }).then(r => r.json());
    const r = j.resumen || {};
    d.innerHTML = `<h2>${esc(r.codigo)} · <span class="q">${esc(r.episodio)}</span></h2>
      <div class="barra"><a class="btn prim" target="_blank" href="/api/traza/constancia/${encodeURIComponent(id)}">Ver constancia (PDF)</a>
      <span>Integridad: ${r.integridad === 'OK' ? '<span class="si">íntegro</span>' : '<span class="no">ALTERADO</span>'}</span></div>
      ${(j.eventos || []).map(e => `<div class="ev"><div class="t">${esc(e.nombre)}
        ${e.hash_ok === false ? ' <span class="no">· alterado</span>' : ''}</div>
        <div class="h">${esc(hora(e.cuando))} · ${esc(e.usuario)}</div>
        <pre>${esc(JSON.stringify(e.datos, null, 2))}</pre></div>`).join('')}`;
    d.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  $('filas').addEventListener('click', e => {
    if (e.target.closest('a')) return;
    const tr = e.target.closest('tr.fila');
    if (tr) detalle(tr.dataset.id);
  });
  $('buscar').addEventListener('input', pintar);
  $('recargar').addEventListener('click', cargar);
  cargar();
})();
