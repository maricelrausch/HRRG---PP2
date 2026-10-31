/* frontend/sugerencia.js · Tarjeta de sugerencia (A09) · Pantalla 3.
   - Color: el más urgente entre las reglas de la base (motor_reglas.js), MedGemma y la clasificación anterior: calcSug().
     [Dario 30/10] Ya no hay reglas escritas en este archivo: se administran en reglas.html.
     Cuando estén las guías aprobadas (D09) y la autorización del HRRG, acá se reemplaza por la respuesta validada del backend.
   - "Por qué", decisión del profesional (aceptar / modificar / rechazar / manual)
     y su guardado en el servidor.
   - Chat "Consultar a la IA" (simulado sin servidor; con servidor lo reemplaza js/chat_ia.js).
   Se carga DESPUÉS de formulario.js (usa st, $, esc, LEVELS…) y antes de espera.js. */
/* [Dario 30/10] Se sacó la «guía Manchester de EJEMPLO» (lista DISC: discriminadores por diagrama inventados
   por el equipo, escritos en el código). Sin la guía del HRRG no había forma de validarlos y, al tocar «Sí»,
   cambiaban el color. Cuando el hospital mande su adaptación de Manchester se cargan en una tabla, como las
   reglas y los signos vitales. El color sale de: reglas del hospital, MedGemma y la clasificación anterior. */
/* [Dario 30/10] Sugerencia de MedGemma REAL (POST /api/sugerir, backend/ia/medgemma.py → sugerir()).
   Antes era una simulación con umbrales escritos acá (dolor 5–7, febrícula, fiebre): esos umbrales pasaron
   a reglas del hospital (tanda 3 de datos/reglas_semilla.json) y ahora se administran en reglas.html.
   - La respuesta se guarda por caso (datos + relato): si el profesional cambia un dato, se vuelve a consultar.
   - Mientras responde: «Consultando a MedGemma…» y Aceptar desactivado; el color provisorio es el de las reglas.
   - Sin servidor, con la IA apagada o si MedGemma no responde: VERDE de base + reglas del hospital
     (fuente «Sin IA · reglas del hospital»). Las reglas siempre fijan el piso: la IA nunca baja el color. */
const IA_SUG={clave:null,res:null,cargando:null,fallida:null,error:null};
const relatoIA=()=>st.relatoOriginal||($('#caso')?$('#caso').value:'')||'';
const claveIA=()=>JSON.stringify(st.rev)+'|'+relatoIA();
async function pedirSugerenciaIA(clave){
  IA_SUG.cargando=clave;
  try{
    const r=await TriageAPI.pedir('/api/sugerir',{method:'POST',body:JSON.stringify({datos:st.rev,relato:relatoIA(),
      traza:window.HRRGTraza?HRRGTraza.paraPedido(false):null})});
    if(!r.ok)throw new Error((r.datos&&(r.datos.error||r.datos.mensaje))||('HTTP '+r.estado));
    IA_SUG.res=r.datos;IA_SUG.clave=clave;IA_SUG.error=null;
  }catch(e){IA_SUG.fallida=clave;IA_SUG.error=e.message;console.warn('[MedGemma] no respondió:',e.message)}
  finally{IA_SUG.cargando=null;if(st.screen==='resumen')renderCard()}
}
function motivoTexto(){
  const r=st.rev,cat=(r.motivo_categoria||'').trim(),mc=(r.motivo_consulta||'').trim();
  if(!cat&&!mc)return null;
  const det=mc&&mc.toLowerCase()!==cat.toLowerCase()?mc.toLowerCase():'';
  const tpo=r.tiempo_evolucion_valor?' (hace '+r.tiempo_evolucion_valor+' '+r.tiempo_evolucion_unidad+')':'';
  return 'Motivo: '+(cat&&det?cat+' — '+det:(cat||mc))+tpo;
}
/* Devuelve {lv, why, fuente}: fuente = 'ia' | 'cargando' | 'insuf' | 'sin'. lv 3 (VERDE) es la base sin IA. */
function medgemma(){
  const sinIA=why=>({lv:3,why:[motivoTexto(),...why].filter(Boolean),fuente:'sin'});
  if(!TriageAPI.MODO_REAL||!st.ollama||st.manual)return sinIA(['Sin IA: el color sale de las reglas del hospital y del criterio del profesional']);
  const clave=claveIA();
  if(IA_SUG.res&&IA_SUG.clave===clave){
    const j=IA_SUG.res;
    if(j.insuficiente)return {lv:3,why:['MedGemma: datos insuficientes para sugerir un color'],fuente:'insuf'};
    return {lv:Number.isInteger(j.nivel)?j.nivel:2,why:(j.motivos&&j.motivos.length?j.motivos:['MedGemma no detalló motivos']),fuente:'ia',fuentes:j.fuentes||[]};
  }
  if(IA_SUG.fallida===clave)return sinIA(['MedGemma no respondió'+(IA_SUG.error?' ('+IA_SUG.error+')':'')+': se usan solo las reglas del hospital']);
  if(!IA_SUG.cargando)pedirSugerenciaIA(clave);
  return {lv:3,why:['Consultando a MedGemma… (color provisorio con las reglas del hospital)'],fuente:'cargando'};
}
/* ===== Reglas del hospital (propuesta Barby 28/10) =====
   Las carga la Jefatura de Guardia en reglas.html. Se piden al servidor cada vez que se pide una
   sugerencia, así una regla recién activada interviene en el próximo paciente sin recargar nada.
   Fijan un piso (no se puede sugerir menos) y aparecen en el "Por qué" con la marca HRRG.
   Si la Jefatura apaga las "reglas de ejemplo", quedan solo las del hospital (más la IA). */
const REGLAS_HRRG={lista:[],error:null};
async function cargarReglasHospital(){
  if(!TriageAPI.MODO_REAL)return;
  if(typeof cargarTiempos==='function')cargarTiempos();   /* [Dario 29/10 · Etapa C] tiempos por color al día */
  const r=await TriageAPI.reglasActivas();
  if(r.estado===401){location.href='index.html';return}
  if(r.ok){REGLAS_HRRG.lista=r.datos.reglas||[];REGLAS_HRRG.error=null}
  else REGLAS_HRRG.error='No se pudieron leer las reglas del hospital: se usan las últimas conocidas.';
}
function calcSug(){
  const H=window.MotorReglas?MotorReglas.evaluar(REGLAS_HRRG.lista,st.rev):[],hl=H.length?H[0].lv:9;
  /* R y rl quedan vacíos (antes: reglas escritas en el código); se conservan para no cambiar quien los lee. */
  const R=[],M=medgemma(),rl=9;   /* M: MedGemma real (o VERDE de base sin IA) */
  const C=[],cl=9;   /* [Dario 30/10] antes: discriminadores de la guía de ejemplo (se sacaron) */
  /* Reevaluación: el color anterior (aceptado o modificado por el profesional) es un piso, como las reglas.
     Para bajar la prioridad hay que usar Modificar con motivo. */
  const pl=st.prev&&st.prev.lv!=null?st.prev.lv:9,fin=Math.min(rl,M.lv,cl,pl,hl);
  return {R,M,C,H,rl,cl,pl,hl,fin};
}
function renderCard(){
  const c=calcSug();SUG=c.fin;const L=LEVELS[SUG];
  $('#tcPrev').hidden=!st.prev;if(st.prev)$('#tcPrev').textContent='Reevaluación · Antes: '+LEVELS[st.prev.lv][0]+' (hace '+fmtMin(st.prev.min)+')  →  Ahora: '+L[0];
  $('#triageCard').style.setProperty('--mc','var('+L[1]+')');$('#triageCard').style.setProperty('--mi',L[2]);
  $('#tcName').textContent=L[0];$('#tcDesc').textContent=DESC[SUG]+' [tiempo de ejemplo]';
  /* [Dario 30/10] Mientras MedGemma responde (unos segundos) no se muestra un color grande que después cambia:
     tarjeta gris «Analizando…» y, si una regla ya fija un piso, se avisa. Aceptar queda desactivado. */
  if(c.M.fuente==='cargando'){$('#triageCard').style.setProperty('--mc','var(--muted)');$('#triageCard').style.setProperty('--mi','#FFFFFF');
    $('#tcName').textContent='Analizando…';$('#tcDesc').textContent=c.hl<9?'MedGemma revisando · reglas: al menos '+LEVELS[c.hl][0]:'MedGemma revisando el caso';}
  const FUENTE={ia:'Sugerencia de MedGemma con las reglas del hospital.',cargando:'Consultando a MedGemma… (color provisorio con las reglas del hospital)',insuf:'MedGemma: datos insuficientes · color con las reglas del hospital.',sin:'Sin IA · reglas del hospital.'};
  $('#tcOrigin').innerHTML='<b>'+FUENTE[c.M.fuente]+'</b><span class="old">'+(c.H.length?'Coincide o supera las reglas del hospital.':'Reglas del hospital: ninguna se cumple.')+'</span>';
  const ac=document.querySelector('[data-d="aceptar"]');if(ac){ac.disabled=c.M.fuente==='cargando';ac.title=ac.disabled?'Esperá la respuesta de MedGemma':''}
  if(c.hl<9&&c.hl<=Math.min(c.rl,c.cl)&&c.hl<c.M.lv&&c.M.fuente!=='ia')$('#tcOrigin').innerHTML='<b>'+FUENTE[c.M.fuente]+'</b><span class="old">Color fijado por regla del hospital ('+esc(c.H[0].codigo)+').</span>';
  else if(c.hl<9&&c.hl<=Math.min(c.rl,c.cl)&&c.hl<c.M.lv)$('#tcOrigin').innerHTML='<b>Color fijado por regla del hospital ('+esc(c.H[0].codigo)+').</b><span class="old">Sin esa regla la sugerencia sería '+LEVELS[Math.min(c.rl,c.M.lv,c.cl)][0]+'. Se administra en la pantalla de reglas (Jefatura de Guardia).</span>';
  if(c.pl<Math.min(c.rl,c.M.lv,c.cl,c.hl))$('#tcOrigin').innerHTML='<b>Color mantenido por la clasificación anterior.</b><span class="old">Con los datos nuevos la sugerencia sería '+LEVELS[Math.min(c.rl,c.M.lv,c.cl)][0]+'. Para bajar la prioridad, usá Modificar con motivo.</span>';
  $('#tcWhy').innerHTML=(c.pl<9?'<li><span class="src g">ANTES</span><span>Clasificación anterior: '+LEVELS[c.pl][0]+'</span></li>':'')+c.H.map(x=>'<li><span class="src h'+(x.origen==='provisoria'?' prov':'')+'" title="Regla '+esc(x.codigo)+' v'+x.version+'">'+esc(MotorReglas.etiqueta(x.origen,x.validada_por))+'</span><span>'+esc(x.texto)+' <span class="old">('+esc(x.codigo)+' · '+esc(x.color)+' · '+esc(MotorReglas.ORIGEN[x.origen]||x.origen)+' · '+(x.validada_por?'validada por '+esc(x.validada_por):'sin validar')+')</span></span></li>').join('')+(REGLAS_HRRG.error?'<li><span class="src r">AVISO</span><span>'+esc(REGLAS_HRRG.error)+'</span></li>':'')+c.R.map(x=>'<li><span class="src r">REGLA</span><span>'+esc(x.t)+'</span></li>').join('')+c.M.why.map((t,i)=>{if(c.M.fuente!=='ia')return '<li><span class="src g">INFO</span><span>'+esc(t)+'</span></li>';
    /* MedGemma dice de dónde sale cada motivo: lo contó el paciente, lo midió enfermería o es criterio del modelo. */
    const f=(c.M.fuentes||[])[i],et=f==='relato'?'IA · RELATO':f==='medido'?'IA · MEDIDO':'IA';
    return '<li><span class="src ia">'+et+'</span><span>'+esc(t)+'</span></li>'}).join('');
  pintarDecision();
}
/* Si el profesional modificó o rechazó la sugerencia, el color grande muestra la clasificación final.
   La sugerencia original queda escrita debajo (trazabilidad). */
function pintarDecision(){
  const ceja=$('#triageCard .eyebrow'),tag=$('#triageCard .ia-tag'),n=ceja.querySelector('.n'),nH=n?' '+n.outerHTML:'';
  const fl=(st.decision==='modificar'||st.decision==='rechazar')&&st.level!=null?st.level:null;
  if(fl==null){
    ceja.innerHTML=(medgemma().fuente==='ia'?'Prioridad sugerida · MedGemma y reglas':'Prioridad sugerida · reglas del hospital')+nH;   /* [Dario 30/10] */
    tag.textContent=st.decision==='aceptar'?'Sugerencia aceptada':'Sugerencia · requiere validación';return}
  const L=LEVELS[fl],acc=st.decision==='modificar'?'modificada':'rechazada';
  $('#triageCard').style.setProperty('--mc','var('+L[1]+')');$('#triageCard').style.setProperty('--mi',L[2]);
  $('#tcName').textContent=L[0];$('#tcDesc').textContent=DESC[fl]+' [tiempo de ejemplo]';
  ceja.innerHTML='Clasificación final · decidida por el profesional'+nH;tag.textContent='Decisión registrada';
  if(st.prev)$('#tcPrev').textContent='Reevaluación · Antes: '+LEVELS[st.prev.lv][0]+' (hace '+fmtMin(st.prev.min)+')  →  Ahora: '+L[0];
  $('#tcOrigin').innerHTML='<b>Sugerencia '+LEVELS[SUG][0]+' '+acc+' a '+L[0]+' por el profesional.</b><span class="old">Motivo: '+esc(textoMotivo()||'—')+'</span>';
}
/* [Barby 30/10] Solo los 4 colores clínicos. El AZUL se dejó de ofrecer (recomendación de Navoni, HRRG):
   los casos policiales, judiciales o con custodia van como "Condición especial" en el Ingreso.
   LEVELS conserva el AZUL solo para mostrar decisiones viejas que lo tengan. */
$('#levels').innerHTML=LEVELS.slice(0,4).map((L,i)=>'<button type="button" class="lvl" data-l="'+i+'" aria-pressed="false" style="background:var('+L[1]+');color:'+L[2]+'" title="'+L[3]+'">'+L[0]+'</button>').join('');
/* [Dario 30/10] Si ya se registró un color MÁS urgente (p. ej. se modificó a ROJO), «Aceptar» no puede volver a la
   sugerencia (NARANJA) sin motivo: bajar la prioridad se hace con Modificar, que pide motivo y queda como discrepancia. */
const refBajar=()=>st.registrado!=null?Math.min(SUG,st.registrado):SUG;
document.querySelectorAll('[data-d]').forEach(b=>b.addEventListener('click',()=>{
  const d=b.dataset.d;
  if(d==='aceptar'&&st.registrado!=null&&SUG>st.registrado){
    $('#okMsg').hidden=false;$('#okMsg').innerHTML='<b>Ya registraste '+LEVELS[st.registrado][0]+'.</b> Para bajar a '+LEVELS[SUG][0]+' usá <b>Modificar</b> e indicá el motivo: queda registrado como discrepancia.';
    return}
  st.decision=null;st.level=null;renderCard();
  document.querySelectorAll('[data-d]').forEach(x=>x.setAttribute('aria-pressed',x===b));
  document.querySelectorAll('.lvl').forEach(x=>x.setAttribute('aria-pressed','false'));
  $('#okMsg').hidden=true;$('#modForm').hidden=d==='aceptar';$('#motivoForm').hidden=d==='aceptar';$('#lowerBox').hidden=true;
  $('#motivo').value='';$('#detalle').value='';$('#lowerOk').checked=false;
  if(d==='aceptar'){st.decision='aceptar';commit(SUG);$('#okMsg').hidden=false;$('#okMsg').innerHTML='<b>Registrado.</b> Clasificación '+LEVELS[SUG][0]+' aceptada por el profesional.'+(st.prev?' Actualizado en En espera.':'');renderReg()}
  else{$('#registrar').dataset.d=d;updReg()}
}));
$('#levels').addEventListener('click',e=>{const b=e.target.closest('.lvl');if(!b)return;st.level=+b.dataset.l;
  document.querySelectorAll('.lvl').forEach(x=>x.setAttribute('aria-pressed',x===b));
  $('#lowerTxt').textContent='Confirmo asignar una prioridad menor que la sugerida. Queda registrada como discrepancia.';
  $('#lowerOk').checked=false;$('#lowerBox').hidden=!(st.level>refBajar());updReg()});
function updReg(){
  const d=$('#registrar').dataset.d;let ok=!!$('#motivo').value;
  if(d==='modificar')ok=ok&&st.level!=null&&(st.level!==SUG||(st.registrado!=null&&st.level!==st.registrado));
  if(d==='rechazar')ok=ok&&st.level!=null;
  if(st.level>refBajar())ok=ok&&$('#lowerOk').checked;
  $('#registrar').disabled=!ok;
}
$('#motivo').addEventListener('change',updReg);$('#lowerOk').addEventListener('change',updReg);
const notaMenor=()=>st.level>refBajar()?' · Discrepancia registrada.':'';
$('#registrar').addEventListener('click',()=>{
  const d=$('#registrar').dataset.d,nota=notaMenor(),antes=st.registrado;st.decision=d;commit(st.level);   /* nota antes de commit: compara con lo registrado antes */$('#motivoForm').hidden=true;$('#modForm').hidden=true;$('#okMsg').hidden=false;
  $('#okMsg').innerHTML=d==='modificar'?'<b>Registrado.</b> '+(antes!=null&&antes!==st.level?'Clasificación cambiada de '+LEVELS[antes][0]+' a '+LEVELS[st.level][0]:'Sugerencia '+LEVELS[SUG][0]+' modificada a '+LEVELS[st.level][0])+'. Motivo: '+esc(textoMotivo())+nota:'<b>Registrado.</b> Sugerencia rechazada. Clasificación manual: '+LEVELS[st.level][0]+'. Motivo: '+esc(textoMotivo())+nota;
  renderCard();renderReg();
});
$('#manual').addEventListener('click',()=>{st.insuf=false;st.manual=true;renderResumen()});
function resetDecision(){st.decision=null;st.level=null;st.mlv=null;
  $('#motivo').value='';$('#detalle').value='';$('#lowerOk').checked=false;   /* [Dario 30/10] el motivo no pasa de un caso a otro */
  document.querySelectorAll('[data-d]').forEach(x=>x.setAttribute('aria-pressed','false'));document.querySelectorAll('.lvl').forEach(x=>x.setAttribute('aria-pressed','false'));
  $('#okMsg').hidden=true;$('#motivoForm').hidden=true;$('#modForm').hidden=true;$('#mOk').hidden=true;$('#mReg').disabled=true;}
/* Clasificación manual sin IA */
$('#mLevels').innerHTML=LEVELS.slice(0,4).map((L,i)=>'<button type="button" class="lvl" data-m="'+i+'" aria-pressed="false" style="background:var('+L[1]+');color:'+L[2]+'">'+L[0]+'</button>').join('');
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
/* Reglas del hospital que intervinieron (código y versión): quedan en la decisión guardada. */
function textoReglasHospital(){
  const H=window.MotorReglas?MotorReglas.evaluar(REGLAS_HRRG.lista,st.rev):[];
  return H.length?'Reglas HRRG aplicadas: '+H.map(x=>x.codigo+' v'+x.version+' ('+x.color+', '+x.origen+')').join(', ')+'.':'';
}
function decisionActual(lv){
  const d=decisionBase(lv),disc=st.manual?'':textoReglasHospital();
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
    const up=LEVELS[SUG-1][0],it=REGLAS_HRRG.lista.filter(r=>MotorReglas.NIVEL[r.color]<SUG).map(r=>'• '+r.nombre+' ('+r.color+')').join('\n');
    return it?'Pasaría a '+up+' o más si se cumple alguna de estas reglas del hospital:\n'+it:'No hay reglas del hospital activas que suban el color.';}
  if(/fuente|gu[ií]a|de d[oó]nde|p[aá]gina|manchester/.test(t))
    return 'Sale de las reglas del hospital (pantalla de reglas) y de MedGemma.\nTodavía no hay una guía oficial del HRRG cargada.';
  if(/tiempo|esper|cu[aá]nto|minutos/.test(t))
    return 'Para '+L+' el tiempo de ejemplo es: '+DESC[SUG]+'.\nLos tiempos reales salen de la guía del hospital.';
  if(/por ?qu[eé]|motivo|raz[oó]n|color|prioridad/.test(t)){
    const r=[...c.H.map(x=>'• Regla del hospital '+x.codigo+': '+x.texto),...c.M.why.map(x=>(c.M.fuente==='ia'?'• MedGemma: ':'• ')+x)];
    return 'Sugiero '+L+' por:\n'+r.join('\n')+(c.hl<c.M.lv?'\nUna regla del hospital no deja bajar el color.':'');}
  return 'Puedo explicarte por qué se sugirió '+L+', qué datos faltan, qué lo haría subir o de dónde sale. Probá con alguna de esas preguntas.';
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
