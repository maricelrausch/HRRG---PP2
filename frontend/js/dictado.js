/* frontend/js/dictado.js · Dictado de voz con Whisper local, POR TROZOS (streaming).
 *
 * Reemplaza los DOS micrófonos simulados:
 *   - #mic      (Ingreso): agrega lo dictado al relato a medida que se habla.
 *   - #chatMic  (chat "Consultar a la IA"): transcribe la pregunta y la envía al detener.
 *
 * Cómo funciona:
 *   1. Captura el micrófono en crudo (Web Audio) y lo pasa a 16 kHz mono.
 *   2. Cuando detecta una pausa (o pasan 10 s), corta un trozo y lo manda a /api/transcribir
 *      como WAV, MIENTRAS la persona sigue hablando.
 *   3. El texto de cada trozo aparece apenas llega. Al tocar "detener" solo falta el último
 *      trozo, así que la espera es de 1 o 2 segundos en lugar de todo el audio.
 * Si el navegador no tiene Web Audio, graba todo junto como antes (MediaRecorder).
 * Se carga DESPUÉS de formulario.js.
 */
(function () {
  'use strict';

  const HZ = 16000;              // lo que espera Whisper
  const MARCO = 480;             // 30 ms a 16 kHz: unidad para medir volumen
  const MIN_TROZO = 4 * HZ;      // no cortar trozos más cortos que esto (pierden contexto)
  const MAX_TROZO = 12 * HZ;     // cortar sí o sí a los 12 s aunque no haya pausa
  const PAUSA = 0.6 * HZ;        // silencio que cuenta como pausa entre frases
  const ESPERA_MIC = 0.5 * HZ;   // el micrófono tarda en ajustar el volumen: se avisa
                                 // "Escuchando" recién cuando ya capta bien
  const MARGEN = 0.3 * HZ;       // silencio agregado al principio y al final de cada trozo:
                                 // sin él, Whisper suele comerse la primera sílaba

  function avisar(m) {
    const h = document.getElementById('hint');
    if (h && !h.closest('[hidden]')) { h.textContent = m; h.classList.add('err'); }
    else alert(m);
  }

  async function enviar(blob, nombre, previo) {
    const fd = new FormData();
    fd.append('audio', blob, nombre);
    if (previo) fd.append('previo', previo);
    const r = await fetch('/api/transcribir', { method: 'POST', body: fd, credentials: 'same-origin' });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || ('HTTP ' + r.status));
    return (j.texto || '').trim();
  }

  /* Float32 16 kHz -> WAV PCM 16 bits mono */
  function aWav(voz) {
    const muestras = new Float32Array(voz.length + 2 * MARGEN);
    muestras.set(voz, MARGEN);
    const buf = new ArrayBuffer(44 + muestras.length * 2), v = new DataView(buf);
    const txt = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    txt(0, 'RIFF'); v.setUint32(4, 36 + muestras.length * 2, true); txt(8, 'WAVE');
    txt(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, HZ, true); v.setUint32(28, HZ * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    txt(36, 'data'); v.setUint32(40, muestras.length * 2, true);
    for (let i = 0; i < muestras.length; i++) {
      const x = Math.max(-1, Math.min(1, muestras[i]));
      v.setInt16(44 + i * 2, x < 0 ? x * 0x8000 : x * 0x7fff, true);
    }
    return new Blob([buf], { type: 'audio/wav' });
  }

  /* Pasa de la frecuencia del micrófono (44.1/48 kHz) a 16 kHz promediando. */
  function bajarA16k(entrada, hzOrigen, estado) {
    const paso = hzOrigen / HZ, salida = [];
    let pos = estado.pos;                         // posición fraccional que quedó del bloque anterior
    while (pos + paso <= entrada.length) {
      const a = Math.max(0, Math.floor(pos)), b = Math.min(entrada.length, Math.floor(pos + paso));
      let s = 0;
      for (let i = a; i < b; i++) s += entrada[i];
      salida.push(b > a ? s / (b - a) : entrada[a]);
      pos += paso;
    }
    estado.pos = pos - entrada.length;
    return salida;
  }

  /* Captura cruda del micrófono. alBloque(Float32Array a 16 kHz) se llama ~cada 100 ms. */
  async function capturar(flujo, alBloque) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    if (ctx.state === 'suspended') await ctx.resume();   // algunos navegadores lo crean pausado
    const fuente = ctx.createMediaStreamSource(flujo);
    const est = { pos: 0 };
    const recibir = datos => alBloque(Float32Array.from(bajarA16k(datos, ctx.sampleRate, est)));
    let nodo;
    if (ctx.audioWorklet && window.AudioWorkletNode) {
      const codigo = `class T extends AudioWorkletProcessor{process(i){const c=i[0]&&i[0][0];
        if(c)this.port.postMessage(c.slice(0));return true}}registerProcessor('toma-audio',T);`;
      const url = URL.createObjectURL(new Blob([codigo], { type: 'application/javascript' }));
      await ctx.audioWorklet.addModule(url);
      URL.revokeObjectURL(url);
      nodo = new AudioWorkletNode(ctx, 'toma-audio');
      let acum = [];
      nodo.port.onmessage = e => {               // juntar bloques de 128 muestras en ~100 ms
        acum.push(e.data);
        if (acum.length >= Math.ceil(ctx.sampleRate / 1280)) {
          const n = acum.reduce((t, a) => t + a.length, 0), todo = new Float32Array(n);
          let o = 0; for (const a of acum) { todo.set(a, o); o += a.length; }
          acum = []; recibir(todo);
        }
      };
      fuente.connect(nodo);
    } else {                                     // navegadores viejos
      nodo = ctx.createScriptProcessor(4096, 1, 1);
      nodo.onaudioprocess = e => recibir(e.inputBuffer.getChannelData(0));
      fuente.connect(nodo); nodo.connect(ctx.destination);
    }
    return () => { try { fuente.disconnect(); nodo.disconnect(); } catch (_) {} ctx.close(); };
  }

  /* Corta el audio en trozos en las pausas y los transcribe en orden, uno por uno. */
  function cortador(alTexto, alError) {
    let actual = [], largo = 0, silencio = 0, hayVoz = false, piso = 0.003;
    let previo = '', cola = Promise.resolve(), pendientes = 0;

    function cerrar() {
      if (!largo) return;
      const muestras = new Float32Array(largo);
      let o = 0; for (const a of actual) { muestras.set(a, o); o += a.length; }
      const conVoz = hayVoz;
      actual = []; largo = 0; silencio = 0; hayVoz = false;
      if (!conVoz) return;                       // solo silencio: Whisper inventaría texto
      pendientes++;
      cola = cola.then(async () => {
        try {
          const t = await enviar(aWav(muestras), 'trozo.wav', previo);
          if (t) { previo = (previo + ' ' + t).slice(-400); alTexto(t); }
        } catch (e) { alError(e); }
        finally { pendientes--; }
      });
    }

    function bloque(b) {
      actual.push(b); largo += b.length;
      for (let i = 0; i + MARCO <= b.length; i += MARCO) {
        let s = 0; for (let j = i; j < i + MARCO; j++) s += b[j] * b[j];
        const rms = Math.sqrt(s / MARCO);
        const umbral = Math.max(0.008, piso * 3);
        if (rms < umbral) { silencio += MARCO; piso = piso * 0.95 + rms * 0.05; }
        else { silencio = 0; hayVoz = true; }
      }
      if ((largo >= MIN_TROZO && silencio >= PAUSA) || largo >= MAX_TROZO) cerrar();
    }

    return {
      bloque,
      terminar: () => { cerrar(); return cola; },
      get pendientes() { return pendientes; },
    };
  }

  /* Convierte un botón en grabador.
     pintar(b, modo): 'listo' | 'grabando' | 'procesando'
     alParcial(texto): cada trozo transcripto, apenas llega
     alFinal(textoCompleto): al terminar (vacío si no se entendió nada) */
  function grabador(id, pintar, alParcial, alFinal) {
    const viejo = document.getElementById(id);
    if (!viejo) return;
    const b = viejo.cloneNode(true);           // el clon no trae el listener simulado
    viejo.replaceWith(b);
    let grabando = false, detener = null;

    const estado = modo => {
      b.setAttribute('aria-pressed', modo === 'grabando');
      b.classList.toggle('rec', modo === 'grabando');
      b.disabled = modo === 'procesando' || modo === 'preparando';
      pintar(b, modo);
    };

    async function empezar() {
      if (!navigator.mediaDevices) {
        avisar('Este navegador no deja usar el micrófono. Abrí la app desde http://127.0.0.1:5000 o por HTTPS.');
        return;
      }
      let flujo;
      try {
        flujo = await navigator.mediaDevices.getUserMedia(
          { audio: { channelCount: 1, echoCancellation: true, autoGainControl: true,
                   noiseSuppression: false } });   // el supresor del navegador recorta el inicio de las palabras
      } catch (e) {
        avisar('No se pudo usar el micrófono: ' + (e.name === 'NotAllowedError' ? 'permiso denegado.' : e.message));
        return;
      }
      const partes = [];
      let fallo = null;
      const parcial = t => { partes.push(t); alParcial(t); };
      const error = e => { fallo = fallo || e; };
      const fin = () => {
        flujo.getTracks().forEach(t => t.stop());
        estado('listo');
        if (fallo && !partes.length) avisar('Falló la transcripción: ' + fallo.message);
        else if (!partes.length) avisar('No se entendió el audio. Probá de nuevo, más cerca del micrófono.');
        alFinal(partes.join(' ').trim());
      };

      if (window.AudioContext || window.webkitAudioContext) {
        const corte = cortador(parcial, error);
        let soltar, captado = 0, listo;
        const microListo = new Promise(r => { listo = r; });
        estado('preparando');
        const alBloque = blq => { captado += blq.length; if (captado >= ESPERA_MIC) listo(); corte.bloque(blq); };
        try {
          soltar = await capturar(flujo, alBloque);
          await Promise.race([microListo, new Promise(r => setTimeout(r, 2000))]);
        }
        catch (e) { flujo.getTracks().forEach(t => t.stop()); estado('listo'); avisar('No se pudo iniciar el audio: ' + e.message); return; }
        detener = async () => {
          soltar();
          estado('procesando');
          await corte.terminar();               // espera solo los trozos que faltan
          fin();
        };
      } else if (window.MediaRecorder) {          // respaldo: todo el audio junto al final
        const trozos = [], rec = new MediaRecorder(flujo);
        rec.ondataavailable = e => { if (e.data.size) trozos.push(e.data); };
        rec.onstop = async () => {
          estado('procesando');
          const tipo = rec.mimeType || 'audio/webm';
          const ext = tipo.includes('ogg') ? '.ogg' : tipo.includes('mp4') ? '.m4a' : '.webm';
          try { const t = await enviar(new Blob(trozos, { type: tipo }), 'dictado' + ext); if (t) parcial(t); }
          catch (e) { error(e); }
          fin();
        };
        rec.start();
        detener = () => rec.stop();
      } else {
        flujo.getTracks().forEach(t => t.stop());
        avisar('Este navegador no permite grabar audio.');
        return;
      }
      grabando = true;
      estado('grabando');
    }

    b.addEventListener('click', async () => {
      if (grabando) { grabando = false; const d = detener; detener = null; await d(); }
      else empezar();
    });
  }

  /* 1. Micrófono del Ingreso: cada trozo se agrega al relato apenas se transcribe. */
  const caso = document.getElementById('caso');
  grabador('mic',
    (b, modo) => {
      const t = document.getElementById('micTxt');
      if (t) t.innerHTML = modo === 'grabando' ? '<span class="pulse"></span> Escuchando… detener'
                         : modo === 'procesando' ? 'Terminando…'
                         : modo === 'preparando' ? 'Preparando micrófono…' : 'Dictar';
    },
    texto => {
      if (!caso) return;
      caso.value = (caso.value.trim() + ' ' + texto).trim();
      caso.dispatchEvent(new Event('input', { bubbles: true }));
    },
    () => {});

  /* 2. Micrófono del chat: muestra lo que va entendiendo y envía la pregunta completa al detener. */
  const chatTxt = document.getElementById('chatTxt');
  let preguntaVoz = '';
  grabador('chatMic',
    (b, modo) => {
      b.textContent = modo === 'grabando' ? '⏹' : (modo === 'procesando' || modo === 'preparando') ? '…' : '🎤';
      b.title = modo === 'grabando' ? 'Detener y enviar' : 'Preguntar por voz';
      if (chatTxt && modo === 'grabando') { preguntaVoz = ''; chatTxt.value = 'Escuchando… tocá ⏹ para enviar'; }
    },
    texto => {
      preguntaVoz = (preguntaVoz + ' ' + texto).trim();
      if (chatTxt) chatTxt.value = preguntaVoz + ' …';
    },
    texto => {
      if (chatTxt) chatTxt.value = '';
      if (!texto) return;
      if (typeof enviarChat === 'function') enviarChat(texto);
      else if (chatTxt) chatTxt.value = texto;
    });
})();
