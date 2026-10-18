/* frontend/dictado.js · Dictado de voz con Whisper local. Funciona en Chrome, Edge, Firefox y Safari.
 *
 * Reemplaza los DOS micrófonos simulados:
 *   - #mic      (Ingreso): agrega lo dictado al relato.
 *   - #chatMic  (chat "Consultar a la IA"): transcribe la pregunta y la envía.
 * Graba con MediaRecorder, manda el audio a /api/transcribir (Flask + faster-whisper).
 * Se carga DESPUÉS de formulario.js.
 */
(function () {
  'use strict';

  function avisar(m) {
    const h = document.getElementById('hint');
    if (h && !h.closest('[hidden]')) { h.textContent = m; h.classList.add('err'); }
    else alert(m);
  }

  async function transcribir(trozos, tipo) {
    const ext = tipo.includes('ogg') ? '.ogg' : tipo.includes('mp4') ? '.m4a' : '.webm';
    const fd = new FormData();
    fd.append('audio', new Blob(trozos, { type: tipo }), 'dictado' + ext);
    const r = await fetch('/api/transcribir', { method: 'POST', body: fd, credentials: 'same-origin' });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
    return (j.texto || '').trim();
  }

  /* Convierte un botón en grabador. pintar(modo) dibuja 'listo' | 'grabando' | 'procesando';
     alTexto(texto) recibe lo transcripto. */
  function grabador(id, pintar, alTexto) {
    const viejo = document.getElementById(id);
    if (!viejo) return;
    const b = viejo.cloneNode(true);           // el clon no trae el listener simulado
    viejo.replaceWith(b);
    let rec = null, trozos = [], flujo = null;

    const estado = modo => {
      b.setAttribute('aria-pressed', modo === 'grabando');
      b.classList.toggle('rec', modo === 'grabando');
      b.disabled = modo === 'procesando';
      pintar(b, modo);
    };

    async function empezar() {
      if (!navigator.mediaDevices || !window.MediaRecorder) {
        avisar('Este navegador no deja usar el micrófono. Abrí la app desde http://127.0.0.1:5000 o por HTTPS.');
        return;
      }
      try {
        flujo = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (e) {
        avisar('No se pudo usar el micrófono: ' + (e.name === 'NotAllowedError' ? 'permiso denegado.' : e.message));
        return;
      }
      trozos = [];
      rec = new MediaRecorder(flujo);
      rec.ondataavailable = e => { if (e.data.size) trozos.push(e.data); };
      rec.onstop = async () => {
        flujo.getTracks().forEach(t => t.stop());
        estado('procesando');
        try {
          const texto = await transcribir(trozos, rec.mimeType || 'audio/webm');
          if (texto) alTexto(texto);
          else avisar('No se entendió el audio. Probá de nuevo, más cerca del micrófono.');
        } catch (e) {
          avisar('Falló la transcripción: ' + e.message);
        } finally {
          estado('listo');
        }
      };
      rec.start();
      estado('grabando');
    }

    b.addEventListener('click', () => {
      if (rec && rec.state === 'recording') rec.stop(); else empezar();
    });
  }

  /* 1. Micrófono del Ingreso */
  const caso = document.getElementById('caso');
  grabador('mic',
    (b, modo) => {
      const t = document.getElementById('micTxt');
      if (t) t.innerHTML = modo === 'grabando' ? '<span class="pulse"></span> Escuchando… detener'
                         : modo === 'procesando' ? 'Transcribiendo…' : 'Dictar';
    },
    texto => {
      caso.value = (caso.value.trim() + ' ' + texto).trim();
      caso.dispatchEvent(new Event('input', { bubbles: true }));
    });

  /* 2. Micrófono del chat */
  const chatTxt = document.getElementById('chatTxt');
  grabador('chatMic',
    (b, modo) => {
      b.textContent = modo === 'grabando' ? '⏹' : modo === 'procesando' ? '…' : '🎤';
      b.title = modo === 'grabando' ? 'Detener y enviar' : 'Preguntar por voz';
      if (chatTxt && modo === 'grabando') chatTxt.value = 'Escuchando… tocá ⏹ para enviar';
      if (chatTxt && modo === 'procesando') chatTxt.value = 'Transcribiendo…';
    },
    texto => {
      if (chatTxt) chatTxt.value = '';
      if (typeof enviarChat === 'function') enviarChat(texto);
      else if (chatTxt) chatTxt.value = texto;
    });
})();
