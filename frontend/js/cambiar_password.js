/* frontend/js/cambiar_password.js · Cambio de contraseña propia.
   Se llega acá al ingresar con una clave temporal o con la contraseña vencida (90 días). */
(function () {
  'use strict';
  const api = window.TriageAPI;
  const $ = (id) => document.getElementById(id);
  const form = $('pwForm');
  const btn = form.querySelector('button[type="submit"]');

  function error(texto) {
    $('pwErr').querySelector('b').textContent = texto;
    $('pwErr').hidden = false;
  }

  const destino = (u) => (u.rol === 'admin' ? 'admin.html' : u.rol === 'jefatura' ? 'reglas.html' : 'formulario.html');

  (async function iniciar() {
    if (!api.MODO_REAL) { location.href = 'index.html'; return; }
    const u = await api.sesion();
    if (!u) { location.href = 'index.html'; return; }
    if (!u.debeCambiar) $('motivo').textContent = 'Elegí una contraseña nueva para tu cuenta.';
  })();

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    $('pwErr').hidden = true;
    const actual = $('pwActual').value;
    const nueva = $('pwNueva').value;
    if (!actual || !nueva) { error('Completá todos los campos.'); return; }
    if (nueva !== $('pwRepetir').value) { error('Las contraseñas nuevas no coinciden.'); return; }

    btn.disabled = true;
    btn.textContent = 'Guardando…';
    const r = await api.cambiarPassword(actual, nueva);
    btn.disabled = false;
    btn.textContent = 'Guardar contraseña';
    if (!r.ok) { error(r.datos.mensaje || 'No se pudo cambiar la contraseña.'); return; }

    form.reset();
    const u = await api.sesion();
    location.href = u ? destino(u) : 'index.html';
  });

  $('salir').addEventListener('click', async () => {
    try { await api.logout(); } catch (e) { /* igual vuelve al ingreso */ }
    location.href = 'index.html';
  });
})();
