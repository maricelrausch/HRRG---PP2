/* frontend/formulario.js · Lógica común del formulario (A05).
   Antes estaba dentro de formulario.html. Usa validacion.js (C04) para los controles.
   Organización (23/10):
     formulario.js  → datos compartidos (st, F, LEVELS…), navegación, Ingreso, Medición, guardado,
                      resumen, sesión, imprimir y DNI.
     sugerencia.js  → tarjeta de sugerencia (A09): color simulado, "Por qué", decisión y chat.
     espera.js      → lista En espera y reevaluación (A10).
   Orden de carga en formulario.html: formulario.js → sugerencia.js → espera.js → js/dictado.js → js/chat_ia.js.
   La sesión arranca cuando ya se cargaron todos (DOMContentLoaded). */
const SPECS={
  login:{t:'Pantalla 0 · Acceso',items:[
    ['1','Usuario individual por profesional: cada sugerencia y decisión queda registrada con su usuario (auditoría, Cuestionario §6).'],
    ['2','Roles: Enfermería y Médico/a usan el triage; Auditoría solo consulta En espera y el registro.'],
    ['3','Credenciales locales y cifradas, sin nube (Ley 25.326). A futuro: credenciales del hospital.']],src:'Cuestionario HRRG §6 Trazabilidad · Clase docentes'},
  ingreso:{t:'Pantalla 1 · Ingreso',items:[
    ['1','Relato del paciente o acompañante, en sus palabras. Caso ficticio.'],
    ['P','Si detecta un DNI o teléfono en el relato, avisa y no lo envía a la IA (§4).'],
    ['M','Dictado por voz: transcribe al cuadro y se puede editar.'],
    ['2','No envía texto vacío. Mientras procesa, botón bloqueado.'],
    ['S','Indica de dónde sale la extracción: MedGemma en esta computadora (IA local) o la simulación con casos de ejemplo.']],src:'Cuestionario HRRG §2, §4 · A1, A2'},
  revision:{t:'Pantalla 2 · Medición',items:[
    ['1','Solo lo que se mide en el box. Nombre completo, unidad y referencia en cada campo. Enter pasa al siguiente.'],
    ['A','Aviso inmediato: fuera de lo normal (borde oscuro), crítico por regla de seguridad o valor imposible (rojo).'],
    ['2','Glasgow o estado de conciencia: con uno alcanza. PAM se calcula sola.'],
    ['3','Banderas rojas y antecedentes con un toque. Lo que mencionó el paciente ya viene marcado.'],
    ['4','Avisa faltantes, rangos y discordancias. Con 3 o más vitales sin medir no se emite prioridad (RF-10). “Clasificar sin IA” siempre disponible (§6).']],src:'Doc. técnico V1.1 · Cuestionario §2 · RNF-01'},
  resumen:{t:'Pantalla 3 · Sugerencia',items:[
    ['1','Color Manchester sugerido, grande (hoy: simulado con reglas de ejemplo).'],
    ['2','Por qué: explicación clínica comprensible. Agrupa las variables que van juntas y dice qué indican (p. ej. "SpO₂ 88 % y taquipnea: posible compromiso respiratorio"), marcadas REGLA, GUÍA o IA. Las reglas fijan un piso: la IA no puede sugerir menos (no downgrade).'],
    ['3','Aceptar con un toque. Modificar o Rechazar piden motivo.'],
    ['4','Corregir datos del relato: lo que extrajo la IA se puede corregir acá. La decisión final es del profesional.'],
    ['5','Reglas provisorias de ejemplo: los umbrales los aprueban Guardia y Enfermería.'],
    ['↑','Qué lo haría subir: muestra los discriminadores del nivel siguiente. Los que no se miden se confirman con Sí/No, recalculan al instante y quedan guardados en la decisión del servidor (triage guiado por discriminadores).']],src:'Doc. técnico §9 Motor híbrido · Cuestionario §2 · Clase docentes'},
  espera:{t:'Pantalla 4 · En espera',items:[
    ['1','Pacientes ya clasificados que esperan, ordenados por color y tiempo.'],
    ['2','Marca a quien superó el tiempo objetivo de su color (tiempos según guía HRRG).'],
    ['3','Reevaluar abre el mismo episodio con los datos anteriores. La tarjeta muestra antes → ahora y el registro guarda las dos versiones.'],
    ['4','Escalar a ROJO rápido, sin volver a cargar datos: solo se elige el motivo (y un detalle si hace falta), que queda registrado. La Guardia no depende de la IA (RNF-04).'],
    ['⏱','Reloj de reevaluación: cuenta regresiva según el tiempo objetivo de cada color; al vencerse parpadea y pide reevaluar.'],
    ['A','Auditoría (solo lectura): ve el DNI, el historial completo de cada episodio (datos de ingreso, mediciones, correcciones, decisiones y motivos) y, buscando por DNI, todas las atenciones del paciente, incluidas las finalizadas. Con "Historial de casos" ve todos los episodios (filtrables por estado y por fecha), el historial de cada uno y puede exportarlos a Excel o PDF sin DNI (vuelve a pedir su contraseña).']],src:'Doc. técnico V1.1 · Re-triage · Cuestionario §6'}
};
const LEVELS=[['ROJO','--m-rojo','#FFFFFF','Inmediato'],['NARANJA','--m-naranja','#1A1D26','Muy urgente · 10 min'],['AMARILLO','--m-amarillo','#1A1D26','Urgente · 60 min'],['VERDE','--m-verde','#FFFFFF','Normal · 120 min'],['AZUL','--m-azul','#FFFFFF','Solo asignación manual · criterio del HRRG a confirmar (p. ej. casos policiales o judiciales)']];
let SUG=2;
const DESC=['Inmediato · atención inmediata','Muy urgente · 10 min','Urgente · 60 min','Normal · 120 min','Asignación manual · criterio del HRRG a confirmar'];
const F=[
  {k:'edad',l:'Edad',u:'años',t:'num',hce:'58',min:0,max:120,req:1,box:'ident',ph:'años'},
  {k:'sexo',l:'Sexo',t:'sel',hce:'Femenino',opts:['Femenino','Masculino','No informado'],req:1,box:'ident'},
  {k:'motivo_categoria',l:'Categoría',t:'sel',ia:'Dolor abdominal',opts:['Dolor torácico','Dolor abdominal','Disnea','Trauma','Fiebre','Cefalea','Síntoma neurológico','Otro'],req:1,box:'relato',w:'half'},
  {k:'tiempo_evolucion_valor',l:'Desde hace',t:'num',ia:'6',min:0,max:10000,req:1,box:'relato'},
  {k:'tiempo_evolucion_unidad',l:'Unidad',t:'sel',ia:'horas',opts:['minutos','horas','días'],req:1,box:'relato'},
  {k:'motivo_consulta',l:'Motivo (resumen del relato)',t:'text',ia:'Dolor abdominal alto con náuseas',req:1,box:'relato',w:'full'},
  {k:'dolor_localizacion',l:'Dónde le duele',t:'text',ia:'Epigastrio (“acá arriba de la panza”)',req:1,box:'relato',w:'half'},
  {k:'sintomas_asociados',l:'Síntomas que refiere',t:'text',ia:'Náuseas, se siente afiebrada',box:'relato',w:'half'},
  {k:'dolor_caracteristicas',l:'Cómo es el dolor',t:'text',ia:null,box:'relato',w:'full',ph:'Opresivo, cólico, punzante… (si lo describe)'},
  {k:'ta_sistolica',l:'TA sistólica',u:'mmHg',t:'num',src:'med',min:50,max:260,req:1,box:'vitales'},
  {k:'ta_diastolica',l:'TA diastólica',u:'mmHg',t:'num',src:'med',min:20,max:160,req:1,box:'vitales'},
  {k:'frecuencia_cardiaca',l:'Frec. cardíaca',u:'lpm',t:'num',src:'med',min:20,max:250,req:1,box:'vitales'},
  {k:'frecuencia_respiratoria',l:'Frec. respiratoria',u:'rpm',t:'num',src:'med',min:4,max:60,req:1,box:'vitales'},
  {k:'saturacion_o2',l:'SpO₂',u:'%',t:'num',src:'med',min:50,max:100,req:1,box:'vitales'},
  {k:'temperatura',l:'Temperatura',u:'°C',t:'num',src:'med',min:30,max:43,req:1,box:'vitales'},
  {k:'glucemia',l:'Glucemia capilar',u:'mg/dL',t:'num',src:'med',min:20,max:800,box:'vitales'},
  {k:'pam',l:'PAM (calculada)',u:'mmHg',t:'calc',box:'vitales'},
  {k:'estado_conciencia',l:'Estado de conciencia',t:'sel',src:'med',opts:['','Alerta','Responde a la voz','Responde al dolor','No responde'],box:'dolor'},
  {k:'glasgow',l:'Glasgow',u:'3–15',t:'num',src:'med',min:3,max:15,box:'dolor'},
  {k:'dolor_intensidad',l:'Escala de dolor',u:'0–10',t:'num',src:'med',min:0,max:10,req:1,box:'dolor'},
  {k:'aspecto_general',l:'Aspecto general',t:'text',src:'med',box:'dolor',ph:'Pálida, sudorosa…'},
  {k:'br_sangrado',l:'Sangrado evidente',t:'chk',ia:false,box:'br'},
  {k:'br_convulsion',l:'Convulsión activa',t:'chk',ia:false,box:'br'},
  {k:'br_disnea',l:'Dificultad para respirar',t:'chk',ia:false,box:'br'},
  {k:'br_trauma',l:'Mecanismo de trauma',t:'chk',ia:false,box:'br'},
  {k:'ant_diabetes',l:'Diabetes',t:'chk',ia:true,box:'ant'},
  {k:'ant_cardio',l:'Cardiovascular',t:'chk',ia:false,box:'ant'},
  {k:'ant_resp',l:'Respiratorio',t:'chk',ia:false,box:'ant'},
  {k:'ant_anticoag',l:'Anticoagulación',t:'chk',ia:false,box:'ant'},
  {k:'ant_inmuno',l:'Inmunosupresión',t:'chk',ia:false,box:'ant'},
  {k:'ant_embarazo',l:'Embarazo',t:'chk',ia:false,box:'ant'},
  {k:'ant_medicacion',l:'Medicación crítica',t:'chk',ia:false,box:'ant'},
  {k:'alergias',l:'Alergias',t:'text',ia:null,box:'ant'},
  {k:'antecedentes_otros',l:'Otros',t:'text',ia:'Toma pastillas para la diabetes',box:'ant'}
];
const CORE=['ta_sistolica','frecuencia_cardiaca','frecuencia_respiratoria','saturacion_o2','temperatura'];
const DEMO={ta_sistolica:'130',ta_diastolica:'80',frecuencia_cardiaca:'98',frecuencia_respiratoria:'18',saturacion_o2:'97',temperatura:'37,8',glucemia:'210',estado_conciencia:'Alerta',dolor_intensidad:'7'};
const FI=F.filter(f=>f.t!=='calc');
const byK=k=>F.find(f=>f.k===k);
const ml=k=>k==='glasgow'?'Conciencia (Glasgow o estado)':byK(k).l;
/* Conserva los valores del ejemplo para la demo sin servidor. */
const ejemploOriginal = F.map(f => ({ia: f.ia, hce: f.hce}));
const base=f=>f.t==='chk'?f.ia:(f.ia??f.hce??'');
/* Al iniciar un caso con servidor, deja vacíos los datos no obtenidos aún. */
const init=()=>Object.fromEntries(FI.map(f=>[f.k,
  TriageAPI.MODO_REAL ? (f.t==='chk'?false:'') : base(f)]));
const st={user:null,disc:{},fast:false,screen:'ingreso',rev:init(),insuf:false,decision:null,level:null,ollama:true,ep:'EP-004812',prev:null,manual:false,mlv:null};
let epN=4812;
const $=s=>document.querySelector(s);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function go(s){
  if(s!=='resumen'&&$('#chat'))abrirChat(false);
  st.screen=s;
  if(!st.user){location.href='index.html';return}
  if(st.user.rol==='auditor'&&s!=='espera')s='espera';
  st.screen=s;
  ['ingreso','revision','resumen','espera'].forEach(x=>$('#s-'+x).hidden=x!==s);
  document.querySelectorAll('.tab').forEach(b=>b.setAttribute('aria-current',b.dataset.go===s?'page':'false'));
  document.querySelectorAll('#stepper span').forEach(sp=>sp.classList.toggle('on',sp.dataset.s===s));
  $('#stepper').hidden=s==='espera';
  const sp=SPECS[s];
  $('#specs').innerHTML='<div class="eyebrow">Especificaciones</div><h2>'+sp.t+'</h2><ol>'+sp.items.map(i=>'<li><span class="n">'+i[0]+'</span><span>'+i[1]+'</span></li>').join('')+'</ol><div class="src">Fuente: '+sp.src+'</div>';
  if(s==='revision'){$('#epCode').textContent=st.ep;$('#dniTag').textContent=st.dni?'DNI '+fmtDni(st.dni):'Sin DNI';$('#reBadge').hidden=!st.prev;if(st.prev)$('#reBadge').textContent='Reevaluación · antes '+LEVELS[st.prev.lv][0]+', hace '+fmtMin(st.prev.min);$('#demoWorse').hidden=!st.prev;$('#demoVitals').hidden=!!st.prev;renderForm();updOllama();setTimeout(()=>{const i=$('#r-ta_sistolica');i&&!i.value&&i.focus()},0)}
  if(s==='resumen')renderResumen();
  if(s==='espera'){renderWait();if(TriageAPI.MODO_REAL)cargarEspera().then(renderWait)}
  window.scrollTo({top:0});
}
document.addEventListener('click',e=>{const t=e.target.closest('[data-go]');if(t)go(t.dataset.go)});
$('#sp').addEventListener('change',e=>document.body.classList.toggle('nospecs',!e.target.checked));

/* Ingreso */
let micTimer=null;
$('#mic').addEventListener('click',()=>{
  const b=$('#mic'),on=b.getAttribute('aria-pressed')!=='true';
  b.setAttribute('aria-pressed',on);b.classList.toggle('rec',on);
  $('#micTxt').innerHTML=on?'<span class="pulse"></span> Escuchando… detener':'Dictar';
  if(on){micTimer=setTimeout(()=>{const t=$('#caso');t.value=(t.value.trim()+' Esta mañana vomité una vez.').trim();},1800);}
  else clearTimeout(micTimer);
});
$('#borrar').addEventListener('click',()=>{$('#caso').value='';$('#caso').focus()});
function showErr(code){
  const E={'422':['Escribí el texto del caso antes de extraer.','El cuadro está vacío.','422 · entrada_invalida'],
    '503':['No se pudo conectar con la IA local.','Verificá que Ollama esté corriendo. Podés seguir con el triage manual.','503 · ollama_no_disponible'],
    '504':['La IA tardó demasiado en responder.','Probá de nuevo en unos segundos. Tu texto se conservó.','504 · tiempo_agotado'],
    '502':['La respuesta de la IA no es válida.','No se muestran datos de esta respuesta. Probá de nuevo.','502 · salida_invalida']}[code];
  $('#errTitle').textContent=E[0];$('#errMsg').textContent=E[1];$('#errCode').textContent=E[2];$('#errBanner').hidden=false;
  st.ollama=code!=='503';
  $('#ollama').innerHTML=st.ollama?'<span class="dot"></span>Ollama: conectado':'<span class="dot off"></span>Ollama: no disponible';
}
const PII=/\b(?:dni|documento|tel(?:é|e)fono|tel\.|cel(?:ular)?)\b[^\d\n]{0,6}[\d.\s-]{6,}|\b\d{1,2}\.\d{3}\.\d{3}\b|\b\d{7,10}\b|\b\d{2,4}[\s-]\d{6,8}\b/gi;
$('#piiFix').addEventListener('click',()=>{$('#caso').value=$('#caso').value.replace(PII,'[dato quitado]');$('#piiBanner').hidden=true;$('#extraer').click()});
/* Extrae por el contrato común. El servidor informa si el origen es simulado o IA.
   Los identificadores son ficticios; esta llamada todavía no crea un episodio. */
$('#extraer').addEventListener('click', async () => {
  $('#piiBanner').hidden = true;
  const texto = $('#caso').value.trim();
  if (!leerDni()) return;
  if (!texto) {
    $('#hint').textContent = 'Escribí el relato antes de continuar.';
    $('#hint').classList.add('err');
    return;
  }
  PII.lastIndex = 0;
  if (PII.test(texto)) {
    PII.lastIndex = 0;
    $('#piiBanner').hidden = false;
    return;
  }
  /* Con servidor: el episodio se crea una sola vez, antes de la primera extracción. */
  if (TriageAPI.MODO_REAL && !(await asegurarEpisodio())) return;
  /* Conserva el recorrido ilustrativo al abrir el HTML sin servidor. */
  if (!TriageAPI.MODO_REAL || !st.ollama) {
    go('revision');
    return;
  }
  const boton = $('#extraer');
  boton.disabled = true;
  boton.textContent = 'Procesando…';
  $('#proc').hidden = false;
  $('#proc').textContent = 'Consultando el backend…';
  $('#errBanner').hidden = true;
  try {
    const r = await TriageAPI.pedir('/api/extraer', {
      method: 'POST',
      body: JSON.stringify({
        codigo_paciente: st.srv.pac,
        codigo_episodio: st.ep,
        texto: texto
      })
    });
    if (!r.ok) throw new Error(r.datos.mensaje || 'No se pudo extraer el relato.');
    const resultado = r.datos;
    if (resultado.ok !== true || !['simulado', 'ia'].includes(resultado.modo) ||
        !resultado.datos || typeof resultado.datos !== 'object' || Array.isArray(resultado.datos)) {
      throw new Error('El servidor devolvió una respuesta incompatible con el contrato.');
    }
    /* Actualiza solo campos de extracción; conserva las mediciones profesionales.
       Guarda el original en f.ia para que “restaurar” use la respuesta recibida. */
    const campos = F.filter(f => ['relato', 'ant', 'br'].includes(f.box));
    for (const f of campos) {
      if (!Object.prototype.hasOwnProperty.call(resultado.datos, f.k)) {
        throw new Error('La respuesta de extracción está incompleta.');
      }
    }
    for (const f of campos) {
      const valor = resultado.datos[f.k];
      f.ia = f.t === 'chk' ? valor === true : (valor == null ? '' : String(valor));
      st.rev[f.k] = f.ia;
    }
    st.extraccion = resultado;
    /* A08: guarda el relato tal como se envió, aunque después se edite el Ingreso. */
    st.relatoOriginal = texto;
    st.modoServidor = resultado.modo;
    renderSimbar();
    st.disc = {};
    resetDecision();
    $('#hint').classList.remove('err');
    $('#hint').textContent = 'Respuesta recibida. Revisá los datos antes de continuar.';
    go('revision');
    /* Las advertencias se muestran como texto, sin interpretar HTML. */
    $('#errTitle').textContent = resultado.modo === 'simulado'
      ? 'Extracción simulada: caso predefinido' : 'Extracción por IA: requiere revisión';
    $('#errMsg').textContent = (resultado.advertencias || []).join(' ');
    $('#errCode').textContent = resultado.modo === 'simulado' ? 'MODO SIMULADO' : 'MODO IA';
    $('#errBanner').hidden = false;
  } catch (error) {
    /* Conserva el relato y los datos previos cuando falla la solicitud. */
    $('#hint').textContent = error.message || 'No se pudo completar la extracción.';
    $('#hint').classList.add('err');
  } finally {
    boton.disabled = false;
    boton.textContent = 'Extraer datos';
    $('#proc').hidden = true;
  }

});
function updOllama(){
  $('#ollama').textContent = st.ollama
    ? (st.extraccion ? 'Extracción: '+st.extraccion.modo : (TriageAPI.MODO_REAL ? 'Extracción: backend (sin consultar)' : 'Demo sin servidor'))
    : 'Continuar sin extracción';
  if(!st.ollama){$('#errTitle').textContent='La IA no está disponible.';$('#errMsg').textContent='Seguí con el triage habitual: no se pierde nada de lo cargado.';$('#errCode').textContent='503 · ollama_no_disponible';$('#errBanner').hidden=false;$('#extraer').textContent='Continuar sin IA'}
  else{$('#errBanner').hidden=true;$('#extraer').textContent='Extraer datos'}
  const c=$('#confirmar');c.textContent=st.ollama?'Pedir sugerencia':'IA no disponible';$('#sinIA').classList.toggle('primary',!st.ollama);
  if(st.screen==='revision')updControl();
}
$('#ollama').addEventListener('click',()=>{st.ollama=!st.ollama;updOllama()});

/* Revisión */
const num=v=>Number(String(v).replace(',','.'));
/* Controles técnicos: los define validacion.js (mismos que el backend, C04).
   Se valida el caso completo para que también cuenten la coherencia de TA y la privacidad. */
function errorTecnico(f,v){
  if(!window.TriageDatos)return null;
  const datos=Object.assign({},st.rev,{[f.k]:v});
  return TriageDatos.validate(datos).errors[f.k]||null;
}
function check(f,v){
  if(f.t==='chk')return 'ok';
  if(v===''||v==null)return 'none';
  if(errorTecnico(f,v))return 'bad';
  if(f.t==='num'){const n=num(v);return (isNaN(n)||n<f.min||n>f.max)?'bad':'ok'}
  return 'ok';
}
function status(f){
  const v=st.rev[f.k];
  if(f.t==='chk')return v!==f.ia?'fix':(v?'ia':'');
  const c=check(f,v);
  if(c==='bad')return 'bad';
  if(c==='none')return isReq(f)?'none':'';
  if(f.src==='med')return 'med';
  if(f.hce!=null)return v===f.hce?'hce':'fix';
  /* A08: si la extracción no trajo el dato y lo cargó el profesional, es "completado", no "corregido". */
  const orig=f.ia??'';
  if(orig==='')return 'add';
  if(v!==orig)return 'fix';
  return 'ia';
}
/* A08: los obligatorios salen del esquema común (TriageDatos.required = OBLIGATORIOS del backend). */
const REQ=window.TriageDatos?[...TriageDatos.required.ingreso,...TriageDatos.required.medicion]:null;
function isReq(f){
  if(REQ?REQ.includes(f.k):f.req)return true;
  if(f.k==='glasgow'||f.k==='estado_conciencia')return !st.rev.glasgow&&!st.rev.estado_conciencia;
  return false;
}
function missing(){return FI.filter(f=>status(f)==='none').map(f=>f.k).filter(k=>k!=='estado_conciencia')}
function pam(){const s=num(st.rev.ta_sistolica),d=num(st.rev.ta_diastolica);return (s&&d&&check(byK('ta_sistolica'),st.rev.ta_sistolica)==='ok'&&check(byK('ta_diastolica'),st.rev.ta_diastolica)==='ok')?String(Math.round((s+2*d)/3)):''}
function fmt(f,v){if(f.t==='chk')return v?'Sí':'No';return v==null||v===''?'sin dato':v}
function tag(f){
  const s=status(f),r=' <button type="button" class="restore" data-restore="'+f.k+'" aria-label="Restaurar valor de la IA">restaurar</button>';
  if(s==='fix')return 'corregido'+r;
  if(s==='none')return f.src==='med'?'':'falta';
  if(s==='bad')return 'revisar'+((f.ia??'')!==''?r:'');
  if(s==='add')return f.box==='ident'?'cargado':'completado';
  if(s==='ia')return st.extraccion?.modo==='ia'?'IA':'simulado';
  if(s==='hce')return '';
  return '';
}
function field(f){
  const id='r-'+f.k,v=st.rev[f.k],s=status(f),w=f.w?' '+f.w:'';
  if(f.t==='chk')return '<label class="ck s-'+s+'" id="f-'+f.k+'"><input type="checkbox" id="'+id+'" data-k="'+f.k+'"'+(v?' checked':'')+'>'+f.l+'<span class="tg" id="t-'+f.k+'">'+tag(f)+'</span></label>';
  const lab='<div class="fl"><label for="'+id+'">'+(SHORT[f.k]||(f.l+(f.u?' ('+f.u+')':'')))+'</label><span class="tg" id="t-'+f.k+'">'+(f.t==='calc'?'':tag(f))+'</span></div>';
  let ctl;
  if(f.t==='calc')ctl='<input id="'+id+'" class="ro" readonly value="'+pam()+'" placeholder="—">';
  else if(f.t==='sel')ctl='<select id="'+id+'" data-k="'+f.k+'">'+(f.opts.includes('')?[]:['']).concat(f.opts).map(o=>'<option value="'+o+'"'+(o===v?' selected':'')+'>'+(o||'Sin dato')+'</option>').join('')+'</select>';
  else ctl='<input id="'+id+'" data-k="'+f.k+'" value="'+esc(v)+'"'+(f.t==='num'?' inputmode="decimal"':'')+' placeholder="'+(f.ph||(f.src==='med'?'':(isReq(f)?'Completar':'Opcional')))+'"'+(s==='bad'?' aria-invalid="true"':'')+'>';
  return '<div class="f s-'+s+w+'" id="f-'+f.k+'">'+lab+ctl+'</div>';
}
const ORDER=['ta','frecuencia_cardiaca','frecuencia_respiratoria','saturacion_o2','temperatura','estado_conciencia','glasgow','dolor_intensidad','glucemia','pam','aspecto_general'];
const SHORT={glucemia:'Glucemia (mg/dL)',frecuencia_cardiaca:'FC (lpm)',frecuencia_respiratoria:'FR (rpm)',saturacion_o2:'SpO₂ (%)',temperatura:'Temp. (°C)',estado_conciencia:'Conciencia',glasgow:'Glasgow (3–15)',dolor_intensidad:'Dolor (0–10)',glucemia:'Glucemia (mg/dL)',pam:'PAM (calc.)',aspecto_general:'Aspecto general',edad:'Edad',sexo:'Sexo'};
function taCell(){const a=byK('ta_sistolica'),b=byK('ta_diastolica');
  return '<div class="f ta s-'+status(a)+'" id="f-ta_sistolica"><div class="fl"><label for="r-ta_sistolica">TA (mmHg)</label><span class="tg" id="t-ta_sistolica">'+tag(a)+'</span></div><div class="tapair"><input id="r-ta_sistolica" data-k="ta_sistolica" inputmode="decimal" aria-label="TA sistólica" placeholder="sist." value="'+esc(st.rev.ta_sistolica)+'"><span>/</span><span class="f s-'+status(b)+'" id="f-ta_diastolica"><input id="r-ta_diastolica" data-k="ta_diastolica" inputmode="decimal" aria-label="TA diastólica" placeholder="diast." value="'+esc(st.rev.ta_diastolica)+'"><span class="tg" id="t-ta_diastolica" hidden></span></span></div></div>';}

/* Signos vitales: celdas con nombre completo, unidad, referencia y aviso inmediato */
const VIT={
  ta:{n:'Tensión arterial',ab:'TA',u:'mmHg',ref:'Normal 90–140 / 60–90',cls:'ta'},
  frecuencia_cardiaca:{n:'Frecuencia cardíaca',ab:'FC',u:'lpm',ref:'Normal 60–100',lo:60,hi:100,clo:40,chi:130,lt:'Bradicardia',ht:'Taquicardia'},
  frecuencia_respiratoria:{n:'Frecuencia respiratoria',ab:'FR',u:'rpm',ref:'Normal 12–20',lo:12,hi:20,clo:8,chi:30,lt:'Bradipnea',ht:'Taquipnea'},
  saturacion_o2:{n:'Saturación de oxígeno',ab:'SpO₂',u:'%',ref:'Normal 95–100',lo:95,clo:90,lt:'Saturación baja'},
  temperatura:{n:'Temperatura',ab:'T°',u:'°C',ref:'Normal 36–37,5',lo:36,hi:37.5,lt:'Hipotermia',ht:'Fiebre'},
  glucemia:{n:'Glucemia capilar',ab:'opcional',u:'mg/dL',ref:'Normal 70–140',lo:70,hi:140,lt:'Hipoglucemia',ht:'Hiperglucemia'},
  pam:{n:'Presión arterial media',ab:'PAM',u:'mmHg',ref:'Se calcula sola con la TA',calc:true},
  estado_conciencia:{n:'Nivel de conciencia',ab:'',sel:true,ref:'Con esto o Glasgow alcanza'},
  glasgow:{n:'Escala de Glasgow',ab:'3–15',u:'pts',ref:'15 = normal',lo:15,clo:15,lt:'Alteración de conciencia'},
  dolor_intensidad:{n:'Intensidad del dolor',ab:'0–10',u:'/10',ref:'0 sin dolor · 10 el peor',hi:4,chi:7,ht:'Dolor'},
  aspecto_general:{n:'Aspecto general',ab:'opcional',text:true,ref:'Pálido, sudoroso, agitado…'}
};
function vEval(k){
  const c=VIT[k],v=st.rev[k],f=byK(k);
  if(v===''||v==null)return {s:status(f)==='none'?'none':'',m:c.ref};
  if(c.sel)return v!=='Alerta'?{s:'crit',m:'Alteración de conciencia · regla de seguridad'}:{s:'',m:c.ref};
  if(c.text)return {s:'',m:c.ref};
  if(check(f,v)==='bad')return {s:'bad',m:errorTecnico(f,v)||('Valor imposible ('+f.min+'–'+f.max+'). Verificá el dato.')};
  const n=num(v);
  if(c.clo!=null&&n<c.clo)return {s:'crit',m:(c.lt||'Bajo')+' · regla de seguridad'};
  if(c.chi!=null&&n>c.chi)return {s:'crit',m:(c.ht||'Alto')+(k==='dolor_intensidad'?' intenso':'')+' · regla de seguridad'};
  if(c.lo!=null&&n<c.lo)return {s:'abn',m:(c.lt||'Bajo')+' · '+c.ref.toLowerCase()};
  if(c.hi!=null&&n>c.hi)return {s:'abn',m:(c.ht||'Alto')+(k==='dolor_intensidad'?' moderado':'')+' · '+c.ref.toLowerCase()};
  return {s:'',m:c.ref};
}
function taEval(){
  const a=byK('ta_sistolica'),b=byK('ta_diastolica'),sv=st.rev.ta_sistolica,dv=st.rev.ta_diastolica;
  if(!sv&&!dv)return {s:'none',m:VIT.ta.ref};
  if((sv&&check(a,sv)==='bad')||(dv&&check(b,dv)==='bad'))return {s:'bad',m:(sv&&errorTecnico(a,sv))||(dv&&errorTecnico(b,dv))||'Valor imposible. Verificá el dato.'};
  if(!sv||!dv)return {s:'none',m:'Falta '+(!sv?'la sistólica':'la diastólica')};
  const s1=num(sv),d1=num(dv);
  if(d1>=s1)return {s:'bad',m:'La diastólica no puede ser mayor que la sistólica.'};
  if(s1<90)return {s:'crit',m:'Hipotensión · regla de seguridad'};
  if(s1>140||d1>90)return {s:'abn',m:'Hipertensión · normal 90–140 / 60–90'};
  if(d1<60)return {s:'abn',m:'Diastólica baja · normal 60–90'};
  return {s:'',m:VIT.ta.ref};
}
function vCell(k){
  const c=VIT[k];
  if(k==='ta'){const e=taEval();
    return '<div class="v ta s-'+e.s+'" id="f-ta"><label for="r-ta_sistolica"><b>'+c.n+'</b><span class="ab">'+c.ab+' · sistólica / diastólica</span></label><div class="vin"><input id="r-ta_sistolica" data-k="ta_sistolica" inputmode="numeric" aria-label="TA sistólica" placeholder="120" value="'+esc(st.rev.ta_sistolica)+'"><span class="sl">/</span><input id="r-ta_diastolica" data-k="ta_diastolica" inputmode="numeric" aria-label="TA diastólica" placeholder="80" value="'+esc(st.rev.ta_diastolica)+'"><span class="u">'+c.u+'</span></div><div class="vh" id="h-ta">'+e.m+'</div></div>'}
  if(c.calc)return '<div class="v calc" id="f-pam"><div class="vl"><b>'+c.n+'</b><span class="ab">'+c.ab+'</span></div><div class="vin"><span class="pv" id="pamv">'+(pam()||'—')+'</span><span class="u">'+c.u+'</span></div><div class="vh">'+c.ref+'</div></div>';
  const e=vEval(k),f=byK(k),v=st.rev[k];
  let ctl;
  if(c.sel)ctl='<select id="r-'+k+'" data-k="'+k+'">'+f.opts.map(o=>'<option value="'+o+'"'+(o===v?' selected':'')+'>'+(o||'Elegí…')+'</option>').join('')+'</select>';
  else ctl='<input id="r-'+k+'" data-k="'+k+'" '+(c.text?'':'inputmode="decimal" ')+'value="'+esc(v)+'"'+(c.text?' placeholder="'+c.ref+'"':'')+'>'+(c.u?'<span class="u">'+c.u+'</span>':'');
  return '<div class="v s-'+e.s+'" id="f-'+k+'"'+(c.text?' style="grid-column:span 1"':'')+'><label for="r-'+k+'"><b>'+c.n+'</b>'+(c.ab?'<span class="ab">'+c.ab+'</span>':'')+'</label><div class="vin">'+ctl+'</div><div class="vh" id="h-'+k+'">'+(c.text?'':e.m)+'</div></div>';
}
function updVital(k){
  if(k==='ta_sistolica'||k==='ta_diastolica'){const e=taEval();$('#f-ta').className='v ta s-'+e.s;$('#h-ta').textContent=e.m;return}
  if(!VIT[k]||VIT[k].calc)return;const e=vEval(k);$('#f-'+k).className='v s-'+e.s;if(!VIT[k].text)$('#h-'+k).textContent=e.m;
}
function renderForm(){
  $('#origTxt').textContent=st.relatoOriginal||$('#caso').value||'(sin texto)';
  $('#g-ident').innerHTML=F.filter(f=>f.box==='ident').map(field).join('');
  $('#g-vitales').innerHTML=['ta','frecuencia_cardiaca','frecuencia_respiratoria','saturacion_o2','temperatura','glucemia','pam'].map(vCell).join('');
  $('#g-dolor').innerHTML=['estado_conciencia','glasgow','dolor_intensidad','aspecto_general'].map(vCell).join('');
  ['br','ant'].forEach(b=>$('#g-'+b).innerHTML=F.filter(f=>f.box===b).map(field).join(''));
  updControl();
}
function updField(f){
  if(VIT[f.k]||f.k==='ta_sistolica'||f.k==='ta_diastolica'){updVital(f.k);return}
  const el=$('#f-'+f.k),s=status(f);
  el.className=(f.t==='chk'?'ck':'f')+' s-'+s+(f.w?' '+f.w:'')+(f.k==='ta_sistolica'?' ta':'');
  $('#t-'+f.k).innerHTML=tag(f);
  const i=$('#r-'+f.k);if(i&&i.tagName==='INPUT'&&f.t!=='chk')i.toggleAttribute('aria-invalid',s==='bad');
}
function updControl(){
  const m=missing(),bad=FI.filter(f=>status(f)==='bad'),msgs=[];
  ['glasgow','estado_conciencia'].forEach(k=>updField(byK(k)));
  $('#pamv')&&($('#pamv').textContent=pam()||'—');
  const cm=CORE.filter(k=>!st.rev[k]);if(m.length)msgs.push('<span>Falta: '+m.map(k=>ml(k)).join(', ')+'.</span>');
  if(cm.length>=3)msgs.push('<span class="w">Con '+cm.length+' vitales sin medir no se emite prioridad.</span>');
  if(st.rev.ant_diabetes&&!st.rev.glucemia)msgs.push('<span>Diabetes: medir glucemia capilar.</span>');
  if(bad.length)msgs.push('<span class="w">Fuera de rango lógico: '+bad.map(f=>f.l).join(', ')+'. Verificá el dato antes de seguir.</span>');
  const sp=num(st.rev.saturacion_o2),fr=num(st.rev.frecuencia_respiratoria),gl=num(st.rev.glasgow),ec=st.rev.estado_conciencia;
  if(st.rev.br_disnea&&sp>=95&&fr&&fr<=20)msgs.push('<span class="w">Discordancia: “Dificultad para respirar” marcada con SpO₂ '+sp+' % y FR '+fr+'. Confirmá los valores.</span>');
  if(gl===15&&ec&&ec!=='Alerta')msgs.push('<span class="w">Discordancia: Glasgow 15 con estado “'+ec+'”. Confirmá.</span>');
  if(!msgs.length)msgs.push('<span>Datos completos.</span>');
  $('#ctrl').innerHTML=msgs.join('');
  $('#confirmar').disabled=bad.length>0||!st.ollama;$('#badHint').hidden=!bad.length;
}
$('#rvForm').addEventListener('keydown',e=>{
  if(e.key!=='Enter'||e.target.tagName==='TEXTAREA')return;
  const L=[...document.querySelectorAll('#g-vitales input:not([readonly]),#g-dolor input,#g-dolor select')],i=L.indexOf(e.target);
  if(i>-1){e.preventDefault();(L[i+1]||$('#confirmar')).focus()}
});
$('#rvForm').addEventListener('input',e=>{
  const k=e.target.dataset.k;if(!k)return;const f=byK(k);
  st.rev[k]=f.t==='chk'?e.target.checked:e.target.value;
  updField(f);updControl();
});
$('#rvForm').addEventListener('click',e=>{const k=e.target.dataset.restore;if(!k)return;e.preventDefault();const f=byK(k);st.rev[k]=base(f);renderForm()});
$('#confirmar').addEventListener('click',async()=>{await guardarMediciones();st.manual=false;st.insuf=CORE.filter(k=>!st.rev[k]).length>=3;go('resumen')});
$('#sinIA').addEventListener('click',async()=>{await guardarMediciones();st.manual=true;st.insuf=false;go('resumen')});

/* ===== Guardado en el servidor (episodio, mediciones, correcciones, historial) =====
   Solo con servidor. Sin servidor (doble clic) no se guarda nada, como antes.
   - El episodio lo crea el servidor y genera el código (EPI-…).
   - La primera vez que se piden sugerencias se registra una MEDICIÓN.
   - Si después se cambian valores, se registra una CORRECCIÓN (no se pisa la original).
   - Una reevaluación desde En espera es una toma nueva: se registra otra MEDICIÓN. */
const VALORES_MEDICION=['ta_sistolica','ta_diastolica','frecuencia_cardiaca','frecuencia_respiratoria','saturacion_o2','temperatura','glucemia','estado_conciencia','glasgow','dolor_intensidad','aspecto_general'];
const nuevoSrv=()=>({ep:null,pac:null,medicion:null,ingreso:null,nuevaToma:false,aviso:null});
st.srv=nuevoSrv();
/* Circuito de Maricel:
   1) Con DNI: POST /api/demo/pacientes/identificar {dni} -> paciente.codigo_paciente (el mismo DNI siempre da el mismo código).
   2) Ese código se usa para crear el episodio (una atención nueva).
   3) Las atenciones anteriores se buscan con GET /api/demo/episodios?codigo_paciente=…
   Sin DNI (paciente sin documento) se usa un código provisorio, como antes. */
async function asegurarEpisodio(){
  if(st.srv.ep)return true;
  let pac='PAC-'+Math.random().toString(36).slice(2,8).toUpperCase().padEnd(6,'0');
  st.srv.anteriores=null;st.srv.identificado=false;
  if(st.dni){
    const id=await TriageAPI.identificarPaciente(st.dni);
    if(id.estado===401){location.href='index.html';return false}
    if(!id.ok){$('#hint').textContent='No se pudo identificar al paciente por DNI: '+(id.datos.mensaje||'error del servidor')+' Tu texto se conservó.';$('#hint').classList.add('err');return false}
    pac=id.datos.paciente.codigo_paciente;st.srv.identificado=true;DNI_PAC[st.dni]=pac;
    /* Atenciones anteriores (antes de crear la nueva, así no se cuenta a sí misma). */
    if(!id.datos.paciente.creado){
      const prev=await TriageAPI.episodiosDePaciente(pac);
      if(prev.ok)st.srv.anteriores=prev.datos.episodios||[];
    }else st.srv.anteriores=[];
  }
  const r=await TriageAPI.crearEpisodio(pac);
  if(r.estado===401){location.href='index.html';return false}
  if(!r.ok){$('#hint').textContent='No se pudo crear el episodio: '+(r.datos.mensaje||'error del servidor')+' Tu texto se conservó.';$('#hint').classList.add('err');return false}
  st.srv.ep=r.datos.episodio.codigo_episodio;st.srv.pac=r.datos.episodio.codigo_paciente||pac;st.ep=st.srv.ep;
  return true;
}
function valoresMedidos(){
  const d=window.TriageDatos?TriageDatos.validate(st.rev).data:{},v={};
  VALORES_MEDICION.forEach(k=>{if(d[k]!=null&&d[k]!=='')v[k]=d[k]});
  return v;
}
/* Datos de ingreso revisados (los guarda el servidor desde 23/10): edad, sexo y lo extraído del relato.
   Se mandan con su tipo (número, texto, sí/no). No se manda el relato completo ni el DNI.
   Solo se vuelven a mandar si cambiaron. */
const CAMPOS_INGRESO=['edad','sexo','motivo_categoria','tiempo_evolucion_valor','tiempo_evolucion_unidad','motivo_consulta',
  'dolor_localizacion','sintomas_asociados','dolor_caracteristicas','br_sangrado','br_convulsion','br_disnea','br_trauma',
  'ant_diabetes','ant_cardio','ant_resp','ant_anticoag','ant_inmuno','ant_embarazo','ant_medicacion','alergias','antecedentes_otros'];
function datosIngreso(){
  const d={};
  CAMPOS_INGRESO.forEach(k=>{const f=byK(k);if(!f)return;const v=st.rev[k];
    if(f.t==='chk'){d[k]=v===true;return}
    if(v==null||String(v).trim()==='')return;
    if(f.t==='num'){const n=num(v);if(Number.isFinite(n))d[k]=k==='edad'?Math.round(n):n;return}
    d[k]=String(v).trim();});
  return d;
}
async function guardarDatosIngreso(){
  const d=datosIngreso(),clave=JSON.stringify(d);
  if(st.srv.ingreso===clave)return;
  const origen=st.manual?'manual':(st.extraccion&&st.extraccion.modo)||null;
  const r=await TriageAPI.registrarDatosIngreso(st.srv.ep,d,origen);
  if(r.estado===401){location.href='index.html';return}
  if(!r.ok){st.srv.aviso='No se pudieron guardar los datos de ingreso: '+(r.datos.mensaje||'error del servidor')+' El triage sigue.';return}
  st.srv.ingreso=clave;
}
async function guardarMediciones(){
  st.srv.aviso=null;
  if(!TriageAPI.MODO_REAL||!st.srv.ep)return;
  await guardarDatosIngreso();
  const v=valoresMedidos();
  if(!Object.keys(v).length)return;
  let r;
  if(!st.srv.medicion||st.srv.nuevaToma){
    r=await TriageAPI.registrarMedicion(st.srv.ep,new Date().toISOString(),v);
  }else{
    const prev=st.srv.medicion.valores,cambios={};
    VALORES_MEDICION.forEach(k=>{const a=prev[k]??null,b=v[k]??null;if(a!==b)cambios[k]=b});
    if(!Object.keys(cambios).length)return;
    r=await TriageAPI.corregirMedicion(st.srv.ep,st.srv.medicion.id,cambios,'Corregido en la revisión, antes de la decisión.');
  }
  if(r.estado===401){location.href='index.html';return}
  if(!r.ok){st.srv.aviso='No se pudo guardar la medición: '+(r.datos.mensaje||'error del servidor')+' El triage sigue; los datos quedan en pantalla.';return}
  st.srv.medicion={id:r.datos.evento.id,valores:v};st.srv.nuevaToma=false;
}
const TIPO_EVENTO={EPISODIO_CREADO:'Episodio creado',MEDICION_REGISTRADA:'Medición registrada',MEDICION_CORREGIDA:'Medición corregida',ESTADO_CAMBIADO:'Cambio de estado',DECISION_REGISTRADA:'Decisión registrada',DATOS_INGRESO_REGISTRADOS:'Datos de ingreso registrados'};
const NOMBRE_ESTADO={en_ingreso:'en ingreso',en_espera:'en espera',finalizado:'finalizado (atendido)'};
/* Atenciones anteriores del mismo paciente (mismo DNI). Cada una se puede abrir para ver su historial. */
function htmlAnteriores(){
  const a=st.srv.anteriores;
  if(!st.srv.identificado)return '<div class="prev"><b>Atenciones anteriores:</b> paciente sin DNI, no se pueden buscar.</div>';
  if(!a||!a.length)return '<div class="prev"><b>Atenciones anteriores:</b> es la primera atención registrada de este paciente.</div>';
  const hora=t=>new Date(t).toLocaleString('es-AR',{dateStyle:'short',timeStyle:'short'});
  return '<div class="prev"><b>Atenciones anteriores ('+a.length+')</b><ul>'+a.map(e=>'<li>'+esc(hora(e.creado_en))+' · '+esc(e.codigo_episodio)+' · '+esc(e.profesional_usuario||'')+
    ' <button type="button" class="linkbtn" data-prev="'+esc(e.codigo_episodio)+'">ver historial</button><div class="prevdet" id="pd-'+esc(e.codigo_episodio)+'" hidden></div></li>').join('')+'</ul></div>';
}
/* Un renglón del historial guardado en el servidor (lo usan el resumen, las atenciones anteriores y el auditor). */
const horaCorta=t=>new Date(t).toLocaleString('es-AR',{dateStyle:'short',timeStyle:'short'});
function htmlEvento(e){
  const d=e.datos||{},val=d.valores?Object.entries(d.valores).filter(([k,x])=>x!==false).map(([k,x])=>(byK(k)?byK(k).l:k)+' '+(x===true?'Sí':x)).join(' · '):'';
  return '<li><b>'+esc(TIPO_EVENTO[e.tipo]||e.tipo)+'</b> · '+esc(horaCorta(e.ocurrido_en))+' · '+esc(e.profesional_usuario)+
    (d.estado_nuevo?' · '+esc(NOMBRE_ESTADO[d.estado_anterior]||'sin estado')+' → '+esc(NOMBRE_ESTADO[d.estado_nuevo]||d.estado_nuevo):'')+(d.decision?' · '+esc(d.decision)+(d.color_final?' · '+esc(d.color_final):'')+(d.motivo?' ('+esc(d.motivo)+')':''):'')+(d.evento_corregido_id?' · corrige #'+esc(d.evento_corregido_id)+(d.motivo?' ('+esc(d.motivo)+')':''):'')+(val?'<br><span class="old">'+esc(val)+'</span>':'')+'</li>';
}
const htmlEventos=evs=>'<ul>'+(evs||[]).map(htmlEvento).join('')+'</ul>';
async function verAnterior(ep,btn){
  /* El detalle va en el recuadro que está justo después del botón (si no, en #pd-<episodio>). */
  const sig=btn&&btn.nextElementSibling,box=sig&&sig.classList.contains('prevdet')?sig:document.getElementById('pd-'+ep);if(!box)return;
  if(!box.hidden){box.hidden=true;return}
  box.hidden=false;box.textContent='cargando…';
  const r=await TriageAPI.consultarEpisodio(ep);
  if(!r.ok){box.textContent='No se pudo consultar: '+(r.datos.mensaje||'error');return}
  box.innerHTML=htmlEventos(r.datos.episodio.eventos);
}
document.addEventListener('click',e=>{const b=e.target.closest('[data-prev]');if(b){e.preventDefault();verAnterior(b.dataset.prev,b)}});
async function renderHistorial(){
  const box=$('#histBox');
  if(!TriageAPI.MODO_REAL||!st.srv.ep){box.hidden=true;return}
  box.hidden=false;box.innerHTML='<b>Historial guardado en el servidor</b> · cargando…';
  const r=await TriageAPI.consultarEpisodio(st.srv.ep);
  if(!r.ok){box.innerHTML='<b>Historial guardado en el servidor.</b> No se pudo consultar: '+esc(r.datos.mensaje||'error');return}
  box.innerHTML=htmlAnteriores()+'<b>Historial guardado en el servidor</b> · '+esc(st.srv.ep)+(st.srv.aviso?'<br><span class="w">'+esc(st.srv.aviso)+'</span>':'')+
    htmlEventos(r.datos.episodio.eventos);
}
$('#demoWorse').addEventListener('click',()=>{Object.assign(st.rev,{saturacion_o2:'86',frecuencia_cardiaca:'125',frecuencia_respiratoria:'26',br_disnea:true});renderForm()});
$('#demoVitals').addEventListener('click',()=>{Object.assign(st.rev,DEMO);renderForm()});
$('#relline').addEventListener('click',e=>{const b=e.currentTarget;b.setAttribute('aria-expanded',b.getAttribute('aria-expanded')!=='true')});
function iaText(){
  const r=st.rev,ant=F.filter(f=>f.box==='ant'&&f.t==='chk'&&r[f.k]).map(f=>f.l);if(r.antecedentes_otros)ant.push(r.antecedentes_otros);
  const L=[['Motivo',[r.motivo_categoria,r.motivo_consulta].filter(Boolean).join(' · ')],['Desde hace',r.tiempo_evolucion_valor?r.tiempo_evolucion_valor+' '+r.tiempo_evolucion_unidad:''],['Dónde le duele',r.dolor_localizacion],['Cómo es el dolor',r.dolor_caracteristicas],['Síntomas que refiere',r.sintomas_asociados],['Antecedentes que menciona',ant.join(', ')]];
  $('#iaRelato').textContent=L.filter(x=>x[1]).map(x=>x[1]).join(' · ');
}
$('#iaFix').addEventListener('input',e=>{const k=e.target.dataset.k;if(!k)return;const f=byK(k);st.rev[k]=e.target.value;updField(f);iaText();refreshSummary()});
$('#iaFix').addEventListener('click',e=>{const k=e.target.dataset.restore;if(!k)return;e.preventDefault();st.rev[k]=base(byK(k));$('#g-relato').innerHTML=F.filter(f=>f.box==='relato').map(field).join('');iaText();refreshSummary()});

/* Resumen */
function summaryRows(){
  const r=st.rev,v=k=>r[k]===''?null:r[k],fx=origen;
  const list=pre=>FI.filter(f=>f.box===pre&&f.t==='chk'&&r[f.k]).map(f=>f.l);
  const ant=list('ant');if(r.alergias)ant.push('Alergias: '+r.alergias);if(r.antecedentes_otros)ant.push(r.antecedentes_otros);
  const br=list('br');
  return [
    ['Episodio',st.ep,''],
    ['Paciente (DNI)',st.dni?fmtDni(st.dni):'Sin identificar',''],
    ['Edad / sexo',[v('edad')?r.edad+' años':null,v('sexo')].filter(Boolean).join(' · ')||null,fx('edad','sexo')],
    ['Motivo',(v('motivo_categoria')||'')+(v('motivo_consulta')?' · '+r.motivo_consulta:''),fx('motivo_categoria','motivo_consulta')],
    ['Síntomas referidos',v('sintomas_asociados')||'No refiere',fx('sintomas_asociados')],
    ['Evolución',v('tiempo_evolucion_valor')?r.tiempo_evolucion_valor+' '+r.tiempo_evolucion_unidad:null,fx('tiempo_evolucion_valor','tiempo_evolucion_unidad')],
    ['TA / PAM',v('ta_sistolica')&&v('ta_diastolica')?r.ta_sistolica+'/'+r.ta_diastolica+' mmHg'+(pam()?' · PAM '+pam():''):null,fx('ta_sistolica','ta_diastolica')],
    ['FC',v('frecuencia_cardiaca')?r.frecuencia_cardiaca+' lpm':null,fx('frecuencia_cardiaca')],
    ['FR',v('frecuencia_respiratoria')?r.frecuencia_respiratoria+' rpm':null,fx('frecuencia_respiratoria')],
    ['SpO₂',v('saturacion_o2')?r.saturacion_o2+' %':null,fx('saturacion_o2')],
    ['Temperatura',v('temperatura')?r.temperatura+' °C':null,fx('temperatura')],
    ['Glucemia',v('glucemia')?r.glucemia+' mg/dL':'No registrada',fx('glucemia')],
    ['Conciencia',[v('estado_conciencia'),v('glasgow')?'Glasgow '+r.glasgow:null].filter(Boolean).join(' · ')||null,fx('estado_conciencia','glasgow')],
    ['Dolor',(v('dolor_intensidad')?r.dolor_intensidad+'/10 · ':'Escala sin medir · ')+(r.dolor_localizacion||'—')+(r.dolor_caracteristicas?' · '+r.dolor_caracteristicas:''),fx('dolor_localizacion','dolor_caracteristicas')],
    ['Banderas rojas',br.length?br.join(', '):'Ninguna',fx('br_sangrado','br_convulsion','br_disnea','br_trauma')],
    ['Aspecto general',v('aspecto_general')||'No registrado',fx('aspecto_general')],
    ['Antecedentes',ant.length?ant.join(', '):'Ninguno',fx('ant_diabetes','ant_cardio','ant_resp','ant_anticoag','ant_inmuno','ant_embarazo','ant_medicacion','alergias','antecedentes_otros')],
  ];
}
/* A08: de dónde sale cada dato del resumen. Prioridad: corregido > completado/cargado > medido > extraído. */
function origen(...ks){
  const ss=ks.map(k=>status(byK(k)));
  if(ss.includes('fix'))return 'corregido';
  if(ss.includes('add'))return ks.every(k=>byK(k).box==='ident')?'cargado':'completado';
  if(ss.includes('med'))return 'medido';
  if(ss.includes('ia'))return 'extraído · '+(st.extraccion?.modo==='ia'?'IA':'simulado');
  return '';
}
function conteo(){
  const n=s=>FI.filter(f=>status(f)===s).length;
  return {ia:n('ia'),fix:n('fix'),add:n('add'),med:n('med'),falta:missing().length};
}
function renderResumen(){
  $('#g-relato').innerHTML=F.filter(f=>f.box==='relato').map(field).join('');$('#iaDet').open=false;iaText();
  refreshSummary();renderCard();
  renderInsuf();renderHistorial();
  $('#triageCard').hidden=st.insuf||st.manual;$('#insufCard').hidden=!st.insuf||st.manual;$('#manualCard').hidden=!st.manual;
  renderReg();
}
/* Información insuficiente: lista lo que falta de verdad (antes era un texto fijo del maquetado). */
function renderInsuf(){
  const esMed=k=>byK(k).src==='med'||k==='glasgow',m=missing();
  const sinMedir=m.filter(esMed).map(k=>ml(k)),otros=m.filter(k=>!esMed(k)).map(k=>ml(k));
  const items=sinMedir.map(t=>'Medir: '+t).concat(otros.map(t=>'Completar: '+t));
  $('#insufList').innerHTML=(items.length?items:['Revisá los datos cargados']).map(t=>'<li>'+esc(t)+'</li>').join('');
}
/* Cartel de arriba: dice la verdad según de dónde vino la extracción. */
function renderSimbar(){
  /* Se recuerda el último modo que informó el servidor, aunque se empiece un caso nuevo. */
  const ia=st.modoServidor==='ia';
  $('#simbar').innerHTML=ia
    ?'<b>Datos ficticios · Extracción con IA local.</b> Los datos del relato los extrajo MedGemma en esta computadora y requieren revisión. La sugerencia de color, el dictado, los tiempos y los registros siguen siendo de demostración (no son guías del hospital).'
    :'<b>Datos ficticios · Simulación.</b> La extracción, la sugerencia de color, el dictado, los tiempos y los registros son de demostración. No provienen de MedGemma ni de guías del hospital.';
  $('#simChip').lastChild.textContent=ia?'IA LOCAL · RESTO SIMULADO':'MODO SIMULADO';
  /* Chip de estado de la IA: antes de la primera extracción decía siempre "IA: simulada". */
  if(st.ollama&&!st.extraccion)$('#ollama').innerHTML='<span class="dot"></span>IA: '+(ia?'MedGemma local':'simulada');
}
function refreshSummary(){
  $('#summary').innerHTML=summaryRows().map(([l,val,c])=>'<div><span>'+l+'</span><b>'+(val==null?'<span class="st none">Sin información</span>':esc(val))+'</b>'+(c?'<em>'+c+'</em>':'')+'</div>').join('');
  const m=missing();$('#sumMiss').innerHTML=m.length?m.map(k=>'<span class="st none">'+ml(k)+'</span>').join(' '):'ninguno';
  const c=FI.filter(f=>status(f)==='fix'),a=FI.filter(f=>status(f)==='add'),notas=[];
  /* A08: el valor original (admisión o extracción) se conserva y se muestra junto al confirmado. */
  if(c.length)notas.push('<b>Correcciones ('+c.length+').</b> '+c.map(f=>f.l+': '+(f.hce!=null?'admisión ':'extracción ')+esc(fmt(f,f.ia??f.hce))+' → '+esc(fmt(f,st.rev[f.k]))).join(' · '));
  if(a.length)notas.push('<b>Completados por el profesional ('+a.length+').</b> '+a.map(f=>f.l+': '+esc(fmt(f,st.rev[f.k]))).join(' · '));
  $('#corrNote').innerHTML=notas.length?notas.join('<br>'):'Sin correcciones: se usaron los valores extraídos.';
  $('#triageMiss').innerHTML=m.map(k=>'<li>'+ml(k)+'</li>').join('');$('#missBox').hidden=!m.length;
}
function renderReg(){
  const d=st.decision,l=st.level!=null?LEVELS[st.level][0]:null;
  const sug=st.manual?'Sin asistencia IA':st.insuf?'Información insuficiente':(()=>{const c=calcSug();return LEVELS[SUG][0]+' (simulación: '+LEVELS[c.M.lv][0]+(c.R.length?' · reglas: '+c.R.map(x=>x.t).join(', '):'')+')'})();
  const dec=st.manual?(st.mlv!=null?'Manual · '+LEVELS[st.mlv][0]:'pendiente'):(d?(d==='aceptar'?'Aceptada · '+LEVELS[SUG][0]:d==='modificar'?'Modificada · '+(l||'—'):'Rechazada · manual '+(l||'—')):'pendiente');
  $('#reg').textContent='Episodio:  '+st.ep+'\nPaciente:  '+(st.dni?'DNI '+fmtDni(st.dni):'sin identificar')+'\n'+(st.prev?'Anterior:  '+LEVELS[st.prev.lv][0]+' (hace '+fmtMin(st.prev.min)+') · se conserva en el historial\n':'')+'Fecha:     '+new Date().toLocaleString('es-AR',{dateStyle:'short',timeStyle:'short'})+'\nExtracción: '+(st.extraccion?(st.extraccion.modo==='ia'?'IA · '+(st.extraccion.modelo||'modelo local'):'simulada · caso '+(st.extraccion.caso_simulado_id||'—')):'SIMULADO (sin servidor)')+'\nDatos:     '+(()=>{const q=conteo();return q.ia+' extraídos · '+q.fix+' corregidos · '+q.add+' completados · '+q.med+' medidos · '+q.falta+' faltantes'})()+'\nGuía:      de ejemplo, no oficial\nSugerencia: '+sug+'\nDecisión:  '+dec+'\nDiscrim.:  '+(Object.keys(st.disc).length?Object.entries(st.disc).map(([k,v])=>k.split('|')[1]+': '+v.toUpperCase()).join(' · '):'sin preguntas respondidas')+'\nFuente:    Guía '+GUIA_VER+' · «'+diagName()+'» · '+LEVELS[SUG][0]+'\nUsuario:   '+(st.user?st.user.u+' ('+st.user.nom+')':'[USUARIO]')+' · Box 1';
}

$('#nuevo').addEventListener('click',()=>{
  /* Restablece los originales para evitar restaurar datos de otro episodio. */
  st.extraccion=null;st.relatoOriginal=null;st.srv=nuevoSrv();renderSimbar();
  st.dni=null;$('#dni').value='';$('#dni').classList.remove('bad');
  F.forEach((f,i)=>{f.ia=TriageAPI.MODO_REAL?(f.t==='chk'?false:null):ejemploOriginal[i].ia;});$('#caso').value='';st.rev=init();st.disc={};st.prev=null;st.manual=false;st.insuf=false;epN++;st.ep='EP-00'+epN;resetDecision();go('ingreso')});
/* Sesión de DEMOSTRACIÓN: la crea index.html (login.js). No es autenticación real. */
/* Sesión (A07): la consulta api.js. Modo real = Flask (/api/sesion); modo demo = login simulado. */
async function salir() {
  try {
    await TriageAPI.logout();
    location.href = 'index.html';
  } catch (e) {
    alert(e.message);
  }
}
/* Evita presentar los ejemplos precargados como extracción del servidor. */
if (TriageAPI.MODO_REAL) {
  F.forEach(f=>{if ('ia' in f) f.ia=f.t==='chk'?false:null;
    /* A08: con servidor no hay admisión (HCE): edad y sexo los carga el profesional. */
    if ('hce' in f) f.hce=null;});
}
/* Arranca cuando ya se cargaron sugerencia.js y espera.js (usa funciones de los tres archivos). */
document.addEventListener('DOMContentLoaded',async function iniciarSesion(){
  st.user=await TriageAPI.sesion();
  if(!st.user){location.href='index.html';return}
  if(st.user.debeCambiar){location.href='cambiar_password.html';return}
  if(st.user.rol==='admin'){location.href='admin.html';return}
  if(st.user.modoExtraccion){st.modoServidor=st.user.modoExtraccion;renderSimbar()}
  const etiqueta=st.user.modo==='real'?'sesión del servidor':'acceso simulado';
  $('#userChip').hidden=false;$('#userChip').innerHTML='<b>'+esc(st.user.u)+'</b> · '+esc(st.user.nom)+' · '+etiqueta+' <button type="button" class="linkbtn" id="logout">Salir</button>';
  $('#userChip').addEventListener('click',e=>{if(e.target.id==='logout')salir()});
  go(st.user.rol==='auditor'?'espera':'ingreso');
});
/* ===== Imprimir / PDF =====
   Imprime solo el resumen del episodio (datos, correcciones, historial y registro).
   Desde el diálogo de impresión se puede elegir "Guardar como PDF". */
$('#imprimir').addEventListener('click',()=>{
  const det=$('#s-resumen details.more'),abierto=det&&det.open;
  if(det)det.open=true;
  $('#printHead').innerHTML='<b>Triage asistido · HRRG · Equipo 1 PP2</b><br>Episodio '+esc(st.ep)+' · '+(st.dni?'DNI '+esc(fmtDni(st.dni))+' · ':'')+esc(new Date().toLocaleString('es-AR'))+' · Usuario '+esc(st.user?st.user.u:'—')+
    '<br><i>Datos ficticios. La sugerencia de color usa reglas de ejemplo (no es la guía del hospital). La decisión es del profesional.</i>';
  const volver=()=>{if(det)det.open=abierto;window.removeEventListener('afterprint',volver)};
  window.addEventListener('afterprint',volver);
  window.print();
});

/* ===== DNI del paciente =====
   Pedido del HRRG: identificar al paciente para vincular el triage con la historia clínica.
   - Es opcional (puede llegar alguien sin documento) y se valida el formato: 7 u 8 dígitos.
   - NUNCA se manda a la IA: no está en st.rev ni en el relato; /api/extraer recibe solo el texto y los códigos.
   - Por ahora no se guarda en el servidor ni en el navegador: falta la ruta de Maricel que lo vincule con codigo_paciente.
   - A futuro puede venir "por defecto" desde admisión / HCE. */
st.dni=null;
const fmtDni=d=>String(d).replace(/\B(?=(\d{3})+(?!\d))/g,'.');
function leerDni(){
  const el=$('#dni'),crudo=el.value.trim();
  if(!crudo){st.dni=null;el.classList.remove('bad');return true}
  const d=crudo.replace(/[.\s-]/g,'');
  if(!/^\d{7,8}$/.test(d)||/^0+$/.test(d)){
    el.classList.add('bad');
    $('#hint').textContent='El DNI tiene que tener 7 u 8 números (con o sin puntos). Corregilo o dejalo vacío si el paciente no tiene documento.';
    $('#hint').classList.add('err');el.focus();return false;
  }
  el.classList.remove('bad');st.dni=d;el.value=fmtDni(d);return true;
}
$('#dni').addEventListener('blur',()=>{if($('#dni').value.trim())leerDni()});
