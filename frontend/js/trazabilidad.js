/* frontend/js/trazabilidad.js · Registro de cada episodio de triage (trazabilidad).
 *
 * Se carga DESPUÉS de formulario.js y medgemma.js. Registra en /api/traza/evento:
 *   inicio · datos revisados (con las correcciones a la IA) · prioridad mostrada · discriminadores
 *   confirmados · decisión del profesional · cambios de modo IA/sin IA.
 * La extracción, la sugerencia y el chat los registra el backend (las rutas de IA reciben "traza").
 * Además agrega el botón "Ver constancia" y el acceso a "Auditoría".
 * Si el registro falla, la atención sigue igual (nunca bloquea la pantalla).
 */
(function () {
  'use strict';
  const $id = id => document.getElementById(id);
  const actual = { id: null, ep: null, decidido: false, ultimaPrioridad: null };

  function usuario() {
    const u = (typeof st !== 'undefined' && st.user) || {};
    return u.usuario || u.user || u.nom || u.nombre || '';
  }
  function modo() {
    const c = $id('ollama');
    return c && /medgemma|MedGemma/.test(c.textContent) ? 'con IA' : 'sin IA';
  }

  /* Un episodio = un paciente. Se abre uno nuevo si cambió el código de episodio ("Nuevo caso")
     o si ya hubo una decisión y empieza otro relato. */
  function asegurar(nuevoRelato) {
    const ep = (typeof st !== 'undefined' && st.ep) || 'EP';
    if (!actual.id || actual.ep !== ep || (nuevoRelato && actual.decidido)) {
      actual.id = ep + '-' + Date.now().toString(36).toUpperCase();
      actual.ep = ep; actual.decidido = false; actual.ultimaPrioridad = null;
      enviar('inicio', { modo: modo() });
    }
    return actual.id;
  }

  function enviar(tipo, datos) {
    if (!actual.id) return;
    try {
      fetch('/api/traza/evento', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
        body: JSON.stringify({ episodio: actual.id, ep: actual.ep, usuario: usuario(), tipo, datos: datos || {} })
      }).catch(e => console.warn('[Trazabilidad]', e.message));
    } catch (e) { console.warn('[Trazabilidad]', e.message); }
  }

  /* API para medgemma.js: los pedidos a la IA llevan el episodio para que el backend los registre */
  window.HRRGTraza = {
    paraPedido(nuevoRelato) { asegurar(nuevoRelato); return { id: actual.id, ep: actual.ep, usuario: usuario() }; },
    evento(tipo, datos, nuevoRelato) { asegurar(nuevoRelato); enviar(tipo, datos); },
    id: () => actual.id
  };

  /* ---------- Datos revisados: al pasar a la pantalla 3 ---------- */
  const BANDERAS = { br_sangrado: 'Sangrado evidente', br_convulsion: 'Convulsión activa',
                     br_disnea: 'Dificultad para respirar', br_trauma: 'Mecanismo de trauma' };
  function datosRevisados() {
    const r = st.rev, datos = {}, correcciones = [];
    Object.entries(r).forEach(([k, v]) => { if (v !== '' && v != null && v !== false && !k.startsWith('br_')) datos[k] = v; });
    (typeof FI !== 'undefined' ? FI : []).forEach(f => {
      if (f.src === 'med' || f.t === 'calc' || f.ia == null) return;      // solo lo que propuso la IA
      const final = f.t === 'chk' ? !!r[f.k] : String(r[f.k] ?? '');
      const deIA = f.t === 'chk' ? !!f.ia : String(f.ia);
      if (final !== deIA) correcciones.push({ campo: f.l, ia: f.t === 'chk' ? (deIA ? 'Sí' : 'No') : deIA,
                                               final: f.t === 'chk' ? (final ? 'Sí' : 'No') : final });
    });
    return { datos, banderas: Object.keys(BANDERAS).filter(k => r[k]).map(k => BANDERAS[k]), correcciones, modo: modo() };
  }

  const goAnterior = window.go;
  window.go = function (s) {
    const out = goAnterior.apply(this, arguments);
    if (s === 'resumen' && typeof st !== 'undefined' && st.user) {
      asegurar(false);
      enviar('datos_revisados', datosRevisados());
    }
    return out;
  };

  /* ---------- Prioridad mostrada: cada vez que cambia el color o sus motivos ---------- */
  const renderAnterior = window.renderCard;
  window.renderCard = function () {
    const out = renderAnterior.apply(this, arguments);
    try {
      if (st.screen !== 'resumen' || st.manual) return out;
      const ceja = (document.querySelector('#triageCard .eyebrow') || {}).textContent || '';
      if (/Consultando/.test(ceja)) return out;                           // todavía no respondió MedGemma
      let datos;
      if (st.insuf) datos = { insuficiente: true, modo: modo() };
      else {
        const c = typeof calcSug === 'function' ? calcSug() : { R: [], C: [] };
        const motivos = [...document.querySelectorAll('#tcWhy li')].map(li => {
          const tag = li.querySelector('.src'); const t = li.textContent.trim();
          return tag ? '[' + tag.textContent.trim() + '] ' + t.slice(tag.textContent.trim().length).trim() : t;
        });
        const iaLinea = motivos.find(m => /MedGemma estima/.test(m)) || '';
        const origen = $id('tcOrigin') ? [...$id('tcOrigin').childNodes].map(n => n.textContent.trim())
          .filter(t => t && !/^Reglas provisorias$/i.test(t)).join(' ') : '';
        datos = { color: LEVELS[SUG][0], color_ia: (iaLinea.match(/estima (\w+)/) || [])[1] || '',
                  origen, reglas: c.R.map(x => x.t), confirmados: c.C.map(x => x.t), motivos, modo: modo(),
                  fuente: ceja.replace(/\s*\d+\s*$/, '').trim() };
      }
      const clave = JSON.stringify(datos);
      if (clave !== actual.ultimaPrioridad) { actual.ultimaPrioridad = clave; asegurar(false); enviar('prioridad_mostrada', datos); }
    } catch (e) { console.warn('[Trazabilidad] prioridad', e.message); }
    return out;
  };

  /* ---------- Discriminadores confirmados con Sí/No ---------- */
  document.addEventListener('click', e => {
    const b = e.target.closest('.yn button[data-a]');
    if (!b) return;
    const clave = b.closest('.yn').dataset.key || '';
    const key = clave.split('|');
    setTimeout(() => enviar('discriminador', { nivel: LEVELS[+key[0]] ? LEVELS[+key[0]][0] : key[0], texto: key[1] || '',
      respuesta: (st.disc && st.disc[clave]) || 'sin respuesta' }), 0);
  });

  /* ---------- Decisión del profesional (aceptar, modificar, rechazar o manual) ---------- */
  const commitAnterior = window.commit;
  window.commit = function (lv) {
    const out = commitAnterior.apply(this, arguments);
    if (lv == null) return out;
    asegurar(false);
    const motivo = $id('motivo') ? $id('motivo').value : '';
    enviar('decision', {
      decision: st.manual ? 'manual' : (st.decision || 'aceptar'),
      color_final: LEVELS[lv][0], color_sugerido: st.manual ? '' : LEVELS[SUG][0],
      motivo: st.manual ? 'Clasificación manual' : motivo,
      menor_prioridad_que_sugerida: !st.manual && lv > SUG, modo: modo()
    });
    actual.decidido = true;
    mostrarConstancia();
    return out;
  };

  /* ---------- Botón "Ver constancia" ---------- */
  function boton(idDespues) {
    const ref = $id(idDespues);
    if (!ref) return null;
    let b = $id('btnConst_' + idDespues);
    if (!b) {
      b = document.createElement('button');
      b.type = 'button'; b.className = 'btn'; b.id = 'btnConst_' + idDespues; b.style.marginTop = '8px';
      b.textContent = 'Ver constancia (PDF)';
      b.addEventListener('click', () => { if (actual.id) window.open('/api/traza/constancia/' + encodeURIComponent(actual.id), '_blank'); });
      ref.insertAdjacentElement('afterend', b);
    }
    return b;
  }
  function mostrarConstancia() {
    setTimeout(() => ['okMsg', 'mOk'].forEach(id => {
      const ref = $id(id), b = boton(id);
      if (b) b.hidden = !(ref && !ref.hidden && actual.decidido);
    }), 50);
  }
  // al cambiar de caso, se ocultan
  const resetAnterior = window.resetDecision;
  if (typeof resetAnterior === 'function') {
    window.resetDecision = function () { const o = resetAnterior.apply(this, arguments); mostrarConstancia(); return o; };
  }

  /* ---------- Cambio de modo IA / sin IA ---------- */
  const chip = $id('ollama');
  if (chip) chip.addEventListener('click', () => setTimeout(() => { if (actual.id) enviar('modo', { modo: modo() }); }, 2500));

  /* ---------- Acceso a Auditoría en el encabezado ---------- */
  const chips = document.querySelector('.chips');
  if (chips && !$id('linkAuditoria')) {
    const a = document.createElement('a');
    a.id = 'linkAuditoria'; a.className = 'chip'; a.href = 'auditoria.html'; a.target = '_blank';
    a.textContent = 'Auditoría'; a.title = 'Registro de episodios, constancias y exportación CSV';
    chips.appendChild(a);
  }
})();
