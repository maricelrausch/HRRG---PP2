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
  /* [Propuesta Barby 28/10] Consultas automáticas (listas que se actualizan solas): llevan el
     encabezado X-HRRG-Auto: 1, no muestran el indicador de carga y NO cuentan como actividad para
     el cierre de sesión por inactividad. Se usan con TriageAPI.enSegundoPlano(() => …). */
  let enAuto = 0;
  function enSegundoPlano(fn) {
    enAuto++;
    try { return fn(); } finally { enAuto--; }
  }
  if (MODO_REAL && root.fetch && !root.fetch.__hrrgCarga) {
    const fetchOriginal = root.fetch.bind(root);
    const conIndicador = function (recurso, opciones) {
      const url = typeof recurso === 'string' ? recurso : (recurso && recurso.url) || '';
      const propio = /^\/(api|upload|chat)\b/.test(url) || url.indexOf(location.origin + '/api') === 0;
      if (!propio) return fetchOriginal(recurso, opciones);
      if (enAuto > 0) {
        opciones = Object.assign({}, opciones);
        const h = new Headers(opciones.headers || {});
        h.set('X-HRRG-Auto', '1');
        opciones.headers = h;
        return fetchOriginal(recurso, opciones).then(revisarVencida);
      }
      empezarCarga();
      return fetchOriginal(recurso, opciones).then(revisarVencida).finally(terminarCarga);
    };
    conIndicador.__hrrgCarga = true;
    root.fetch = conIndicador;
  }

  /* Si el servidor cerró la sesión por inactividad, se recuerda para avisarlo en el ingreso. */
  function revisarVencida(r) {
    if (r.status === 401) {
      r.clone().json().then(function (j) {
        if (j && j.codigo === 'SESION_VENCIDA') { try { sessionStorage.setItem('hrrg_sesion_vencida', '1'); } catch (e) {} }
      }).catch(function () {});
    }
    return r;
  }

  /* ===== Cierre de sesión por inactividad (pedido 28/10) =====
     El servidor cierra la sesión si pasan N minutos (15 por defecto) sin uso. Acá se cuenta la
     actividad real de la persona (teclado, mouse, toques) en TODAS las pestañas abiertas del sistema:
     - con actividad, cada 30 s como máximo se avisa al servidor (GET /api/sesion);
     - 1 minuto antes del cierre aparece un aviso con cuenta regresiva y el botón "Seguir conectado";
     - al vencer, se cierra la sesión y se vuelve al ingreso con el aviso.
     Las listas que se actualizan solas no cuentan como actividad (ver enSegundoPlano). */
  const CLAVE_ACT = 'hrrg_ultima_actividad';
  let vigilando = false;
  function vigilarInactividad(minutos) {
    if (vigilando || !MODO_REAL || !minutos) return;
    vigilando = true;
    const limite = minutos * 60000 - 45000;      // un margen para cerrar antes que el servidor
    const avisoDesde = limite - 60000;
    let ultimoPing = Date.now(), barra = null, cerrando = false;
    const leer = () => { let v = 0; try { v = +localStorage.getItem(CLAVE_ACT) || 0; } catch (e) {} return v; };
    const guardar = t => { try { localStorage.setItem(CLAVE_ACT, String(t)); } catch (e) {} };
    let local = Date.now(); guardar(local);
    function actividad() {
      if (cerrando) return;
      const ahora = Date.now();
      if (ahora - local < 1000) return;          // los movimientos del mouse llegan de a cientos
      local = ahora; guardar(ahora);
      if (ahora - ultimoPing > 30000) { ultimoPing = ahora; pedir('/api/sesion', { method: 'GET', cache: 'no-store' }); }
      revisar();
    }
    function mostrarAviso(seg) {
      if (!barra) {
        barra = document.createElement('div');
        barra.className = 'aviso-inactividad';
        barra.setAttribute('role', 'alertdialog');
        barra.setAttribute('aria-live', 'assertive');
        /* Estilos en línea: funciona también en pantallas sin estilos.css (administración). */
        barra.style.cssText = 'position:fixed;left:50%;bottom:20px;transform:translateX(-50%);z-index:9999;' +
          'display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;max-width:calc(100% - 32px);' +
          'background:#1B2030;color:#fff;border-radius:12px;padding:14px 18px;box-shadow:0 8px 30px rgba(0,0,0,.35);font-size:15px';
        barra.innerHTML = '<span class="ai-txt"></span><button type="button" style="min-height:44px;padding:0 18px;border-radius:8px;' +
          'border:0;background:#fff;color:#1B2030;font:inherit;font-weight:600;cursor:pointer">Seguir conectado</button>';
        barra.querySelector('button').addEventListener('click', function () { ultimoPing = 0; local = 0; actividad(); });
        document.body.appendChild(barra);
      }
      barra.querySelector('.ai-txt').innerHTML = '<b>¿Seguís ahí?</b> Por seguridad, la sesión se cierra en <b>' + seg + ' s</b> si no hay actividad.';
      barra.hidden = false;
    }
    async function cerrar() {
      cerrando = true;
      try { sessionStorage.setItem('hrrg_sesion_vencida', '1'); } catch (e) {}
      try { await pedir('/api/logout', { method: 'POST', body: '{}' }); } catch (e) {}
      location.href = 'index.html';
    }
    function revisar() {
      if (cerrando) return;
      const quieto = Date.now() - Math.max(local, leer());
      if (quieto >= limite) return cerrar();
      if (quieto >= avisoDesde) mostrarAviso(Math.max(1, Math.ceil((limite - quieto) / 1000)));
      else if (barra) barra.hidden = true;
    }
    ['pointerdown', 'keydown', 'wheel', 'touchstart', 'mousemove', 'input'].forEach(function (ev) {
      document.addEventListener(ev, actividad, { passive: true, capture: true });
    });
    /* Otra pestaña del sistema registró actividad: se oculta el aviso acá también. */
    window.addEventListener('storage', function (e) { if (e.key === CLAVE_ACT) revisar(); });
    setInterval(revisar, 1000);
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

  if (!r.ok) return null;
  /* Todas las pantallas con sesión (menos el ingreso) vigilan la inactividad. */
  if (!/(^|\/)(index\.html)?$/.test(location.pathname)) vigilarInactividad(r.datos.inactividad_min || 15);
  return aUsuario(r.datos);
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
  /* codigoPaciente (opcional): solo las atenciones de ese paciente (búsqueda por DNI en el historial). */
  function listarCasos(limite, desplazamiento, rango, codigoPaciente) {
    return pedir('/api/demo/episodios?limite=' + (limite || 50) + '&desplazamiento=' + (desplazamiento || 0) + paramsRango(rango) +
      (codigoPaciente ? '&codigo_paciente=' + encodeURIComponent(codigoPaciente) : ''), { method: 'GET', cache: 'no-store' });
  }
  /* Exportación del historial de casos (auditor): Excel (.xlsx) o PDF. Devuelve el archivo como Blob. */
  /* Pide de nuevo la contraseña del auditor (va en el cuerpo, nunca en la URL). formato: 'excel' | 'pdf'. */
  /* extra = { dni }: un solo paciente (opcional). El archivo queda protegido con la misma contraseña. */
  async function exportarCasos(estado, rango, formato, password, extra) {
    try {
      const cuerpo = { password: password, formato: formato };
      if (extra && extra.dni) cuerpo.dni = extra.dni;
      if (estado) cuerpo.estado = estado;
      if (rango && rango.desde) cuerpo.desde = rango.desde;
      if (rango && rango.hasta) cuerpo.hasta = rango.hasta;
      const r = await fetch('/api/demo/episodios/exportar', { method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo) });
      if (!r.ok) { let m = 'error ' + r.status, c = null; try { const j = await r.json(); m = j.mensaje || m; c = j.codigo || null; } catch (e) {} return { ok: false, estado: r.status, codigo: c, mensaje: m }; }
      const nombre = ((r.headers.get('Content-Disposition') || '').match(/filename="([^"]+)"/) || [])[1] || ('casos_triage.' + (formato === 'pdf' ? 'pdf' : 'xlsx'));
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

  /* [Propuesta Barby 28/10] Cancelar un caso cargado por error (antes de la espera): queda ANULADO. */
  function anularEpisodio(episodio, motivo, versionEsperada) {
    return pedir('/api/demo/episodios/' + encodeURIComponent(episodio) + '/anular', { method: 'POST',
      body: JSON.stringify({ motivo: motivo, version_esperada: versionEsperada }) });
  }
  /* [Propuesta Barby 28/10] Reglas del hospital activas (las carga la Jefatura de Guardia). */
  function reglasActivas() {
    return pedir('/api/reglas/activas', { method: 'GET', cache: 'no-store' });
  }
  root.TriageAPI = { MODO_REAL: MODO_REAL, enSegundoPlano: enSegundoPlano, anularEpisodio: anularEpisodio, reglasActivas: reglasActivas, login: login, sesion: sesion, logout: logout, pedir: pedir, cambiarPassword: cambiarPassword,
    crearEpisodio: crearEpisodio, registrarMedicion: registrarMedicion, registrarDatosIngreso: registrarDatosIngreso, corregirMedicion: corregirMedicion, consultarEpisodio: consultarEpisodio,
    consultarEstado: consultarEstado, cambiarEstado: cambiarEstado, listarEspera: listarEspera,
    identificarPaciente: identificarPaciente, buscarPaciente: buscarPaciente, episodiosDePaciente: episodiosDePaciente, listarCasos: listarCasos, exportarCasos: exportarCasos, registrarDecision: registrarDecision };
})(typeof globalThis !== 'undefined' ? globalThis : this);
