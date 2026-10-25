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
    return u.rol === 'admin' ? 'admin.html' : 'formulario.html';
  }

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
    err.hidden = false;
  }
})();
