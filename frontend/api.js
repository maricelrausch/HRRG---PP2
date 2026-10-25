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

  /* ===== Indicador de carga (pedido 24/10) =====
     Cada consulta al backend (/api/…) muestra una barra arriba y un cartel "Consultando al servidor…".
     Aparece recién a los 250 ms (las consultas rápidas no parpadean) y, si pasa de 6 s, aclara que
     MedGemma puede tardar. Cubre todas las pantallas que cargan api.js, el chat y el dictado. */
  let enCurso = 0, tAparece = null, tLento = null, aviso = null;
  function avisoCarga() {
    if (!aviso && document.body) {
      aviso = document.createElement('div');
      aviso.className = 'carga-global';
      aviso.setAttribute('role', 'status');
      aviso.setAttribute('aria-live', 'polite');
      aviso.innerHTML = '<span class="carga-barra"></span><span class="carga-txt"></span>';
      document.body.appendChild(aviso);
    }
    return aviso;
  }
  function empezarCarga() {
    if (enCurso++ > 0) return;
    tAparece = setTimeout(function () {
      const a = avisoCarga(); if (!a) return;
      a.querySelector('.carga-txt').textContent = 'Consultando al servidor…';
      a.classList.add('on'); document.documentElement.classList.add('cargando');
      if (document.body) document.body.setAttribute('aria-busy', 'true');
    }, 250);
    tLento = setTimeout(function () {
      if (aviso) aviso.querySelector('.carga-txt').textContent = 'Sigue procesando… (MedGemma puede tardar uno o dos minutos)';
    }, 6000);
  }
  function terminarCarga() {
    if (--enCurso > 0) return;
    enCurso = 0; clearTimeout(tAparece); clearTimeout(tLento);
    if (aviso) aviso.classList.remove('on');
    document.documentElement.classList.remove('cargando');
    if (document.body) document.body.removeAttribute('aria-busy');
  }
  if (MODO_REAL && root.fetch && !root.fetch.__hrrgCarga) {
    const fetchOriginal = root.fetch.bind(root);
    const conIndicador = function (recurso, opciones) {
      const url = typeof recurso === 'string' ? recurso : (recurso && recurso.url) || '';
      const propio = /^\/(api|upload|chat)\b/.test(url) || url.indexOf(location.origin + '/api') === 0;
      if (!propio) return fetchOriginal(recurso, opciones);
      empezarCarga();
      return fetchOriginal(recurso, opciones).finally(terminarCarga);
    };
    conIndicador.__hrrgCarga = true;
    root.fetch = conIndicador;
  }

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
    debeCambiar: !!datos.debe_cambiar,
    modoExtraccion: datos.modo_extraccion || null
  };
}

  /* Episodios e historial (rutas de Maricel, modo demostración). Devuelven { ok, estado, datos }. */
  function crearEpisodio(codigoPaciente) {
    return pedir('/api/demo/episodios', { method: 'POST', body: JSON.stringify({ codigo_paciente: codigoPaciente }) });
  }
  /* Datos de ingreso revisados (edad, sexo y lo extraído del relato). Nunca el relato ni el DNI. */
  function registrarDatosIngreso(episodio, datos, origenExtraccion) {
    return pedir('/api/demo/episodios/' + encodeURIComponent(episodio) + '/datos-ingreso',
      { method: 'POST', body: JSON.stringify({ datos: datos, origen_extraccion: origenExtraccion || null }) });
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
  /* Busca un DNI ya identificado SIN crear paciente (ruta de Maricel). 404 = no existe.
     El DNI va en el cuerpo, nunca en la URL. */
  function buscarPaciente(dni) {
    return pedir('/api/demo/pacientes/buscar', { method: 'POST', body: JSON.stringify({ dni: dni }) });
  }
  /* Historial de casos (todos los episodios, del más nuevo al más viejo), de a páginas. */
  /* rango = { desde, hasta } en ISO con zona horaria (desde inclusive, hasta exclusivo); opcional. */
  function paramsRango(rango) {
    let q = '';
    if (rango && rango.desde) q += '&desde=' + encodeURIComponent(rango.desde);
    if (rango && rango.hasta) q += '&hasta=' + encodeURIComponent(rango.hasta);
    return q;
  }
  function listarCasos(limite, desplazamiento, rango) {
    return pedir('/api/demo/episodios?limite=' + (limite || 50) + '&desplazamiento=' + (desplazamiento || 0) + paramsRango(rango), { method: 'GET', cache: 'no-store' });
  }
  /* Exportación del historial de casos (auditor): CSV para Excel, sin DNI. Devuelve el archivo como Blob. */
  /* Pide de nuevo la contraseña del auditor (va en el cuerpo, nunca en la URL). formato: 'excel' | 'pdf'. */
  async function exportarCasos(estado, rango, formato, password) {
    try {
      const cuerpo = { password: password, formato: formato };
      if (estado) cuerpo.estado = estado;
      if (rango && rango.desde) cuerpo.desde = rango.desde;
      if (rango && rango.hasta) cuerpo.hasta = rango.hasta;
      const r = await fetch('/api/demo/episodios/exportar', { method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo) });
      if (!r.ok) { let m = 'error ' + r.status, c = null; try { const j = await r.json(); m = j.mensaje || m; c = j.codigo || null; } catch (e) {} return { ok: false, estado: r.status, codigo: c, mensaje: m }; }
      const nombre = ((r.headers.get('Content-Disposition') || '').match(/filename="([^"]+)"/) || [])[1] || ('casos_triage.' + (formato === 'pdf' ? 'pdf' : 'csv'));
      return { ok: true, blob: await r.blob(), nombre: nombre };
    } catch (e) { return { ok: false, estado: 0, mensaje: 'No se pudo conectar con el servidor.' }; }
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

  /* Cambio de la propia contraseña (clave temporal o vencida). Devuelve { ok, estado, datos }. */
  function cambiarPassword(actual, nueva) {
    return pedir('/api/cuenta/password', { method: 'POST', body: JSON.stringify({ actual: actual, nueva: nueva }) });
  }

  root.TriageAPI = { MODO_REAL: MODO_REAL, login: login, sesion: sesion, logout: logout, pedir: pedir, cambiarPassword: cambiarPassword,
    crearEpisodio: crearEpisodio, registrarMedicion: registrarMedicion, registrarDatosIngreso: registrarDatosIngreso, corregirMedicion: corregirMedicion, consultarEpisodio: consultarEpisodio,
    consultarEstado: consultarEstado, cambiarEstado: cambiarEstado, listarEspera: listarEspera,
    identificarPaciente: identificarPaciente, buscarPaciente: buscarPaciente, episodiosDePaciente: episodiosDePaciente, listarCasos: listarCasos, exportarCasos: exportarCasos, registrarDecision: registrarDecision };
})(typeof globalThis !== 'undefined' ? globalThis : this);
