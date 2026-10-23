/* frontend/sugerencia.js · Tarjeta de sugerencia (A09) · Pantalla 3.
   - Color SIMULADO con reglas de seguridad y de ejemplo (no es la guía del HRRG): reglas(), medgemma(), calcSug().
     Cuando estén las guías aprobadas (D09) y la autorización del HRRG, acá se reemplaza por la respuesta validada del backend.
   - "Por qué", fuente, qué lo haría subir, decisión del profesional (aceptar / modificar / rechazar / manual)
     y su guardado en el servidor.
   - Chat "Consultar a la IA" (simulado sin servidor; con servidor lo reemplaza js/chat_ia.js).
   Se carga DESPUÉS de formulario.js (usa st, $, esc, LEVELS…) y antes de espera.js. */
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
/* Explicación clínica comprensible (pedido del documento del proyecto): en vez de listar valores sueltos,
   agrupa los que van juntos en una frase que dice qué indican (p. ej. "SpO₂ 88 % y taquipnea: posible compromiso
   respiratorio"). Los umbrales y niveles son los mismos de antes: solo cambia cómo se explica. */
function reglas(){
  const r=st.rev,n=k=>r[k]===''||r[k]==null?null:num(r[k]),out=[];
  const add=(lv,t)=>out.push({lv,t});
  const lista=a=>a.length<2?a[0]:a.slice(0,-1).join(', ')+' y '+a[a.length-1];
  /* Neurológico */
  if(r.br_convulsion)add(0,'Convulsión activa: compromiso neurológico agudo');
  if(n('glasgow')!=null&&n('glasgow')<=8)add(0,'Glasgow '+r.glasgow+': conciencia muy deprimida, riesgo para la vía aérea');
  else if((r.estado_conciencia&&r.estado_conciencia!=='Alerta')||(n('glasgow')!=null&&n('glasgow')<15))
    add(1,'Alteración del nivel de conciencia ('+(n('glasgow')!=null&&n('glasgow')<15?'Glasgow '+r.glasgow:r.estado_conciencia)+'): posible compromiso neurológico');
  /* Respiratorio: SpO₂ baja, FR alterada y disnea se explican juntas */
  const resp=[];
  if(n('saturacion_o2')!=null&&n('saturacion_o2')<90)resp.push('SpO₂ '+r.saturacion_o2+' %');
  if(n('frecuencia_respiratoria')!=null&&n('frecuencia_respiratoria')>30)resp.push('taquipnea (FR '+r.frecuencia_respiratoria+' rpm)');
  if(n('frecuencia_respiratoria')!=null&&n('frecuencia_respiratoria')<8)resp.push('bradipnea (FR '+r.frecuencia_respiratoria+' rpm)');
  if(r.br_disnea)resp.push('dificultad para respirar');
  if(resp.length){const t=lista(resp);add(1,t.charAt(0).toUpperCase()+t.slice(1)+': posible compromiso respiratorio')}
  /* Circulatorio: sangrado, hipotensión y FC alterada */
  const hipo=n('ta_sistolica')!=null&&n('ta_sistolica')<90,ta='TA '+r.ta_sistolica+'/'+(r.ta_diastolica||'—');
  const fc=n('frecuencia_cardiaca')!=null&&(n('frecuencia_cardiaca')>130||n('frecuencia_cardiaca')<40)?(n('frecuencia_cardiaca')>130?'taquicardia':'bradicardia')+' (FC '+r.frecuencia_cardiaca+' lpm)':null;
  if(r.br_sangrado&&hipo)add(0,'Sangrado con hipotensión ('+ta+(fc?', FC '+r.frecuencia_cardiaca+' lpm':'')+'): posible shock por pérdida de sangre');
  else{
    if(r.br_sangrado)add(1,'Sangrado evidente: riesgo de pérdida de volumen');
    const circ=[];if(hipo)circ.push('hipotensión ('+ta+')');if(fc)circ.push(fc);
    if(circ.length){const t=lista(circ);add(1,t.charAt(0).toUpperCase()+t.slice(1)+(hipo?': posible compromiso circulatorio (shock)':': alteración del ritmo o compromiso circulatorio'))}
  }
  /* Otros */
  if(r.ant_inmuno&&n('temperatura')!=null&&n('temperatura')>=38)add(1,'Fiebre ('+r.temperatura+' °C) en paciente inmunosuprimido: riesgo de infección grave');
  if(n('dolor_intensidad')!=null&&n('dolor_intensidad')>=8)add(1,'Dolor intenso ('+r.dolor_intensidad+'/10)');
  return out;
}
/* Sugerencia simulada de MedGemma (en el sistema real: JSON validado del modelo con RAG sobre la guía) */
function medgemma(){
  const r=st.rev,n=k=>r[k]===''||r[k]==null?null:num(r[k]),why=[];let lv=3;
  const d=n('dolor_intensidad');
  /* El motivo va siempre primero: categoría + lo que dijo el paciente + tiempo de evolución */
  const cat=(r.motivo_categoria||'').trim(),mc=(r.motivo_consulta||'').trim();
  if(cat||mc){
    const det=mc&&mc.toLowerCase()!==cat.toLowerCase()?mc.toLowerCase():'';
    const tpo=r.tiempo_evolucion_valor?' (hace '+r.tiempo_evolucion_valor+' '+r.tiempo_evolucion_unidad+')':'';
    why.push('Motivo: '+(cat&&det?cat+' — '+det:(cat||mc))+tpo);
  }
  const base=why.length;
  if(d!=null&&d>=5&&d<8){lv=2;why.push('Dolor moderado ('+d+'/10)')}
  const t=n('temperatura');if(t!=null&&t>=37.5&&t<38.5){lv=Math.min(lv,2);why.push('Febrícula ('+r.temperatura+' °C)')}
  if(t!=null&&t>=38.5){lv=Math.min(lv,2);why.push('Fiebre ('+r.temperatura+' °C)')}
  if(r.ant_diabetes)why.push('Diabetes'+(n('glucemia')>=250?' con glucemia '+r.glucemia+' mg/dL':''));
  if(r.sintomas_asociados)why.push('Refiere: '+r.sintomas_asociados.toLowerCase());
  if(d!=null&&d<=2&&!(t>=37.5)&&lv===3)lv=4;
  if(why.length===base)why.push('Sin discriminadores de mayor urgencia en los datos');
  return {lv,why};
}
function calcSug(){
  const R=reglas(),M=medgemma(),rl=R.length?Math.min(...R.map(x=>x.lv)):9;
  const C=Object.entries(st.disc).filter(([k,v])=>v==='si').map(([k])=>{const [lv,t]=k.split('|');return {lv:+lv,t}});
  const cl=C.length?Math.min(...C.map(x=>x.lv)):9;
  /* Reevaluación: el color anterior (aceptado o modificado por el profesional) es un piso, como las reglas.
     Para bajar la prioridad hay que usar Modificar con motivo. */
  const pl=st.prev&&st.prev.lv!=null?st.prev.lv:9,fin=Math.min(rl,M.lv,cl,pl);
  return {R,M,C,rl,cl,pl,fin};
}
function renderCard(){
  const c=calcSug();SUG=c.fin;const L=LEVELS[SUG];
  $('#tcPrev').hidden=!st.prev;if(st.prev)$('#tcPrev').textContent='Reevaluación · Antes: '+LEVELS[st.prev.lv][0]+' (hace '+fmtMin(st.prev.min)+')  →  Ahora: '+L[0];
  $('#triageCard').style.setProperty('--mc','var('+L[1]+')');$('#triageCard').style.setProperty('--mi',L[2]);
  $('#tcName').textContent=L[0];$('#tcDesc').textContent=DESC[SUG]+' [tiempo de ejemplo]';
  $('#tcOrigin').innerHTML=c.rl<c.M.lv?'<b>Color fijado por regla de seguridad.</b><span class="old">La simulación sugería '+LEVELS[c.M.lv][0]+'; la regla no permite bajar.</span><span class="prov">Reglas provisorias</span>'
    :(c.R.length?'<b>Simulación con reglas de ejemplo.</b><span class="old">Coincide o supera las reglas de seguridad.</span>':'<b>Simulación con reglas de ejemplo.</b><span class="old">Reglas de seguridad: sin alertas.</span>');
  if(c.cl<=c.rl&&c.cl<c.M.lv)$('#tcOrigin').innerHTML='<b>Color fijado por discriminador confirmado por el profesional.</b><span class="old">La simulación sugería '+LEVELS[c.M.lv][0]+'.</span>';
  if(c.pl<Math.min(c.rl,c.M.lv,c.cl))$('#tcOrigin').innerHTML='<b>Color mantenido por la clasificación anterior.</b><span class="old">Con los datos nuevos la sugerencia sería '+LEVELS[Math.min(c.rl,c.M.lv,c.cl)][0]+'. Para bajar la prioridad, usá Modificar con motivo.</span>';
  $('#tcWhy').innerHTML=(c.pl<9?'<li><span class="src g">ANTES</span><span>Clasificación anterior: '+LEVELS[c.pl][0]+'</span></li>':'')+c.R.map(x=>'<li><span class="src r">REGLA</span><span>'+esc(x.t)+'</span></li>').join('')+c.C.map(x=>'<li><span class="src g">GUÍA</span><span>Confirmado: '+esc(x.t)+'</span></li>').join('')+c.M.why.map(t=>'<li><span class="src ia">IA</span><span>'+esc(t)+'</span></li>').join('');
  renderFuente();renderSubir();pintarDecision();
}
/* Si el profesional modificó o rechazó la sugerencia, el color grande muestra la clasificación final.
   La sugerencia original queda escrita debajo (trazabilidad). */
function pintarDecision(){
  const ceja=$('#triageCard .eyebrow'),tag=$('#triageCard .ia-tag'),n=ceja.querySelector('.n'),nH=n?' '+n.outerHTML:'';
  const fl=(st.decision==='modificar'||st.decision==='rechazar')&&st.level!=null?st.level:null;
  if(fl==null){
    if(!/Prioridad|MedGemma|Sin IA/.test(ceja.textContent))ceja.innerHTML='Prioridad de ejemplo · simulada'+nH;
    tag.textContent=st.decision==='aceptar'?'Sugerencia aceptada':'Sugerencia · requiere validación';return}
  const L=LEVELS[fl],acc=st.decision==='modificar'?'modificada':'rechazada';
  $('#triageCard').style.setProperty('--mc','var('+L[1]+')');$('#triageCard').style.setProperty('--mi',L[2]);
  $('#tcName').textContent=L[0];$('#tcDesc').textContent=DESC[fl]+' [tiempo de ejemplo]';
  ceja.innerHTML='Clasificación final · decidida por el profesional'+nH;tag.textContent='Decisión registrada';
  if(st.prev)$('#tcPrev').textContent='Reevaluación · Antes: '+LEVELS[st.prev.lv][0]+' (hace '+fmtMin(st.prev.min)+')  →  Ahora: '+L[0];
  $('#tcOrigin').innerHTML='<b>Sugerencia '+LEVELS[SUG][0]+' '+acc+' a '+L[0]+' por el profesional.</b><span class="old">Motivo: '+esc($('#motivo').value||'—')+'</span>';
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
$('#subir').addEventListener('click',e=>{const b=e.target.closest('.yn button');if(!b)return;const k=b.parentElement.dataset.key;
  st.disc[k]=st.disc[k]===b.dataset.a?undefined:b.dataset.a;if(st.disc[k]===undefined)delete st.disc[k];resetDecision();renderCard();renderReg()});
$('#levels').innerHTML=LEVELS.map((L,i)=>'<button type="button" class="lvl" data-l="'+i+'" aria-pressed="false" style="background:var('+L[1]+');color:'+L[2]+'" title="'+L[3]+'">'+L[0]+'</button>').join('');
document.querySelectorAll('[data-d]').forEach(b=>b.addEventListener('click',()=>{
  const d=b.dataset.d;st.decision=null;st.level=null;renderCard();
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
  renderCard();renderReg();
});
$('#manual').addEventListener('click',()=>{st.insuf=false;st.manual=true;renderResumen()});
function resetDecision(){st.decision=null;st.level=null;st.mlv=null;
  document.querySelectorAll('[data-d]').forEach(x=>x.setAttribute('aria-pressed','false'));document.querySelectorAll('.lvl').forEach(x=>x.setAttribute('aria-pressed','false'));
  $('#okMsg').hidden=true;$('#motivoForm').hidden=true;$('#modForm').hidden=true;$('#mOk').hidden=true;$('#mReg').disabled=true;}
/* Clasificación manual sin IA */
$('#mLevels').innerHTML=LEVELS.map((L,i)=>'<button type="button" class="lvl" data-m="'+i+'" aria-pressed="false" style="background:var('+L[1]+');color:'+L[2]+'">'+L[0]+'</button>').join('');
$('#mLevels').addEventListener('click',e=>{const b=e.target.closest('[data-m]');if(!b)return;st.mlv=+b.dataset.m;$('#mLevels').querySelectorAll('.lvl').forEach(x=>x.setAttribute('aria-pressed',x===b));$('#mReg').disabled=false});
$('#mReg').addEventListener('click',()=>{commit(st.mlv);$('#mOk').hidden=false;$('#mOk').innerHTML='<b>Registrado.</b> Clasificación manual '+LEVELS[st.mlv][0]+', sin asistencia IA.';renderReg()});
/* Chat "Consultar a la IA": con servidor responde MedGemma local (js/chat_ia.js), no la simulación. */
if(TriageAPI.MODO_REAL&&$('.chat-warn'))$('.chat-warn').innerHTML='<b>MedGemma local.</b> Responde sobre los datos de este caso. No diagnostica ni indica tratamientos: esas preguntas se bloquean. La decisión es del profesional.';
/* ===== Decisión del profesional (ruta de Maricel: POST …/decision) =====
   Se guarda como un evento nuevo; las anteriores no se borran.
   Mapeo de la pantalla al contrato:
   - Aceptar            -> "aceptada", color sugerido
   - Modificar          -> "modificada", color elegido + motivo
   - Rechazar           -> "modificada" (el backend usa "rechazada" solo SIN color; acá el profesional
                           elige un color manual), con el motivo "Sugerencia rechazada…"
   - Clasificar sin IA  -> "modificada", color manual, motivo "Clasificación manual sin asistencia IA"
   - Escalar a ROJO     -> "modificada", ROJO, motivo "Escalado manual por deterioro en espera" */
function textoMotivo(){
  const m=$('#motivo').value,d=($('#detalle').value||'').trim();
  return [m,d].filter(Boolean).join('. ');
}
/* Discriminadores de la guía que el profesional respondió (Sí/No en "Pasaría a…"): van a la decisión guardada,
   así quedan en el historial del servidor y no solo en el registro de la pantalla. */
function textoDiscriminadores(){
  const si=[],no=[];
  Object.entries(st.disc).forEach(([k,v])=>{const t=k.split('|')[1];if(v==='si')si.push(t);else if(v==='no')no.push(t)});
  return [si.length?'Discriminadores confirmados: '+si.join(', ')+'.':'',no.length?'Descartados: '+no.join(', ')+'.':''].filter(Boolean).join(' ');
}
function decisionActual(lv){
  const d=decisionBase(lv),disc=st.manual?'':textoDiscriminadores();
  if(disc)d.motivo=(d.motivo?d.motivo.replace(/\.?$/,'. '):'')+disc;
  d.motivo=d.motivo.slice(0,1000);
  return d;
}
function decisionBase(lv){
  if(st.manual)return {decision:'modificada',color:LEVELS[lv][0],motivo:'Clasificación manual sin asistencia IA.'};
  if(st.decision==='aceptar')return {decision:'aceptada',color:LEVELS[lv][0],motivo:''};
  if(st.decision==='rechazar')return {decision:'modificada',color:LEVELS[lv][0],motivo:('Sugerencia rechazada; clasificación manual. '+textoMotivo()).trim()};
  return {decision:'modificada',color:LEVELS[lv][0],motivo:textoMotivo()||'Criterio clínico del profesional'};
}
async function versionDecision(ep){
  const r=await TriageAPI.consultarEpisodio(ep);
  if(!r.ok)return null;
  const ult=(r.datos.episodio.eventos||[]).filter(e=>e.tipo==='DECISION_REGISTRADA').pop();
  return ult&&ult.datos?ult.datos.version:0;
}
async function guardarDecision(w,d){
  if(!TriageAPI.MODO_REAL||!w.srv||!w.srv.ep||!d)return;
  const v=await versionDecision(w.ep);
  if(v==null){w.aviso='No se pudo guardar la decisión: no se pudo leer el episodio.';return}
  const r=await TriageAPI.registrarDecision(w.ep,d.decision,d.color,d.motivo,v);
  if(r.estado===401){location.href='index.html';return}
  if(!r.ok){w.aviso='No se guardó la decisión en el servidor: '+(r.datos.mensaje||'error')+'.';if(st.screen==='espera')renderWait();return}
  w.decisionGuardada=true;
  if(st.screen==='resumen')renderHistorial();
}

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

