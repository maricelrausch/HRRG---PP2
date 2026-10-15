/* frontend/formulario.js · Lógica de las pantallas del formulario (A05).
   Antes estaba dentro de formulario.html. Usa validacion.js (C04) para los controles. */
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
    ['3','Ante un error, el texto se conserva.'],
    ['S','Modo simulado hasta conectar el modelo.']],src:'Cuestionario HRRG §2, §4 · A1, A2'},
  revision:{t:'Pantalla 2 · Medición',items:[
    ['1','Solo lo que se mide en el box. Nombre completo, unidad y referencia en cada campo. Enter pasa al siguiente.'],
    ['A','Aviso inmediato: fuera de lo normal (borde oscuro), crítico por regla de seguridad o valor imposible (rojo).'],
    ['2','Glasgow o estado de conciencia: con uno alcanza. PAM se calcula sola.'],
    ['3','Banderas rojas y antecedentes con un toque. Lo que mencionó el paciente ya viene marcado.'],
    ['4','Avisa faltantes, rangos y discordancias. Con 3 o más vitales sin medir no se emite prioridad (RF-10). “Clasificar sin IA” siempre disponible (§6).']],src:'Doc. técnico V1.1 · Cuestionario §2 · RNF-01'},
  resumen:{t:'Pantalla 3 · Sugerencia',items:[
    ['1','Color Manchester sugerido, grande, con su origen: regla de seguridad o extracción + guía (hoy: simulado).'],
    ['2','Por qué, con cada motivo marcado REGLA o IA. Las reglas fijan un piso: la IA no puede sugerir menos (no downgrade).'],
    ['3','Aceptar con un toque. Modificar o Rechazar piden motivo.'],
    ['4','Lo que entendió la IA del relato, corregible. La decisión final es del profesional.'],
    ['5','Reglas provisorias de ejemplo: los umbrales los aprueban Guardia y Enfermería.'],
    ['F','Fuente: cada sugerencia cita el diagrama, nivel y discriminador de la guía oficial (en el sistema real; hoy, guía de ejemplo), con el fragmento para verificarlo (trazabilidad).'],
    ['↑','Qué lo haría subir: muestra los discriminadores del nivel siguiente. Los que no se miden se confirman con Sí/No y recalculan al instante (triage guiado por discriminadores).']],src:'Doc. técnico §9 Motor híbrido · Cuestionario §2 · Clase docentes'},
  espera:{t:'Pantalla 4 · En espera',items:[
    ['1','Pacientes ya clasificados que esperan, ordenados por color y tiempo.'],
    ['2','Marca a quien superó el tiempo objetivo de su color (tiempos según guía HRRG).'],
    ['3','Reevaluar abre el mismo episodio con los datos anteriores. La tarjeta muestra antes → ahora y el registro guarda las dos versiones.'],
    ['4','Escalar a ROJO con dos toques, sin cargar datos. La Guardia no depende de la IA (RNF-04).'],
    ['⏱','Reloj de reevaluación: cuenta regresiva según el tiempo objetivo de cada color; al vencerse parpadea y pide reevaluar.']],src:'Doc. técnico V1.1 · Re-triage · Cuestionario §6'}
};
const LEVELS=[['ROJO','--m-rojo','#FFFFFF','Inmediato'],['NARANJA','--m-naranja','#1A1D26','Muy urgente · 10 min'],['AMARILLO','--m-amarillo','#1A1D26','Urgente · 60 min'],['VERDE','--m-verde','#FFFFFF','Normal · 120 min'],['AZUL','--m-azul','#FFFFFF','No urgente · 240 min']];
let SUG=2;
const DESC=['Inmediato · atención inmediata','Muy urgente · 10 min','Urgente · 60 min','Normal · 120 min','No urgente · 240 min'];
/* Guía Manchester de EJEMPLO (a reemplazar por la guía oficial del HRRG vía ETL).
   Por diagrama y nivel: discriminadores. 'q' = se confirma con Sí/No; 'm' = se mide en Medición. */
const GUIA_VER='de ejemplo, no oficial (no es del HRRG)';
const DISC={
  'Dolor abdominal':{0:[['Compromiso de la vía aérea','q'],['Shock (palidez, sudoración fría, pulso débil)','q']],
                     1:[['Dolor intenso (8–10)','m'],['Vómitos con sangre','q'],['Signos de shock incipiente','q']],
                     2:[['Dolor moderado (5–7)','m'],['Vómitos persistentes','q'],['Fiebre (≥ 38,5 °C)','m']],
                     3:[['Dolor leve reciente (1–4)','m'],['Vómitos','q']]},
  'Dolor torácico':{0:[['Compromiso de la vía aérea','q'],['Shock','q']],
                    1:[['Dolor de características cardíacas (opresivo, irradiado)','q'],['Dolor intenso (8–10)','m'],['Disnea aguda','q']],
                    2:[['Dolor moderado (5–7)','m'],['Antecedente cardiovascular','q']],
                    3:[['Dolor leve reciente','m']]},
  '_':{0:[['Compromiso de la vía aérea','q'],['Respiración inadecuada','q'],['Shock','q']],
       1:[['Dolor intenso (8–10)','m'],['Alteración de conciencia','m'],['SpO₂ < 90 %','m']],
       2:[['Dolor moderado (5–7)','m'],['Fiebre (≥ 38,5 °C)','m'],['Vómitos persistentes','q']],
       3:[['Dolor leve reciente','m'],['Febrícula','m']]}
};
const PAGE={'Dolor abdominal':'[pág. —]','Dolor torácico':'[pág. —]','_':'[pág. —]'};
const diag=()=>DISC[st.rev.motivo_categoria]?st.rev.motivo_categoria:'_';
const diagName=()=>diag()==='_'?'Malestar en adulto (general)':diag();
/* Reglas de seguridad PROVISORIAS (ejemplo para el prototipo; umbrales a aprobar por Guardia y Enfermería del HRRG) */
function reglas(){
  const r=st.rev,n=k=>r[k]===''||r[k]==null?null:num(r[k]),out=[];
  const add=(lv,t)=>out.push({lv,t});
  if(r.br_convulsion)add(0,'Convulsión activa');
  if(n('glasgow')!=null&&n('glasgow')<=8)add(0,'Glasgow '+r.glasgow);
  if(r.br_sangrado&&n('ta_sistolica')!=null&&n('ta_sistolica')<90)add(0,'Sangrado con hipotensión');
  else if(r.br_sangrado)add(1,'Sangrado evidente');
  if(n('saturacion_o2')!=null&&n('saturacion_o2')<90)add(1,'SpO₂ '+r.saturacion_o2+' %');
  if(n('ta_sistolica')!=null&&n('ta_sistolica')<90)add(1,'Hipotensión (TA '+r.ta_sistolica+'/'+(r.ta_diastolica||'—')+')');
  if(n('frecuencia_cardiaca')!=null&&(n('frecuencia_cardiaca')>130||n('frecuencia_cardiaca')<40))add(1,'FC '+r.frecuencia_cardiaca+' lpm');
  if(n('frecuencia_respiratoria')!=null&&(n('frecuencia_respiratoria')>30||n('frecuencia_respiratoria')<8))add(1,'FR '+r.frecuencia_respiratoria+' rpm');
  if((r.estado_conciencia&&r.estado_conciencia!=='Alerta')||(n('glasgow')!=null&&n('glasgow')>8&&n('glasgow')<15))add(1,'Alteración del nivel de conciencia');
  if(r.br_disnea)add(1,'Dificultad para respirar');
  if(r.ant_inmuno&&n('temperatura')!=null&&n('temperatura')>=38)add(1,'Fiebre en inmunosuprimido');
  if(n('dolor_intensidad')!=null&&n('dolor_intensidad')>=8)add(1,'Dolor intenso ('+r.dolor_intensidad+'/10)');
  return out;
}
/* Sugerencia simulada de MedGemma (en el sistema real: JSON validado del modelo con RAG sobre la guía) */
function medgemma(){
  const r=st.rev,n=k=>r[k]===''||r[k]==null?null:num(r[k]),why=[];let lv=3;
  const d=n('dolor_intensidad');
  if(d!=null&&d>=5&&d<8){lv=2;why.push((r.motivo_categoria||'Dolor')+' moderado ('+d+'/10)'+(r.tiempo_evolucion_valor?' de '+r.tiempo_evolucion_valor+' '+r.tiempo_evolucion_unidad:''))}
  const t=n('temperatura');if(t!=null&&t>=37.5&&t<38.5){lv=Math.min(lv,2);why.push('Febrícula ('+r.temperatura+' °C)')}
  if(t!=null&&t>=38.5){lv=Math.min(lv,2);why.push('Fiebre ('+r.temperatura+' °C)')}
  if(r.ant_diabetes)why.push('Diabetes'+(n('glucemia')>=250?' con glucemia '+r.glucemia+' mg/dL':''));
  if(r.sintomas_asociados)why.push('Refiere: '+r.sintomas_asociados.toLowerCase());
  if(d!=null&&d<=2&&!(t>=37.5)&&lv===3)lv=4;
  if(!why.length)why.push('Sin discriminadores de mayor urgencia en los datos');
  return {lv,why};
}
function calcSug(){
  const R=reglas(),M=medgemma(),rl=R.length?Math.min(...R.map(x=>x.lv)):9;
  const C=Object.entries(st.disc).filter(([k,v])=>v==='si').map(([k])=>{const [lv,t]=k.split('|');return {lv:+lv,t}});
  const cl=C.length?Math.min(...C.map(x=>x.lv)):9,fin=Math.min(rl,M.lv,cl);
  return {R,M,C,rl,cl,fin};
}
function renderCard(){
  const c=calcSug();SUG=c.fin;const L=LEVELS[SUG];
  $('#tcPrev').hidden=!st.prev;if(st.prev)$('#tcPrev').textContent='Reevaluación · Antes: '+LEVELS[st.prev.lv][0]+' (hace '+fmtMin(st.prev.min)+')  →  Ahora: '+L[0];
  $('#triageCard').style.setProperty('--mc','var('+L[1]+')');$('#triageCard').style.setProperty('--mi',L[2]);
  $('#tcName').textContent=L[0];$('#tcDesc').textContent=DESC[SUG]+' [tiempo de ejemplo]';
  $('#tcOrigin').innerHTML=c.rl<c.M.lv?'<b>Color fijado por regla de seguridad.</b><span class="old">La simulación sugería '+LEVELS[c.M.lv][0]+'; la regla no permite bajar.</span><span class="prov">Reglas provisorias</span>'
    :(c.R.length?'<b>Simulación con reglas de ejemplo.</b><span class="old">Coincide o supera las reglas de seguridad.</span>':'<b>Simulación con reglas de ejemplo.</b><span class="old">Reglas de seguridad: sin alertas.</span>');
  if(c.cl<=c.rl&&c.cl<c.M.lv)$('#tcOrigin').innerHTML='<b>Color fijado por discriminador confirmado por el profesional.</b><span class="old">La simulación sugería '+LEVELS[c.M.lv][0]+'.</span>';
  $('#tcWhy').innerHTML=c.R.map(x=>'<li><span class="src r">REGLA</span><span>'+esc(x.t)+'</span></li>').join('')+c.C.map(x=>'<li><span class="src g">GUÍA</span><span>Confirmado: '+esc(x.t)+'</span></li>').join('')+c.M.why.map(t=>'<li><span class="src ia">IA</span><span>'+esc(t)+'</span></li>').join('');
  renderFuente();renderSubir();
}
/* Trazabilidad: fragmento de la guía que respalda el color */
function renderFuente(){
  const d=diag(),lvD=DISC[d][SUG]||[],L=LEVELS[SUG];
  $('#fuenteTxt').innerHTML='<b>Guía '+esc(GUIA_VER)+'</b> · Diagrama «'+esc(diagName())+'» · Nivel '+L[0]+' · '+PAGE[d];
  $('#fuenteFrag').textContent='DIAGRAMA: '+diagName()+'   (guía de EJEMPLO, no oficial)\n\n'+LEVELS.map((x,i)=>(i===SUG?'▶ ':'  ')+x[0].padEnd(9)+'  '+((DISC[d][i]||[['Ningún discriminador anterior']]).map(z=>z[0]).join(' · '))).join('\n')+'\n\nEl color surge del primer nivel, de arriba hacia abajo, cuyo discriminador se cumple.';
  $('#fuente').style.setProperty('--mc','var('+L[1]+')');
}
/* Qué lo haría subir + preguntas Sí/No de discriminador */
function renderSubir(){
  const box=$('#subir');
  if(SUG===0){box.hidden=true;return}box.hidden=false;
  const up=SUG-1,U=LEVELS[up],items=DISC[diag()][up]||[];
  box.innerHTML='<h4>Pasaría a <span class="chipc" style="background:var('+U[1]+');color:'+U[2]+'">'+U[0]+'</span> si se cumple alguno <span class="prov">· discriminadores de la guía</span></h4><ul>'+items.map(([t,kind])=>{
    const key=up+'|'+t,a=st.disc[key];
    return '<li><span class="q">'+esc(t)+'</span>'+(kind==='q'?'<span class="yn" data-key="'+esc(key)+'"><button type="button" data-a="si" aria-pressed="'+(a==='si')+'">Sí</button><button type="button" data-a="no" aria-pressed="'+(a==='no')+'">No</button></span>':'<span class="meas">se evalúa con lo medido</span>')+'</li>'}).join('')+'</ul><div class="hint">Tocar <b>Sí</b> recalcula el color al instante y queda registrado. Es el recorrido de la guía: se pregunta solo lo que podría subir la prioridad.</div>';
}
const F=[
  {k:'edad',l:'Edad',u:'años',t:'num',hce:'58',min:0,max:120,req:1,box:'ident'},
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
const base=f=>f.t==='chk'?f.ia:(f.ia??f.hce??'');
const init=()=>Object.fromEntries(FI.map(f=>[f.k,base(f)]));
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
  if(s==='revision'){$('#epCode').textContent=st.ep;$('#reBadge').hidden=!st.prev;if(st.prev)$('#reBadge').textContent='Reevaluación · antes '+LEVELS[st.prev.lv][0]+', hace '+fmtMin(st.prev.min);$('#demoWorse').hidden=!st.prev;$('#demoVitals').hidden=!!st.prev;renderForm();updOllama();setTimeout(()=>{const i=$('#r-ta_sistolica');i&&!i.value&&i.focus()},0)}
  if(s==='resumen')renderResumen();
  if(s==='espera')renderWait();
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
$('#extraer').addEventListener('click',()=>{
  $('#piiBanner').hidden=true;
  if(!$('#caso').value.trim()){$('#hint').textContent='Escribí o dictá el relato del paciente antes de seguir.';$('#hint').classList.add('err');return}
  PII.lastIndex=0;if(PII.test($('#caso').value)){PII.lastIndex=0;$('#piiBanner').hidden=false;return}
  $('#hint').classList.remove('err');$('#hint').textContent='Escribí o dictá lo que cuenta el paciente, con sus palabras. La IA lo interpreta; en el paso siguiente se cargan los signos vitales.';
  if(!st.ollama){go('revision');return}
  const b=$('#extraer');b.disabled=true;b.textContent='Procesando…';$('#proc').hidden=false;
  setTimeout(()=>{b.disabled=false;b.textContent='Extraer datos';$('#proc').hidden=true;go('revision')},1200);
});
function updOllama(){
  $('#ollama').innerHTML=st.ollama?'<span class="dot"></span>IA: simulada':'<span class="dot off"></span>IA: no disponible (simulado)';
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
  if(v!==(f.ia??''))return 'fix';
  return 'ia';
}
function isReq(f){
  if(f.req)return true;
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
  if(s==='bad')return 'revisar'+(f.ia!=null?r:'');
  if(s==='ia')return 'IA';
  if(s==='hce')return '';
  return '';
}
function field(f){
  const id='r-'+f.k,v=st.rev[f.k],s=status(f),w=f.w?' '+f.w:'';
  if(f.t==='chk')return '<label class="ck s-'+s+'" id="f-'+f.k+'"><input type="checkbox" id="'+id+'" data-k="'+f.k+'"'+(v?' checked':'')+'>'+f.l+'<span class="tg" id="t-'+f.k+'">'+tag(f)+'</span></label>';
  const lab='<div class="fl"><label for="'+id+'">'+(SHORT[f.k]||(f.l+(f.u?' ('+f.u+')':'')))+'</label><span class="tg" id="t-'+f.k+'">'+(f.t==='calc'?'':tag(f))+'</span></div>';
  let ctl;
  if(f.t==='calc')ctl='<input id="'+id+'" class="ro" readonly value="'+pam()+'" placeholder="—">';
  else if(f.t==='sel')ctl='<select id="'+id+'" data-k="'+f.k+'">'+f.opts.map(o=>'<option value="'+o+'"'+(o===v?' selected':'')+'>'+(o||'Sin dato')+'</option>').join('')+'</select>';
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
  $('#origTxt').textContent=$('#caso').value||'(sin texto)';
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
$('#confirmar').addEventListener('click',()=>{st.manual=false;st.insuf=CORE.filter(k=>!st.rev[k]).length>=3;go('resumen')});
$('#sinIA').addEventListener('click',()=>{st.manual=true;st.insuf=false;go('resumen')});
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

$('#subir').addEventListener('click',e=>{const b=e.target.closest('.yn button');if(!b)return;const k=b.parentElement.dataset.key;
  st.disc[k]=st.disc[k]===b.dataset.a?undefined:b.dataset.a;if(st.disc[k]===undefined)delete st.disc[k];resetDecision();renderCard();renderReg()});
/* Resumen */
function summaryRows(){
  const r=st.rev,v=k=>r[k]===''?null:r[k],fx=(...ks)=>ks.some(k=>status(byK(k))==='fix');
  const list=pre=>FI.filter(f=>f.box===pre&&f.t==='chk'&&r[f.k]).map(f=>f.l);
  const ant=list('ant');if(r.alergias)ant.push('Alergias: '+r.alergias);if(r.antecedentes_otros)ant.push(r.antecedentes_otros);
  const br=list('br');
  return [
    ['Episodio',st.ep,false],
    ['Edad / sexo',(v('edad')?r.edad+' años':null)+' · '+r.sexo,fx('edad','sexo')],
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
function renderResumen(){
  $('#g-relato').innerHTML=F.filter(f=>f.box==='relato').map(field).join('');$('#iaDet').open=false;iaText();
  refreshSummary();renderCard();
  $('#triageCard').hidden=st.insuf||st.manual;$('#insufCard').hidden=!st.insuf||st.manual;$('#manualCard').hidden=!st.manual;
  renderReg();
}
function refreshSummary(){
  $('#summary').innerHTML=summaryRows().map(([l,val,c])=>'<div><span>'+l+'</span><b>'+(val==null?'<span class="st none">Sin información</span>':esc(val))+'</b>'+(c?'<em>corregido</em>':'')+'</div>').join('');
  const m=missing();$('#sumMiss').innerHTML=m.length?m.map(k=>'<span class="st none">'+ml(k)+'</span>').join(' '):'ninguno';
  const c=FI.filter(f=>status(f)==='fix');
  $('#corrNote').innerHTML=c.length?'<b>Correcciones ('+c.length+').</b> '+c.map(f=>f.l+': '+(f.hce!=null?'admisión ':'IA ')+esc(fmt(f,f.ia??f.hce))+' → '+esc(fmt(f,st.rev[f.k]))).join(' · '):'Sin correcciones: se usaron los valores de la IA.';
  $('#triageMiss').innerHTML=m.map(k=>'<li>'+ml(k)+'</li>').join('');$('#missBox').hidden=!m.length;
}
function renderReg(){
  const d=st.decision,l=st.level!=null?LEVELS[st.level][0]:null;
  const sug=st.manual?'Sin asistencia IA':st.insuf?'Información insuficiente':(()=>{const c=calcSug();return LEVELS[SUG][0]+' (simulación: '+LEVELS[c.M.lv][0]+(c.R.length?' · reglas: '+c.R.map(x=>x.t).join(', '):'')+')'})();
  const dec=st.manual?(st.mlv!=null?'Manual · '+LEVELS[st.mlv][0]:'pendiente'):(d?(d==='aceptar'?'Aceptada · '+LEVELS[SUG][0]:d==='modificar'?'Modificada · '+(l||'—'):'Rechazada · manual '+(l||'—')):'pendiente');
  $('#reg').textContent='Episodio:  '+st.ep+' (seudonimizado)\n'+(st.prev?'Anterior:  '+LEVELS[st.prev.lv][0]+' (hace '+fmtMin(st.prev.min)+') · se conserva en el historial\n':'')+'Fecha:     [DD/MM/AAAA HH:MM]\nModelo:    SIMULADO (sin IA)\nGuía:      de ejemplo, no oficial\nSugerencia: '+sug+'\nDecisión:  '+dec+'\nDiscrim.:  '+(Object.keys(st.disc).length?Object.entries(st.disc).map(([k,v])=>k.split('|')[1]+': '+v.toUpperCase()).join(' · '):'sin preguntas respondidas')+'\nFuente:    Guía '+GUIA_VER+' · «'+diagName()+'» · '+LEVELS[SUG][0]+'\nUsuario:   '+(st.user?st.user.u+' ('+st.user.nom+')':'[USUARIO]')+' · Box 1';
}

$('#levels').innerHTML=LEVELS.map((L,i)=>'<button type="button" class="lvl" data-l="'+i+'" aria-pressed="false" style="background:var('+L[1]+');color:'+L[2]+'" title="'+L[3]+'">'+L[0]+'</button>').join('');
document.querySelectorAll('[data-d]').forEach(b=>b.addEventListener('click',()=>{
  const d=b.dataset.d;st.decision=null;st.level=null;
  document.querySelectorAll('[data-d]').forEach(x=>x.setAttribute('aria-pressed',x===b));
  document.querySelectorAll('.lvl').forEach(x=>x.setAttribute('aria-pressed','false'));
  $('#okMsg').hidden=true;$('#modForm').hidden=d==='aceptar';$('#motivoForm').hidden=d==='aceptar';$('#lowerBox').hidden=true;
  $('#motivo').value='';$('#lowerOk').checked=false;
  if(d==='aceptar'){st.decision='aceptar';commit(SUG);$('#okMsg').hidden=false;$('#okMsg').innerHTML='<b>Registrado.</b> Clasificación '+LEVELS[SUG][0]+' aceptada por el profesional.'+(st.prev?' Actualizado en En espera.':'');renderReg()}
  else{$('#registrar').dataset.d=d;updReg()}
}));
$('#levels').addEventListener('click',e=>{const b=e.target.closest('.lvl');if(!b)return;st.level=+b.dataset.l;
  document.querySelectorAll('.lvl').forEach(x=>x.setAttribute('aria-pressed',x===b));
  $('#lowerBox').hidden=!(st.level>SUG);updReg()});
function updReg(){
  const d=$('#registrar').dataset.d;let ok=!!$('#motivo').value;
  if(d==='modificar')ok=ok&&st.level!=null&&st.level!==SUG;
  if(d==='rechazar')ok=ok&&st.level!=null;
  if(st.level>SUG)ok=ok&&$('#lowerOk').checked;
  $('#registrar').disabled=!ok;
}
$('#motivo').addEventListener('change',updReg);$('#lowerOk').addEventListener('change',updReg);
$('#registrar').addEventListener('click',()=>{
  const d=$('#registrar').dataset.d;st.decision=d;commit(st.level);$('#motivoForm').hidden=true;$('#modForm').hidden=true;$('#okMsg').hidden=false;
  $('#okMsg').innerHTML=d==='modificar'?'<b>Registrado.</b> Sugerencia '+LEVELS[SUG][0]+' modificada a '+LEVELS[st.level][0]+'. Motivo: '+esc($('#motivo').value)+(st.level>SUG?' · Discrepancia registrada.':''):'<b>Registrado.</b> Sugerencia rechazada. Clasificación manual: '+LEVELS[st.level][0]+'. Motivo: '+esc($('#motivo').value)+(st.level>SUG?' · Discrepancia registrada.':'');
  renderReg();
});
$('#manual').addEventListener('click',()=>{st.insuf=false;st.manual=true;renderResumen()});
function resetDecision(){st.decision=null;st.level=null;st.mlv=null;
  document.querySelectorAll('[data-d]').forEach(x=>x.setAttribute('aria-pressed','false'));document.querySelectorAll('.lvl').forEach(x=>x.setAttribute('aria-pressed','false'));
  $('#okMsg').hidden=true;$('#motivoForm').hidden=true;$('#modForm').hidden=true;$('#mOk').hidden=true;$('#mReg').disabled=true;}
$('#nuevo').addEventListener('click',()=>{$('#caso').value='';st.rev=init();st.disc={};st.prev=null;st.manual=false;st.insuf=false;epN++;st.ep='EP-00'+epN;resetDecision();go('ingreso')});
/* Clasificación manual sin IA */
$('#mLevels').innerHTML=LEVELS.map((L,i)=>'<button type="button" class="lvl" data-m="'+i+'" aria-pressed="false" style="background:var('+L[1]+');color:'+L[2]+'">'+L[0]+'</button>').join('');
$('#mLevels').addEventListener('click',e=>{const b=e.target.closest('[data-m]');if(!b)return;st.mlv=+b.dataset.m;$('#mLevels').querySelectorAll('.lvl').forEach(x=>x.setAttribute('aria-pressed',x===b));$('#mReg').disabled=false});
$('#mReg').addEventListener('click',()=>{commit(st.mlv);$('#mOk').hidden=false;$('#mOk').innerHTML='<b>Registrado.</b> Clasificación manual '+LEVELS[st.mlv][0]+', sin asistencia IA.';renderReg()});

/* En espera y re-triage */
const TARGET=[0,10,60,120,240];
const fmtMin=m=>m<60?m+' min':Math.floor(m/60)+' h'+(m%60?' '+m%60+' min':'');
const mk=o=>Object.assign(init(),o);
const WAIT=[
  {ep:'EP-004818',lv:1,mot:'Dolor torácico',min:6,relato:'Me duele el pecho desde hace media hora, como una presión, y estoy sudando.',rev:mk({motivo_categoria:'Dolor torácico',motivo_consulta:'Dolor de pecho opresivo con sudoración',tiempo_evolucion_valor:'30',tiempo_evolucion_unidad:'minutos',dolor_localizacion:'Tórax',sintomas_asociados:'Sudoración',ant_diabetes:false,antecedentes_otros:'Hipertensión',ta_sistolica:'150',ta_diastolica:'95',frecuencia_cardiaca:'110',frecuencia_respiratoria:'22',saturacion_o2:'94',temperatura:'36,8',estado_conciencia:'Alerta',dolor_intensidad:'8'})},
  {ep:'EP-004815',lv:2,mot:'Dolor abdominal',min:72,relato:'Me duele mucho la panza, acá arriba, desde hace unas 6 horas. Tengo ganas de vomitar y me siento afiebrada. Soy diabética, tomo pastillas.',rev:mk(DEMO)},
  {ep:'EP-004809',lv:3,mot:'Dolor de tobillo',min:100,relato:'Me torcí el tobillo jugando al fútbol, me duele al apoyar.',rev:mk({motivo_categoria:'Trauma',motivo_consulta:'Dolor de tobillo tras torcedura',tiempo_evolucion_valor:'2',tiempo_evolucion_unidad:'horas',dolor_localizacion:'Tobillo derecho',sintomas_asociados:'Le duele al apoyar',ant_diabetes:false,antecedentes_otros:'',ta_sistolica:'120',ta_diastolica:'80',frecuencia_cardiaca:'80',frecuencia_respiratoria:'16',saturacion_o2:'98',temperatura:'36,5',estado_conciencia:'Alerta',dolor_intensidad:'4',br_trauma:true})},
  {ep:'EP-004806',lv:4,mot:'Control de curación',min:150,relato:'Vengo a que me miren la herida de la mano, me la hicieron hace tres días.',rev:mk({motivo_categoria:'Otro',motivo_consulta:'Control de herida en la mano',tiempo_evolucion_valor:'3',tiempo_evolucion_unidad:'días',dolor_localizacion:'Mano izquierda',sintomas_asociados:'',ant_diabetes:false,antecedentes_otros:'',ta_sistolica:'118',ta_diastolica:'76',frecuencia_cardiaca:'72',frecuencia_respiratoria:'14',saturacion_o2:'99',temperatura:'36,4',estado_conciencia:'Alerta',dolor_intensidad:'1'})}
];
let escPending=null;
function commit(lv){
  if(lv==null)return;
  let w=WAIT.find(x=>x.ep===st.ep);
  if(w){w.lv=lv;w.min=0;w.reeval=!!st.prev;w.rev=JSON.parse(JSON.stringify(st.rev));w.esc=false}
  else WAIT.push({ep:st.ep,lv,mot:st.rev.motivo_categoria||'Sin categoría',min:0,relato:$('#caso').value,rev:JSON.parse(JSON.stringify(st.rev))});
}
function clock(w){
  if(w.lv===0)return '<span class="clock over"><span class="ct">ROJO · atención inmediata</span><span class="bar"><i></i></span></span>';
  const T=TARGET[w.lv],rem=T-w.min,pct=Math.max(0,Math.min(100,100*w.min/T)),cls=rem<0?' over':(rem<=T*0.25?' warn':'');
  return '<span class="clock'+cls+'"><span class="ct">'+(rem>=0?'⏱ Reevaluar en '+fmtMin(rem):'⏱ Vencido hace '+fmtMin(-rem)+' · reevaluar')+'</span><span class="bar"><i style="width:'+pct+'%"></i></span></span>';
}
function renderWait(){
  const q=($('#epSearch').value||'').trim().toUpperCase();
  const rows=WAIT.filter(w=>!q||w.ep.includes(q)).sort((a,b)=>a.lv-b.lv||b.min-a.min);
  $('#wCount').textContent=WAIT.length+' pacientes';
  const ro=st.user&&st.user.rol==='auditor';
  $('#wList').innerHTML=rows.map(w=>{const L=LEVELS[w.lv],over=w.lv>0&&w.min>TARGET[w.lv];
    return '<div class="wrow"><span class="wc" style="background:var('+L[1]+');color:'+L[2]+'">'+L[0]+'</span><span class="wep">'+w.ep+'</span><span class="wm">'+esc(w.mot)+'</span><span class="wt">'+(w.min?'en espera '+fmtMin(w.min):'recién clasificado')+'</span>'+clock(w)+'<span class="wf">'+(over?'<span class="st bad">Superó '+TARGET[w.lv]+' min</span>':'')+(w.reeval?'<span class="st fix">Reevaluado</span>':'')+(w.esc?'<span class="st bad">Escalado manual · deterioro en espera</span>':'')+'</span><span class="wa">'+(ro?'<span class="hint">Solo lectura (auditoría)</span>':w.lv>0?'<button type="button" class="btn sm" data-re="'+w.ep+'">Reevaluar</button><button type="button" class="btn sm esc'+(escPending===w.ep?' armed':'')+'" data-esc="'+w.ep+'">'+(escPending===w.ep?'Confirmar ROJO':'Escalar a ROJO')+'</button>':'<span class="hint">Atención inmediata</span>')+'</span></div>'}).join('')||'<div class="hint">No hay episodios con ese código.</div>';
}
$('#epSearch').addEventListener('input',renderWait);
$('#fastT').addEventListener('change',e=>st.fast=e.target.checked);
setInterval(()=>{if(!st.fast)return;WAIT.forEach(w=>w.min++);if(st.screen==='espera')renderWait()},1000);
$('#wList').addEventListener('click',e=>{
  const re=e.target.closest('[data-re]'),es=e.target.closest('[data-esc]');
  if(re){const w=WAIT.find(x=>x.ep===re.dataset.re);st.ep=w.ep;st.prev={lv:w.lv,min:w.min};st.rev=JSON.parse(JSON.stringify(w.rev));st.disc={};$('#caso').value=w.relato||'';st.insuf=false;st.manual=false;escPending=null;resetDecision();go('revision');return}
  if(es){const ep=es.dataset.esc;if(escPending===ep){const w=WAIT.find(x=>x.ep===ep);w.lv=0;w.esc=true;w.min=0;escPending=null}else escPending=ep;renderWait()}
});

/* Acceso (demo: en el sistema real, usuarios locales con contraseña cifrada) */


/* ===== Asistente IA (chat sobre la sugerencia) =====
   HOY: respuestas SIMULADAS armadas con los datos del caso.
   DESPUÉS: preguntarIA() llama a la ruta que publique Maricel (a acordar en docs/contrato_api.md),
   enviando la pregunta + episodio + datos revisados + sugerencia. El texto que vuelva se muestra igual. */
const CHAT_API=null;            // ej.: '/api/consulta' cuando exista
const USAR_VOZ_REAL=false;      // true = reconocimiento de voz del navegador (envía audio a Google; solo casos ficticios)
const AVISO='\n\n(Simulación. La decisión es del profesional.)';
function respuestaSimulada(q){
  const t=q.toLowerCase(),c=calcSug(),L=LEVELS[SUG][0];
  const falt=missing().map(k=>{const f=byK(k);return f?f.l:k});
  if(/diagn|tratamiento|medicaci|remedio|dosis|qu[eé] (le )?(doy|damos|indico)/.test(t))
    return 'No puedo diagnosticar ni indicar tratamientos. Solo explico de dónde sale la prioridad sugerida. Para eso, consultá al médico de guardia.';
  if(/falt|sin dato|medir|complet/.test(t))
    return falt.length?'Faltan '+falt.length+' datos: '+falt.join(', ')+'.\nSi los cargás en Medición, la sugerencia se recalcula.':'No falta ningún dato obligatorio.';
  if(/sub|empeor|m[aá]s urgente|cambiar|naranja|rojo/.test(t)){
    if(SUG===0)return 'Ya está en '+L+', la prioridad más alta.';
    const up=LEVELS[SUG-1][0],it=(DISC[diag()][SUG-1]||[]).map(x=>'• '+x[0]).join('\n');
    return 'Pasaría a '+up+' si se cumple alguno de estos (guía de ejemplo):\n'+it;}
  if(/fuente|gu[ií]a|de d[oó]nde|p[aá]gina|manchester/.test(t))
    return 'Sale de la guía '+GUIA_VER+', diagrama «'+diagName()+'», nivel '+L+'.\nNo es la guía del hospital: es de ejemplo para el prototipo.';
  if(/tiempo|esper|cu[aá]nto|minutos/.test(t))
    return 'Para '+L+' el tiempo de ejemplo es: '+DESC[SUG]+'.\nLos tiempos reales salen de la guía del hospital.';
  if(/por ?qu[eé]|motivo|raz[oó]n|color|prioridad/.test(t)){
    const r=[...c.R.map(x=>'• Regla: '+x.t),...c.C.map(x=>'• Confirmado: '+x.t),...c.M.why.map(x=>'• Del relato: '+x)];
    return 'Sugiero '+L+' por:\n'+r.join('\n')+(c.rl<c.M.lv?'\nUna regla de seguridad no deja bajar el color.':'');}
  return 'Puedo explicarte por qué se sugirió '+L+', qué datos faltan, qué lo haría subir o de qué guía sale. Probá con alguna de esas preguntas.';
}
async function preguntarIA(q){
  if(!CHAT_API){await new Promise(r=>setTimeout(r,600));return respuestaSimulada(q)+AVISO}
  const r=await fetch(CHAT_API,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',
    body:JSON.stringify({pregunta:q,episodio:st.ep,datos:st.rev,sugerencia:LEVELS[SUG][0]})});
  if(!r.ok)throw new Error(r.status);
  return (await r.json()).respuesta;
}
function addMsg(txt,who){const d=document.createElement('div');d.className='msg '+who;d.textContent=txt;$('#chatMsgs').appendChild(d);$('#chatMsgs').scrollTop=1e9;return d}
let chatBusy=false,chatEp=null;
async function enviarChat(q){
  q=q.trim();if(!q||chatBusy)return;chatBusy=true;$('#chatTxt').value='';
  addMsg(q,'yo');const w=addMsg('Pensando…','ia typing');
  try{w.textContent=await preguntarIA(q)}catch(e){w.textContent='No pude responder ('+e.message+'). Tu pregunta no se perdió: probá de nuevo.'}
  w.classList.remove('typing');chatBusy=false;$('#chatTxt').focus();
}
function abrirChat(on){
  $('#chat').hidden=!on;$('#chatBtn').setAttribute('aria-expanded',on);
  if(on&&chatEp!==st.ep){$('#chatMsgs').innerHTML='';chatEp=st.ep}
  if(on){if(!$('#chatMsgs').children.length)addMsg('Hola. Puedo explicarte la sugerencia '+LEVELS[SUG][0]+' de '+st.ep+'. Preguntame lo que necesites, escribiendo o por voz.'+AVISO,'ia');$('#chatTxt').focus()}
}
$('#chatBtn').addEventListener('click',()=>abrirChat($('#chat').hidden));
$('#chatX').addEventListener('click',()=>abrirChat(false));
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('#chat').hidden)abrirChat(false)});
$('#chatForm').addEventListener('submit',e=>{e.preventDefault();enviarChat($('#chatTxt').value)});
$('#chatSug').addEventListener('click',e=>{if(e.target.tagName==='BUTTON')enviarChat(e.target.textContent)});
/* Voz: simulada por defecto (igual que el dictado del Ingreso) */
let chatRec=null,chatMicT=null;
$('#chatMic').addEventListener('click',()=>{
  const b=$('#chatMic'),on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',on);
  if(!on){if(chatRec)chatRec.stop();clearTimeout(chatMicT);return}
  const SRc=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(USAR_VOZ_REAL&&SRc){chatRec=new SRc();chatRec.lang='es-AR';
    chatRec.onresult=e=>{$('#chatTxt').value=e.results[0][0].transcript};
    chatRec.onend=()=>{b.setAttribute('aria-pressed','false');enviarChat($('#chatTxt').value)};
    chatRec.onerror=()=>{b.setAttribute('aria-pressed','false')};chatRec.start();return}
  $('#chatTxt').value='Escuchando… (simulado)';
  chatMicT=setTimeout(()=>{b.setAttribute('aria-pressed','false');$('#chatTxt').value='';enviarChat('¿Qué datos faltan?')},1500);
});

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
(async function iniciarSesion(){
  st.user=await TriageAPI.sesion();
  if(!st.user){location.href='index.html';return}
  const etiqueta=st.user.modo==='real'?'sesión del servidor':'acceso simulado';
  $('#userChip').hidden=false;$('#userChip').innerHTML='<b>'+esc(st.user.u)+'</b> · '+esc(st.user.nom)+' · '+etiqueta+' <button type="button" class="linkbtn" id="logout">Salir</button>';
  $('#userChip').addEventListener('click',e=>{if(e.target.id==='logout')salir()});
  go(st.user.rol==='auditor'?'espera':'ingreso');
})();