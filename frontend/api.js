/* frontend/api.js · Comunicación con el backend Flask (A07).
 *
 * Dos modos, según cómo se abre la app:
 *   - Servida por Flask (http://127.0.0.1:5000/index.html) -> MODO REAL: usa /api/login, /api/sesion y /api/logout.
 *   - Abierta con doble clic (file://...)                  -> MODO DEMO: login simulado, sin servidor (como en el A02).
 * Así la demo sigue funcionando sin red ni backend, y el login real no depende de variables del navegador.
 */
(function (root) {
  'use strict';

  /* Usa autenticación de Flask en HTTP/HTTPS y acceso simulado al abrir por file://.
     Esta configuración controla el login, no la extracción con IA. */
  const MODO_REAL =
    location.protocol === 'http:' || location.protocol === 'https:';

  const CLAVE_DEMO = 'hrrg_demo_user';
  const USUARIOS_DEMO = {
    enfermeria: { nom: 'Enfermería', rol: 'triage' },
    medico: { nom: 'Médico/a de guardia', rol: 'triage' },
    auditor: { nom: 'Calidad', rol: 'auditor' }
  };

  /* Llama a una ruta del backend. Devuelve { ok, estado, datos }; nunca tira error hacia afuera. */
  async function pedir(ruta, opciones) {
    try {
      const r = await fetch(ruta, Object.assign({
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }
      }, opciones || {}));
      let datos = {};
      try { datos = await r.json(); } catch (e) { /* respuesta sin JSON */ }
      return { ok: r.ok, estado: r.status, datos: datos };
    } catch (e) {
      return { ok: false, estado: 0, datos: { mensaje: 'No se pudo conectar con el servidor. Verificá que Flask esté corriendo.' } };
    }
  }

  function guardarDemo(u) { try { sessionStorage.setItem(CLAVE_DEMO, JSON.stringify(u)); } catch (e) {} }
  function leerDemo() { try { return JSON.parse(sessionStorage.getItem(CLAVE_DEMO) || 'null'); } catch (e) { return null; } }
  function borrarDemo() { try { sessionStorage.removeItem(CLAVE_DEMO); } catch (e) {} }

  /* Inicia sesión. Devuelve { ok, usuario, mensaje }. */
  async function login(usuario, password) {
    if (!MODO_REAL) {
      const u = (usuario || '').trim().toLowerCase();
      if (!USUARIOS_DEMO[u] || password !== 'demo') return { ok: false, mensaje: 'Usuario o contraseña incorrectos.' };
      const datos = { u: u, nom: USUARIOS_DEMO[u].nom, rol: USUARIOS_DEMO[u].rol, modo: 'demo' };
      guardarDemo(datos);
      return { ok: true, usuario: datos };
    }
    const r = await pedir('/api/login', { method: 'POST', body: JSON.stringify({ usuario: (usuario || '').trim(), password: password || '' }) });
    if (!r.ok) return { ok: false, mensaje: r.datos.mensaje || 'No se pudo iniciar sesión.' };
    const profesional = await sesion();

if (!profesional) {
  return {
    ok: false,
    mensaje: 'No se pudo obtener el perfil. Verificá que la cuenta tenga un rol asignado.'
  };
}

return { ok: true, usuario: profesional };
  }

  /* Consulta quién está logueado. Devuelve el usuario o null (sin sesión). */
 async function sesion() {
  if (!MODO_REAL) return leerDemo();

  const r = await pedir('/api/sesion', {
    method: 'GET',
    cache: 'no-store'
  });

  return r.ok ? aUsuario(r.datos) : null;
}

  /* Cierra sesión (en el servidor y en el navegador). */
  async function logout() {
  if (MODO_REAL) {
    const r = await pedir('/api/logout', {
      method: 'POST',
      body: '{}'
    });

    if (!r.ok) {
      throw new Error(
        r.datos.mensaje || 'No se pudo cerrar la sesión.'
      );
    }
  }

  borrarDemo();
}

  /* Nombre y perfil informados por el servidor. */
function aUsuario(datos) {
  return {
    u: datos.usuario,
    nom: datos.nombre,
    rol: datos.rol,
    modo: 'real',
    modoExtraccion: datos.modo_extraccion || null
  };
}

  /* Episodios e historial (rutas de Maricel, modo demostración). Devuelven { ok, estado, datos }. */
  function crearEpisodio(codigoPaciente) {
    return pedir('/api/demo/episodios', { method: 'POST', body: JSON.stringify({ codigo_paciente: codigoPaciente }) });
  }
  function registrarMedicion(episodio, medidoEn, valores) {
    return pedir('/api/demo/episodios/' + encodeURIComponent(episodio) + '/mediciones',
      { method: 'POST', body: JSON.stringify({ medido_en: medidoEn, valores: valores }) });
  }
  function corregirMedicion(episodio, eventoId, cambios, motivo) {
    return pedir('/api/demo/episodios/' + encodeURIComponent(episodio) + '/mediciones/' + eventoId + '/correcciones',
      { method: 'POST', body: JSON.stringify({ cambios: cambios, motivo: motivo }) });
  }
  function consultarEstado(episodio) {
    return pedir('/api/demo/episodios/' + encodeURIComponent(episodio) + '/estado', { method: 'GET', cache: 'no-store' });
  }
  function cambiarEstado(episodio, estado, versionEsperada) {
    return pedir('/api/demo/episodios/' + encodeURIComponent(episodio) + '/estado',
      { method: 'POST', body: JSON.stringify({ estado: estado, version_esperada: versionEsperada }) });
  }
  /* Paciente por DNI: el servidor devuelve un código interno (no repite el DNI). */
  function identificarPaciente(dni) {
    return pedir('/api/demo/pacientes/identificar', { method: 'POST', body: JSON.stringify({ dni: dni }) });
  }
  function episodiosDePaciente(codigoPaciente) {
    return pedir('/api/demo/episodios?codigo_paciente=' + encodeURIComponent(codigoPaciente) + '&limite=20', { method: 'GET', cache: 'no-store' });
  }
  function registrarDecision(episodio, decision, colorFinal, motivo, versionEsperada) {
    return pedir('/api/demo/episodios/' + encodeURIComponent(episodio) + '/decision', { method: 'POST',
      body: JSON.stringify({ decision: decision, color_final: colorFinal, motivo: motivo, version_esperada: versionEsperada }) });
  }
  function listarEspera() {
    return pedir('/api/demo/espera?limite=100', { method: 'GET', cache: 'no-store' });
  }
  function consultarEpisodio(episodio) {
    return pedir('/api/demo/episodios/' + encodeURIComponent(episodio), { method: 'GET', cache: 'no-store' });
  }

  root.TriageAPI = { MODO_REAL: MODO_REAL, login: login, sesion: sesion, logout: logout, pedir: pedir,
    crearEpisodio: crearEpisodio, registrarMedicion: registrarMedicion, corregirMedicion: corregirMedicion, consultarEpisodio: consultarEpisodio,
    consultarEstado: consultarEstado, cambiarEstado: cambiarEstado, listarEspera: listarEspera,
    identificarPaciente: identificarPaciente, episodiosDePaciente: episodiosDePaciente, registrarDecision: registrarDecision };
})(typeof globalThis !== 'undefined' ? globalThis : this);
