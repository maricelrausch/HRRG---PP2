/* frontend/login.js · Pantalla de ingreso (A02 + A07).
   La validación del usuario la hace api.js: contra Flask (modo real) o simulada (modo demo). */
(function () {
  'use strict';
  const api = window.TriageAPI;
  const form = document.getElementById('loginForm');
  const err = document.getElementById('loginErr');
  const btn = form.querySelector('button[type="submit"]');

  // Carteles según el modo
  document.querySelectorAll('[data-modo]').forEach(el => {
    el.hidden = el.dataset.modo !== (api.MODO_REAL ? 'real' : 'demo');
  });

  /* A dónde va cada perfil: cambio de contraseña pendiente, administración o formulario. */
  function destino(u) {
    if (u.debeCambiar) return 'cambiar_password.html';
    if (u.rol === 'jefatura') return 'reglas.html';
    return u.rol === 'admin' ? 'admin.html' : 'formulario.html';
  }

  /* [Barby 28/10] Aviso cuando la sesión se cerró por inactividad. */
  try {
    if (sessionStorage.getItem('hrrg_sesion_vencida')) {
      sessionStorage.removeItem('hrrg_sesion_vencida');
      mostrarError('La sesión se cerró por inactividad.');
      err.querySelector('span').textContent = 'Por seguridad, se cierra sola después de 15 minutos sin uso. Volvé a ingresar.';
    }
  } catch (e) {}

  // Si ya hay sesión abierta, pasa directo a su pantalla
  api.sesion().then(u => { if (u) location.href = destino(u); });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const usuario = document.getElementById('lgUser').value;
    const password = document.getElementById('lgPass').value;
    if (!usuario.trim() || !password) { mostrarError('Completá usuario y contraseña.'); return; }
    btn.disabled = true; btn.textContent = 'Ingresando…';
    const r = await api.login(usuario, password);
    btn.disabled = false; btn.textContent = 'Ingresar';
    if (!r.ok) { mostrarError(r.mensaje); document.getElementById('lgPass').value = ''; return; }
    err.hidden = true;
    location.href = destino(r.usuario);
  });

  function mostrarError(msg) {
    err.querySelector('b').textContent = msg;
    err.querySelector('span').textContent = 'Revisá los datos e intentá de nuevo.';
    err.hidden = false;
  }
})();
