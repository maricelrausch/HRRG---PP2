/* A02 · Login SIMULADO para la demo.
   No es autenticación real: no consulta al servidor y la contraseña está fija.
   El login real (A07) va a usar /api/login, /api/sesion y /api/logout de Flask (D04). */
(function () {
  const USERS = {
    enfermeria: { nom: 'Enfermería', rol: 'triage' },
    medico: { nom: 'Médico/a de guardia', rol: 'triage' },
    auditor: { nom: 'Calidad', rol: 'auditor' }
  };
  const CLAVE_DEMO = 'demo';
  const form = document.getElementById('loginForm');
  const err = document.getElementById('loginErr');

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    const u = document.getElementById('lgUser').value.trim().toLowerCase();
    const p = document.getElementById('lgPass').value;
    if (!USERS[u] || p !== CLAVE_DEMO) {
      err.hidden = false;
      document.getElementById('lgPass').value = '';
      return;
    }
    err.hidden = true;
    try {
      sessionStorage.setItem('hrrg_demo_user', JSON.stringify({ u: u, nom: USERS[u].nom, rol: USERS[u].rol }));
    } catch (e2) { /* navegador sin almacenamiento: la demo no puede seguir */ }
    location.href = 'formulario.html';
  });
})();
