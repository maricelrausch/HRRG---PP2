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

  // Si ya hay sesión abierta, pasa directo al formulario
  api.sesion().then(u => { if (u) location.href = 'formulario.html'; });

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
    location.href = 'formulario.html';
  });

  function mostrarError(msg) {
    err.querySelector('b').textContent = msg;
    err.hidden = false;
  }
})();
