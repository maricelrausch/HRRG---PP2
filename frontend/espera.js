/* frontend/espera.js · En espera y reevaluación (A10) · Pantalla 4.
   - Lista de pacientes clasificados: con servidor sale de /api/demo/espera (persistente, la ven todas las compus);
     sin servidor (doble clic) usa pacientes de ejemplo.
   - Buscar por código de episodio o DNI (DNI completo → /api/demo/pacientes/buscar, no crea pacientes).
   - Reevaluar, Escalar a ROJO con motivo obligatorio, Finalizar (atendido).
   - Auditor (solo lectura): ve el DNI, "Ver historial" de cada episodio, buscando un DNI completo
     todas las atenciones del paciente (incluidas las finalizadas), y el "Historial de casos" con todos los episodios.
   - commit(): pasa el caso decidido en la Sugerencia a la lista y guarda estado + decisión en el servidor.
   Se carga DESPUÉS de formulario.js y sugerencia.js. */
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
let escPending=null,finPending=null;
/* Auditoría (solo lectura): historial completo por episodio y todas las atenciones del paciente buscado por DNI. */
const HIST_ABIERTO=new Set(),HIST_HTML={},PAC_ATENC={};
function htmlListaAtenciones(lista,titulo){
  if(!lista)return '<div class="prev"><b>'+titulo+':</b> cargando…</div>';
  if(!lista.length)return '<div class="prev"><b>'+titulo+':</b> no hay otras atenciones registradas.</div>';
  return '<div class="prev"><b>'+titulo+' ('+lista.length+')</b><ul>'+lista.map(e=>'<li>'+esc(horaCorta(e.creado_en))+' · '+esc(e.codigo_episodio)+' · '+esc(e.profesional_usuario||'')+
    ' <button type="button" class="linkbtn" data-prev="'+esc(e.codigo_episodio)+'">ver historial</button><div class="prevdet" hidden></div></li>').join('')+'</ul></div>';
}
async function cargarHistorialAuditor(w){
  const r=await TriageAPI.consultarEpisodio(w.ep);
  if(r.estado===401){location.href='index.html';return}
  let html=r.ok?'<b>Historial del episodio</b> · '+esc(w.ep)+htmlEventos(r.datos.episodio.eventos):'<b>Historial del episodio.</b> No se pudo consultar: '+esc((r.datos&&r.datos.mensaje)||'error');
  if(w.srv&&w.srv.pac){const a=await TriageAPI.episodiosDePaciente(w.srv.pac);
    html+=htmlListaAtenciones(a.ok?(a.datos.episodios||[]).filter(x=>x.codigo_episodio!==w.ep):[],'Otras atenciones del paciente');}
  HIST_HTML[w.ep]=html;if(st.screen==='espera')renderWait();
}
/* Historial de casos (auditoría): todos los episodios, también los finalizados, de a 50.
   Se puede filtrar por estado y abrir el historial de cada uno. Solo lectura. */
const CASOS={lista:[],total:0,abierto:false,cargando:false,filtro:''};
async function cargarCasos(mas){
  if(CASOS.cargando)return;CASOS.cargando=true;renderCasos();
  const r=await TriageAPI.listarCasos(50,mas?CASOS.lista.length:0);
  CASOS.cargando=false;
  if(r.estado===401){location.href='index.html';return}
  if(!r.ok){CASOS.error='No se pudo consultar el historial de casos: '+((r.datos&&r.datos.mensaje)||'error');renderCasos();return}
  CASOS.error=null;CASOS.total=r.datos.total||0;
  CASOS.lista=(mas?CASOS.lista:[]).concat(r.datos.episodios||[]);renderCasos();
}
function renderCasos(){
  const box=$('#casosBox');if(!box)return;
  box.hidden=!CASOS.abierto;$('#verCasos').textContent=CASOS.abierto?'Ocultar historial de casos':'Historial de casos';
  if(!CASOS.abierto)return;
  const est={'':'Todos los estados',en_espera:'En espera',finalizado:'Finalizados',en_ingreso:'En ingreso'};
  const vis=CASOS.lista.filter(c=>!CASOS.filtro||c.estado===CASOS.filtro);
  const chip=c=>{const L=LEVELS.find(x=>x[0]===c.color_final);return L?'<span class="chipc" style="background:var('+L[1]+');color:'+L[2]+'">'+L[0]+'</span>':'<span class="hint">sin color</span>'};
  box.innerHTML='<div class="row" style="justify-content:space-between;align-items:center"><b>Historial de casos</b> <span class="hint">'+CASOS.lista.length+' de '+CASOS.total+' episodios · solo lectura</span>'+
    '<select id="casosFiltro">'+Object.entries(est).map(([k,v])=>'<option value="'+k+'"'+(k===CASOS.filtro?' selected':'')+'>'+v+'</option>').join('')+'</select></div>'+
    (CASOS.error?'<div class="werr">'+esc(CASOS.error)+'</div>':'')+
    '<ul>'+vis.map(c=>'<li>'+esc(horaCorta(c.creado_en))+' · <b>'+esc(c.codigo_episodio)+'</b>'+(c.dni?' · DNI '+esc(fmtDni(c.dni)):'')+' · '+esc(c.motivo_categoria||'—')+' · '+
      esc(NOMBRE_ESTADO[c.estado]||c.estado||'sin estado')+' · '+chip(c)+' · '+esc(c.profesional_usuario||'')+
      ' <button type="button" class="linkbtn" data-prev="'+esc(c.codigo_episodio)+'">ver historial</button><div class="prevdet" hidden></div></li>').join('')+'</ul>'+
    (!vis.length&&!CASOS.cargando?'<div class="hint">No hay episodios con ese filtro entre los cargados.</div>':'')+
    (CASOS.cargando?'<div class="hint">Cargando…</div>':CASOS.lista.length<CASOS.total?'<button type="button" class="btn sm" id="casosMas">Ver más</button>':'');
}
$('#verCasos').addEventListener('click',()=>{CASOS.abierto=!CASOS.abierto;if(CASOS.abierto)cargarCasos(false);else renderCasos()});
$('#casosBox').addEventListener('change',e=>{if(e.target.id==='casosFiltro'){CASOS.filtro=e.target.value;renderCasos()}});
$('#casosBox').addEventListener('click',e=>{if(e.target.id==='casosMas')cargarCasos(true)});
async function cargarAtencionesPaciente(pac){
  if(PAC_ATENC[pac]!==undefined)return;PAC_ATENC[pac]=null;
  const r=await TriageAPI.episodiosDePaciente(pac);
  PAC_ATENC[pac]=r.ok?(r.datos.episodios||[]):[];if(st.screen==='espera')renderWait();
}
/* Escalar a ROJO desde En espera: pide el motivo (obligatorio) y queda en la decisión guardada. */
let escForm={mot:'',det:''};
const MOTIVOS_ESC=['Deterioro del estado general','Empeoraron los signos vitales','Alteración de la conciencia','Dificultad respiratoria','Dolor que aumentó o no cede','Sangrado','Otro'];
function textoEscalado(mot,det){return 'Escalado manual por deterioro en espera: '+mot+(det?'. '+det:'')+'.'}
function motivoEscalado(txt){const m=/Escalado manual[^:]*:\s*(.+?)\.?$/.exec(txt||'');return m?m[1]:''}
function htmlEscForm(w){
  const ep=esc(w.ep),ok=!!escForm.mot&&(escForm.mot!=='Otro'||!!escForm.det.trim());
  return '<div class="escform"><b>Escalar a ROJO · motivo (obligatorio)</b>'+
    '<select data-escmot="'+ep+'"><option value="">Seleccionar…</option>'+MOTIVOS_ESC.map(o=>'<option'+(o===escForm.mot?' selected':'')+'>'+o+'</option>').join('')+'</select>'+
    '<input data-escdet="'+ep+'" maxlength="300" value="'+esc(escForm.det)+'" placeholder="'+(escForm.mot==='Otro'?'Contá qué observaste (obligatorio)':'Detalle (opcional): qué observaste')+'">'+
    '<span class="row"><button type="button" class="btn sm esc armed" data-escok="'+ep+'"'+(ok?'':' disabled')+'>Confirmar ROJO</button><button type="button" class="btn sm" data-escno="'+ep+'">Cancelar</button></span></div>';
}
/* DNI -> código de paciente, solo en memoria de esta pestaña (no se guarda en el navegador). */
const DNI_PAC={};
/* Búsqueda en el servidor por DNI completo (7 u 8 dígitos): encuentra pacientes identificados desde
   cualquier compu. Resultado por DNI: 'buscando' | 'no' (no existe) | 'error'. No crea pacientes. */
const DNI_BUSQ={};
async function buscarDniServidor(dni){
  if(!TriageAPI.MODO_REAL||!/^\d{7,8}$/.test(dni)||DNI_PAC[dni]||DNI_BUSQ[dni])return;
  DNI_BUSQ[dni]='buscando';
  const r=await TriageAPI.buscarPaciente(dni);
  if(r.estado===401){location.href='index.html';return}
  if(r.ok&&r.datos.paciente){DNI_PAC[dni]=r.datos.paciente.codigo_paciente;delete DNI_BUSQ[dni]}
  else DNI_BUSQ[dni]=r.estado===404?'no':'error';
  if(st.screen==='espera')renderWait();
}
/* Con servidor, la lista arranca vacía: solo muestra episodios guardados (sin pacientes de ejemplo). */
if(TriageAPI.MODO_REAL)WAIT.length=0;
function commit(lv){
  if(lv==null)return;
  let w=WAIT.find(x=>x.ep===st.ep);
  if(w){w.dni=st.dni;w.lv=lv;w.min=0;w.reeval=!!st.prev;w.rev=JSON.parse(JSON.stringify(st.rev));w.esc=false;w.srv=st.srv}
  else WAIT.push({ep:st.ep,dni:st.dni,lv,mot:st.rev.motivo_categoria||'Sin categoría',min:0,relato:$('#caso').value,rev:JSON.parse(JSON.stringify(st.rev)),srv:st.srv});
  w=WAIT.find(x=>x.ep===st.ep);w.base=Date.now();w.extra=0;
  ponerEnEspera(w);guardarDecision(w,decisionActual(lv));
}

/* ===== Espera persistente (con servidor) =====
   - Al registrar la decisión, el episodio pasa a "en_espera" en el servidor.
   - La lista "En espera" se arma con /api/demo/espera: no se pierde al recargar y la ven todos.
   - "Finalizar" lo pasa a "finalizado" (atendido) y sale de la lista.
   - El color sale SOLO de la decisión guardada en el servidor (color_final). Ya no hay respaldo en la
     pestaña (sessionStorage): si la decisión no se pudo guardar, la fila lo avisa y al recargar queda "Sin color".
   - El motivo (categoría) y el DNI vienen del servidor (datos de ingreso guardados; DNI solo para enfermería y médicos). */
async function versionEstado(ep){
  const r=await TriageAPI.consultarEstado(ep);
  if(r.estado===401){location.href='index.html';return null}
  return r.ok?r.datos.estado:null;
}
async function ponerEnEspera(w){
  if(!TriageAPI.MODO_REAL||!w.srv||!w.srv.ep)return;
  w.aviso=null;
  const e=await versionEstado(w.ep);
  if(!e){w.aviso='No se pudo consultar el estado en el servidor.';return}
  if(e.estado==='en_espera'){w.version=e.version;return}
  const r=await TriageAPI.cambiarEstado(w.ep,'en_espera',e.version);
  if(r.ok){w.version=r.datos.estado.version;w.desde=r.datos.estado.actualizado_en}
  else w.aviso='No se guardó la espera en el servidor: '+(r.datos.mensaje||'error')+'.';
  if(st.screen==='espera')renderWait();
}
async function cargarEspera(){
  if(!TriageAPI.MODO_REAL)return;
  const r=await TriageAPI.listarEspera();
  if(r.estado===401){location.href='index.html';return}
  if(!r.ok){$('#wErr').hidden=false;$('#wErr').textContent='No se pudo leer la lista de espera del servidor: '+(r.datos.mensaje||'error')+'. Se muestra lo de esta pestaña.';return}
  $('#wErr').hidden=true;
  const enServidor=new Set();
  for(const s of r.datos.episodios||[]){
    enServidor.add(s.codigo_episodio);
    let w=WAIT.find(x=>x.ep===s.codigo_episodio);
    if(!w){
      w={ep:s.codigo_episodio,lv:null,mot:'—',esc:false,min:0,relato:'',rev:init(),
         srv:Object.assign(nuevoSrv(),{ep:s.codigo_episodio,pac:s.codigo_paciente}),remoto:true};
      WAIT.push(w);}
    w.desde=s.en_espera_desde;w.version=s.version;w.quien=s.profesional_estado;
    /* Desde 23/10 el servidor devuelve el motivo del último ingreso y, a enfermería y médicos, el DNI. */
    if(s.motivo_categoria&&(w.remoto||!w.mot||w.mot==='—'))w.mot=s.motivo_categoria;
    if(s.dni&&!w.dni){w.dni=s.dni;DNI_PAC[s.dni]=s.codigo_paciente}
    /* El color guardado en el servidor manda (lo ven todas las compus). */
    if(s.color_final){const i=LEVELS.findIndex(L=>L[0]===s.color_final);if(i>-1)w.lv=i;
      if(s.decision_actual&&/Escalado manual/.test(s.decision_actual.motivo||'')){w.esc=true;w.escMot=motivoEscalado(s.decision_actual.motivo)}}
    if(!w.base)w.base=Date.parse(s.en_espera_desde);
  }
  /* Lo que ya no está en espera en el servidor (lo finalizó otro profesional) sale de la lista. */
  for(let i=WAIT.length-1;i>=0;i--)if(WAIT[i].srv&&WAIT[i].srv.ep&&!enServidor.has(WAIT[i].ep)&&!WAIT[i].aviso)WAIT.splice(i,1);
}
async function finalizar(w){
  if(TriageAPI.MODO_REAL&&w.srv&&w.srv.ep){
    const e=await versionEstado(w.ep);
    if(!e){w.aviso='No se pudo consultar el estado en el servidor.';renderWait();return}
    if(e.estado!=='finalizado'){
      const r=await TriageAPI.cambiarEstado(w.ep,'finalizado',e.version);
      if(!r.ok){w.aviso=r.estado===409?'Otro profesional cambió este episodio: se actualizó la lista, probá de nuevo.':'No se pudo finalizar: '+(r.datos.mensaje||'error')+'.';await cargarEspera();renderWait();return}
    }
  }
  const i=WAIT.indexOf(w);if(i>-1)WAIT.splice(i,1);renderWait();
}
/* Episodio que viene del servidor (otra pestaña u otra compu): trae la última medición guardada
   para reevaluar sobre esos valores. El relato y la extracción todavía no se guardan en el servidor. */
async function recuperarUltimaMedicion(w){
  const r=await TriageAPI.consultarEpisodio(w.ep);
  if(!r.ok)return;
  const eventos=r.datos.episodio.eventos||[];
  /* Datos de ingreso (motivo, edad, sexo, banderas…) y última medición: se reevalúa sobre lo que ya se cargó. */
  const ing=eventos.filter(e=>e.tipo==='DATOS_INGRESO_REGISTRADOS').pop();
  if(ing&&ing.datos&&ing.datos.valores){
    for(const [k,v] of Object.entries(ing.datos.valores))if(k in st.rev&&v!=null)st.rev[k]=typeof v==='boolean'?v:String(v).replace('.',',');
    st.srv.ingreso=null;
  }
  const ev=eventos.filter(e=>e.tipo==='MEDICION_REGISTRADA'||e.tipo==='MEDICION_CORREGIDA').pop();
  if(ev&&ev.datos&&ev.datos.valores)
    for(const [k,v] of Object.entries(ev.datos.valores))if(k in st.rev&&v!=null)st.rev[k]=String(v).replace('.',',');
  w.rev=JSON.parse(JSON.stringify(st.rev));
}
/* Minutos en espera: con servidor se cuentan desde la hora real; el modo "tiempo acelerado" suma minutos. */
const minutos=w=>w.base?Math.max(0,Math.floor((Date.now()-w.base)/60000))+(w.extra||0):w.min;
function clock(w){
  if(w.lv==null)return '<span class="clock"><span class="ct">Sin color guardado · reevaluar</span><span class="bar"><i></i></span></span>';
  if(w.lv===0)return '<span class="clock over"><span class="ct">ROJO · atención inmediata</span><span class="bar"><i></i></span></span>';
  const m=minutos(w),T=TARGET[w.lv],rem=T-m,pct=Math.max(0,Math.min(100,100*m/T)),cls=rem<0?' over':(rem<=T*0.25?' warn':'');
  return '<span class="clock'+cls+'"><span class="ct">'+(rem>=0?'⏱ Reevaluar en '+fmtMin(rem):'⏱ Vencido hace '+fmtMin(-rem)+' · reevaluar')+'</span><span class="bar"><i style="width:'+pct+'%"></i></span></span>';
}
function renderWait(){
  const q=($('#epSearch').value||'').trim().toUpperCase();
  /* Si se escriben solo números (con o sin puntos) se busca por DNI; si no, por código de episodio.
     Por DNI se encuentran: los episodios cargados con ese DNI en esta pestaña y, si el paciente ya se
     identificó en esta sesión, todos sus episodios en espera (por su código de paciente). */
  const qDni=/^[\d.\s]+$/.test(q)?q.replace(/[.\s]/g,''):'';
  if(qDni)buscarDniServidor(qDni);
  const pacDeDni=qDni&&DNI_PAC[qDni];
  /* Los episodios de ese paciente que vinieron de otra compu muestran el DNI buscado. */
  if(pacDeDni)WAIT.forEach(w=>{if(w.srv&&w.srv.pac===pacDeDni&&!w.dni)w.dni=qDni});
  const coincide=w=>!q||(qDni?((w.dni||'').startsWith(qDni)||(!!pacDeDni&&w.srv&&w.srv.pac===pacDeDni)):w.ep.includes(q));
  const rows=WAIT.filter(coincide).sort((a,b)=>(a.lv??9)-(b.lv??9)||minutos(b)-minutos(a));
  $('#wCount').textContent=WAIT.length+' pacientes';
  const ro=st.user&&st.user.rol==='auditor';
  $('#verCasos').hidden=!(ro&&TriageAPI.MODO_REAL);
  $('#wList').innerHTML=(rows.map(w=>{const L=w.lv==null?['SIN COLOR','--line','var(--ink)']:LEVELS[w.lv],m=minutos(w),over=w.lv>0&&m>TARGET[w.lv];
    const fin='<button type="button" class="btn sm" data-fin="'+esc(w.ep)+'">'+(finPending===w.ep?'Confirmar finalizar':'Finalizar (atendido)')+'</button>';
    return '<div class="wrow"><span class="wc" style="background:var('+L[1]+');color:'+(w.lv==null?'var(--ink)':L[2])+'">'+L[0]+'</span><span class="wep">'+esc(w.ep)+(w.dni?'<br><span class="hint">DNI '+esc(fmtDni(w.dni))+'</span>':'')+'</span><span class="wm">'+esc(w.mot)+'</span><span class="wt">'+(m?'en espera '+fmtMin(m):'recién clasificado')+'</span>'+clock(w)+'<span class="wf">'+(w.aviso?'<span class="st bad">'+esc(w.aviso)+'</span>':'')+(over?'<span class="st bad">Superó '+TARGET[w.lv]+' min</span>':'')+(w.reeval?'<span class="st fix">Reevaluado</span>':'')+(w.esc?'<span class="st bad">Escalado manual'+(w.escMot?': '+esc(w.escMot):' · deterioro en espera')+'</span>':'')+'</span><span class="wa">'+(ro?'<span class="hint">Solo lectura (auditoría)</span>'+(TriageAPI.MODO_REAL&&w.srv&&w.srv.ep?'<button type="button" class="btn sm" data-hist="'+esc(w.ep)+'">'+(HIST_ABIERTO.has(w.ep)?'Ocultar historial':'Ver historial')+'</button>':''):(w.lv!==0?'<button type="button" class="btn sm" data-re="'+esc(w.ep)+'">Reevaluar</button>'+(escPending===w.ep?'':'<button type="button" class="btn sm esc" data-esc="'+esc(w.ep)+'">Escalar a ROJO</button>'):'<span class="hint">Atención inmediata</span>')+fin)+'</span>'+(!ro&&escPending===w.ep?htmlEscForm(w):'')+(ro&&HIST_ABIERTO.has(w.ep)?'<div class="histpanel note hist">'+(HIST_HTML[w.ep]||'Cargando el historial…')+'</div>':'')+'</div>'}).join('')||'<div class="hint">'+(!qDni?'No hay episodios con ese código.'
    :!TriageAPI.MODO_REAL?'No hay pacientes en espera con ese DNI.'
    :!/^\d{7,8}$/.test(qDni)?'Escribí el DNI completo (7 u 8 dígitos) para buscarlo en el servidor.'
    :DNI_BUSQ[qDni]==='buscando'?'Buscando el DNI en el servidor…'
    :DNI_BUSQ[qDni]==='no'?'No hay ningún paciente identificado con ese DNI.'
    :DNI_BUSQ[qDni]==='error'?'No se pudo consultar el DNI en el servidor. Probá de nuevo.'
    :'El paciente está identificado, pero no tiene episodios en espera.')+'</div>')
    /* Auditor que busca un DNI completo: todas las atenciones del paciente, incluidas las finalizadas. */
    +(ro&&pacDeDni?(cargarAtencionesPaciente(pacDeDni),'<div class="histpanel note hist">'+htmlListaAtenciones(PAC_ATENC[pacDeDni],'Todas las atenciones del DNI '+fmtDni(qDni)+' (incluye finalizadas)')+'</div>'):'');
}
/* Al escribir de nuevo se puede volver a consultar un DNI que antes no estaba o dio error. */
$('#epSearch').addEventListener('input',()=>{for(const k in DNI_BUSQ)if(DNI_BUSQ[k]!=='buscando')delete DNI_BUSQ[k];renderWait()});
$('#fastT').addEventListener('change',e=>st.fast=e.target.checked);
setInterval(()=>{if(!st.fast)return;WAIT.forEach(w=>{w.min++;if(w.base)w.extra=(w.extra||0)+1});if(st.screen==='espera'&&!escPending)renderWait()},1000);
$('#wList').addEventListener('click',e=>{
  const hi=e.target.closest('[data-hist]');
  if(hi){const ep=hi.dataset.hist,w=WAIT.find(x=>x.ep===ep);
    if(HIST_ABIERTO.has(ep))HIST_ABIERTO.delete(ep);else{HIST_ABIERTO.add(ep);if(w)cargarHistorialAuditor(w)}
    renderWait();return}
  const re=e.target.closest('[data-re]'),es=e.target.closest('[data-esc]'),fi=e.target.closest('[data-fin]');
  if(fi){const ep=fi.dataset.fin;if(finPending===ep){finPending=null;const w=WAIT.find(x=>x.ep===ep);if(w)finalizar(w)}else{finPending=ep;renderWait()}return}
  if(re){const w=WAIT.find(x=>x.ep===re.dataset.re);st.ep=w.ep;st.dni=w.dni||null;$('#dni').value=st.dni?fmtDni(st.dni):'';st.srv=w.srv?Object.assign({},w.srv,{nuevaToma:true}):nuevoSrv();st.prev=w.lv==null?null:{lv:w.lv,min:minutos(w)};st.rev=JSON.parse(JSON.stringify(w.rev));st.disc={};$('#caso').value=w.relato||'';st.insuf=false;st.manual=false;escPending=null;resetDecision();
    if(w.remoto&&TriageAPI.MODO_REAL){recuperarUltimaMedicion(w).then(()=>go('revision'));return}
    go('revision');return}
  if(es){escPending=es.dataset.esc;escForm={mot:'',det:''};renderWait();const sel=$('[data-escmot]');if(sel)sel.focus();return}
  const no=e.target.closest('[data-escno]');if(no){escPending=null;renderWait();return}
  const ok=e.target.closest('[data-escok]');
  if(ok&&!ok.disabled){const w=WAIT.find(x=>x.ep===ok.dataset.escok);if(!w)return;
    w.lv=0;w.esc=true;w.escMot=escForm.mot+(escForm.det.trim()?'. '+escForm.det.trim():'');w.min=0;if(w.base){w.base=Date.now();w.extra=0}
    guardarDecision(w,{decision:'modificada',color:'ROJO',motivo:textoEscalado(escForm.mot,escForm.det.trim())});
    escPending=null;escForm={mot:'',det:''};renderWait()}
});
/* El formulario de escalado guarda lo escrito aunque la lista se vuelva a dibujar. */
$('#wList').addEventListener('change',e=>{if(e.target.dataset.escmot!=null){escForm.mot=e.target.value;renderWait();const i=$('[data-escdet]');if(i)i.focus()}});
$('#wList').addEventListener('input',e=>{if(e.target.dataset.escdet!=null){escForm.det=e.target.value;
  const b=$('[data-escok]');if(b)b.disabled=!(escForm.mot&&(escForm.mot!=='Otro'||escForm.det.trim()))}});

