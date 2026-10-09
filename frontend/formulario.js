(()=>{
'use strict';
const api=window.TriageDatos,$=id=>document.getElementById(id);let prepared=null;
const display={sangrado:'Sangrado',convulsion:'Convulsión',dificultad_respiratoria:'Dificultad respiratoria',trauma:'Trauma',diabetes:'Diabetes',cardiaco:'Cardíaco',medicacion_critica:'Medicación crítica'};
function code(){const a=new Uint8Array(8);crypto.getRandomValues(a);return 'EP-'+Array.from(a,x=>x.toString(16).padStart(2,'0')).join('').toUpperCase();}
function numericField(key,target){
 const s=api.numeric[key],wrap=document.createElement('div');wrap.className='field';
 const label=document.createElement('label');label.htmlFor=key;label.textContent=s.label;
 const tag=document.createElement('span');tag.className=api.required.includes(key)?'expected':'optional';tag.textContent=api.required.includes(key)?'Esperado':'Opcional';label.append(tag);
 const unit=document.createElement('div');unit.className='unit';const input=document.createElement('input');input.id=key;input.type='text';input.inputMode=s.integer?'numeric':'decimal';input.setAttribute('aria-describedby',key+'-help '+key+'-error');
 const u=document.createElement('span');u.textContent=s.unit;unit.append(input,u);
 const help=document.createElement('small');help.id=key+'-help';help.textContent=(s.integer?'Entero':'Decimal')+' · '+s.min+' a '+s.max;
 const err=document.createElement('span');err.id=key+'-error';err.className='error';wrap.append(label,unit,help,err);$(target).append(wrap);
}
['tas','tad','frec_cardiaca','frec_respiratoria','saturacion','temperatura'].forEach(k=>numericField(k,'vitals'));
['glasgow','dolor'].forEach(k=>numericField(k,'consciousness'));
for(const [k,values] of Object.entries(api.lists)){
 for(const v of values){const l=document.createElement('label');l.className='check';const i=document.createElement('input');i.type='checkbox';i.name=k;i.value=v;i.addEventListener('change',()=>{if(i.checked)$(k+'_none').checked=false;update()});l.append(i,document.createTextNode(display[v]));$(k==='banderas_rojas'?'flags':'history').append(l);}
 $(k+'_none').addEventListener('change',()=>{if($(k+'_none').checked)document.querySelectorAll('input[name="'+k+'"]').forEach(i=>i.checked=false);update()});
}
function collect(){const raw={};for(const k of Object.keys(api.labels)){if(api.lists[k]){const selected=Array.from(document.querySelectorAll('input[name="'+k+'"]:checked'),i=>i.value);raw[k]=selected.length?selected:($(k+'_none').checked?[]:null)}else raw[k]=$(k).value;}return raw;}
function invalidate(){prepared=null;$('review').hidden=true;}
function update(){invalidate();const r=api.validate(collect());for(const k of Object.keys(api.labels)){const el=$(k),err=$(k+'-error');if(err)err.textContent=r.errors[k]||'';el.setAttribute('aria-invalid',String(Boolean(r.errors[k])));}
 const count=api.required.filter(k=>r.data[k]!==null&&!r.errors[k]).length;$('count').textContent=count+' de '+api.required.length+' campos esperados';$('progress').value=count;
 $('pending').replaceChildren();for(const k of api.required.filter(k=>r.data[k]===null||r.errors[k])){const li=document.createElement('li');li.textContent=api.labels[k]+(r.errors[k]?' · revisar':'');$('pending').append(li);}
 $('inputstate').textContent=r.valid?'Sin errores de formato detectados.':Object.keys(r.errors).length+' campo(s) para revisar.';
 $('contradiction-note').hidden=!$('contradiction').checked;$('errors-summary').hidden=true;return r;}
$('triage').addEventListener('input',e=>{if(!['privacy','contradiction'].includes(e.target.id))$('privacy').checked=false;update()});
$('triage').addEventListener('change',update);
$('triage').addEventListener('submit',e=>{e.preventDefault();const r=update();const messages=Object.values(r.errors);if($('contradiction').checked)messages.push('Información insuficiente: revisá la contradicción señalada.');if(!$('privacy').checked)messages.push('Confirmá que el caso es ficticio y no contiene datos personales.');
 if(messages.length){$('errors-summary').textContent=messages.join(' ');$('errors-summary').hidden=false;const key=Object.keys(r.errors)[0];if(key)$(key).focus();return;}
 prepared=r.data;$('reviewrows').replaceChildren();
 for(const [k] of Object.entries(api.labels)){const tr=document.createElement('tr'),key=document.createElement('td'),val=document.createElement('td');key.textContent=k;const v=r.data[k];val.textContent=v===null?'Sin información':Array.isArray(v)?(v.length?v.map(x=>display[x]).join(', '):'Ninguna de las opciones, tras revisión'):String(v);tr.append(key,val);$('reviewrows').append(tr);}
 $('json').textContent=JSON.stringify(prepared,null,2);
 $('reviewstate').textContent=r.missing.length?'Se permite continuar con datos faltantes: '+r.missing.map(k=>api.labels[k]).join(', ')+'.':'Todos los campos esperados están cargados. Esto no acredita suficiencia clínica.';
 $('review').hidden=false;$('exportstatus').textContent='';$('review').scrollIntoView({behavior:'smooth',block:'start'});
});
$('download').onclick=()=>{if(!prepared)return;const blob=new Blob([JSON.stringify(prepared,null,2)],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=prepared.codigo_episodio+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('exportstatus').textContent='Descarga solicitada. El archivo queda en tu carpeta de descargas.'};
$('edit').onclick=()=>$('triage').scrollIntoView({behavior:'smooth',block:'start'});
function reset(){ $('triage').reset();$('codigo_episodio').value=code();update();}
$('reset').onclick=()=>{if(confirm('¿Iniciar otro episodio? Se borrará la carga actual que no hayas exportado.'))reset()};
$('sample').onclick=()=>{if(!confirm('¿Reemplazar la carga actual por un ejemplo ficticio?'))return;reset();const s={edad:'42',sexo:'X',motivo_consulta:'Dolor de tobillo derecho desde hace 3 horas.',tas:'120',tad:'80',frec_cardiaca:'80',frec_respiratoria:'16',saturacion:'98',temperatura:'36,5',glasgow:'15',dolor:'6',localizacion_dolor:'Tobillo derecho'};Object.entries(s).forEach(([k,v])=>$(k).value=v);update()};
reset();
})();
