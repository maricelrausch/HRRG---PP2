/* frontend/js/chat_ia.js · Conecta el chat "Consultar a la IA" con MedGemma (Flask + Ollama, local).
 *
 * Se carga DESPUÉS de formulario.js. Solo reemplaza preguntarIA(); no toca extracción ni sugerencia.
 * Envía al servidor la pregunta, el caso revisado, el color en pantalla, los motivos que ve el
 * profesional, los datos que faltan y las últimas 4 preguntas del mismo episodio.
 * Si no hay servidor (doble clic en el HTML) o MedGemma no responde, usa la respuesta simulada.
 */
(function () {
  'use strict';

  const RUTA = '/api/ia/consulta';
  /* Pie de cada respuesta según de dónde salió (el servidor manda "tipo") */
  const PIE = {
    modelo: '(Respuesta de MedGemma local. La decisión es del profesional.)',
    modelo_filtrada: '(Respuesta de MedGemma local, recortada por seguridad. La decisión es del profesional.)',
    fija: '(Respuesta armada con los datos del caso. La decisión es del profesional.)',
    bloqueada: '(Límite de seguridad de la herramienta.)',
    sin_ia: '(MedGemma no disponible: respuesta armada con los datos del caso.)',
    sin_respuesta: '(MedGemma no generó una respuesta utilizable.)'
  };
  const SALUDO_SIM = '(Simulación. La decisión es del profesional.)';
  const SALUDO_IA = '(Asistente con MedGemma local. La decisión es del profesional.)';
  const enServidor = location.protocol === 'http:' || location.protocol === 'https:';
  const simulada = window.preguntarIA;          // la de formulario.js
  const chat = { historial: [], ep: null };

  function texto(el) { return el ? el.textContent.replace(/\s+/g, ' ').trim() : ''; }

  function colorEnPantalla() {
    if (st.insuf) return 'sin sugerencia (datos insuficientes)';
    return (typeof LEVELS !== 'undefined' && typeof SUG !== 'undefined') ? LEVELS[SUG][0] : '';
  }

  function motivos() {                          // lo que el profesional ve en "Por qué"
    return [...document.querySelectorAll('#tcWhy li')].map(li => {
      const tag = li.querySelector('.src');
      const t = texto(li);
      return tag ? '[' + texto(tag) + '] ' + t.slice(texto(tag).length).trim() : t;
    }).filter(Boolean);
  }

  function faltan() {
    try { return (typeof missing === 'function' && typeof ml === 'function') ? missing().map(ml) : []; }
    catch (e) { return []; }
  }

  function subir() {                            // recuadro "Pasaría a X si se cumple alguno"
    const box = document.getElementById('subir');
    if (!box || box.hidden) return '';
    const titulo = box.querySelector('h4');
    const items = [...box.querySelectorAll('li')].map(li => texto(li.querySelector('.q') || li)).filter(Boolean);
    return (titulo ? texto(titulo).replace(/·.*$/, '').trim() + ': ' : '') + [...new Set(items)].join('; ');
  }

  function origen() {
    const o = document.getElementById('tcOrigin');
    return o ? [...o.childNodes].map(n => n.textContent.trim()).filter(Boolean).join(' ') : '';
  }

  async function preguntarMedGemma(q) {
    if (chat.ep !== st.ep) { chat.historial = []; chat.ep = st.ep; }
    const caso = document.getElementById('caso');
    const r = await fetch(RUTA, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({
        pregunta: q, datos: st.rev, sugerencia: colorEnPantalla(),
        contexto: { motivos: motivos(), faltan: faltan(), subir: subir(), origen: origen() },
        historial: chat.historial.slice(-4),
        relato: caso ? caso.value : ''
      })
    });
    if (r.status === 401) { location.href = 'index.html'; throw new Error('sesión vencida'); }
    const j = await r.json().catch(() => ({}));
    if (!r.ok || !j.respuesta) throw new Error(j.mensaje || j.error || ('HTTP ' + r.status));
    chat.historial.push({ pregunta: q, respuesta: j.respuesta });
    return j.respuesta + '\n\n' + (PIE[j.tipo] || PIE.modelo);
  }

  /* El saludo de formulario.js dice "Simulación": con servidor se corrige al abrir el chat */
  const abrirOriginal = window.abrirChat;
  if (enServidor && typeof abrirOriginal === 'function') {
    window.abrirChat = function (on) {
      abrirOriginal(on);
      const primero = document.querySelector('#chatMsgs .msg.ia');
      if (on && primero && primero.textContent.includes(SALUDO_SIM))
        primero.textContent = primero.textContent.replace(SALUDO_SIM, SALUDO_IA);
    };
  }

    /* Usa simulación únicamente cuando el HTML se abre sin servidor.
     Con Flask, muestra un aviso si la consulta falla. */
  window.preguntarIA = async function (q) {
    if (!enServidor) return simulada(q);

    try {
      return await preguntarMedGemma(q);
    } catch (e) {
      console.warn('[Chat IA] Consulta no completada:', e.message);
      return 'No se pudo completar la consulta a la IA. Verificá tu sesión y la disponibilidad del servicio e intentá nuevamente.';
    }
  };
})();
