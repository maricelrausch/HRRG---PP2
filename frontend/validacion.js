(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.TriageDatos=api;})(typeof globalThis!=='undefined'?globalThis:this, function(){
'use strict';
const numeric={
edad:{label:'Edad',min:0,max:110,integer:true,unit:'años'},
tas:{label:'Tensión sistólica',min:50,max:260,integer:true,unit:'mmHg'},
tad:{label:'Tensión diastólica',min:20,max:160,integer:true,unit:'mmHg'},
frec_cardiaca:{label:'Frecuencia cardíaca',min:20,max:250,integer:true,unit:'lpm'},
frec_respiratoria:{label:'Frecuencia respiratoria',min:4,max:60,integer:true,unit:'rpm'},
saturacion:{label:'Saturación de oxígeno',min:50,max:100,integer:true,unit:'%'},
temperatura:{label:'Temperatura',min:30,max:43,integer:false,unit:'°C'},
glasgow:{label:'Glasgow',min:3,max:15,integer:true,unit:'puntos'},
dolor:{label:'Intensidad del dolor',min:0,max:10,integer:true,unit:'0–10'}
};
const labels={codigo_episodio:'Código de episodio',edad:'Edad',sexo:'Sexo',motivo_consulta:'Motivo de consulta',tas:'Tensión sistólica',tad:'Tensión diastólica',frec_cardiaca:'Frecuencia cardíaca',frec_respiratoria:'Frecuencia respiratoria',saturacion:'Saturación de oxígeno',temperatura:'Temperatura',glasgow:'Glasgow',dolor:'Intensidad del dolor',localizacion_dolor:'Localización del dolor',banderas_rojas:'Banderas rojas',antecedentes:'Antecedentes',antecedentes_otros:'Otros antecedentes'};
const required=['codigo_episodio','edad','sexo','motivo_consulta','tas','tad','frec_cardiaca','frec_respiratoria','saturacion','temperatura','glasgow'];
const lists={banderas_rojas:['sangrado','convulsion','dificultad_respiratoria','trauma'],antecedentes:['diabetes','cardiaco','medicacion_critica']};
function validate(raw){
 const data={},errors={};
 data.codigo_episodio=String(raw.codigo_episodio||'').trim()||null;
 Object.entries(numeric).forEach(([key,s])=>{
 const val=String(raw[key]??'').trim();
 if(!val){data[key]=null;return;}
 if(!/^-?\d+(?:[.,]\d+)?$/.test(val)){data[key]=null;errors[key]='Ingresá solo un número, sin unidades ni símbolos.';return;}
 const n=Number(val.replace(',','.'));data[key]=n;
 if(!Number.isFinite(n)||(s.integer&&!Number.isInteger(n)))errors[key]='Ingresá un número entero.';
 else if(n<s.min||n>s.max)errors[key]='Rango del diccionario: '+s.min+' a '+s.max+' '+s.unit+'. Revisá el dato; no lo ajustes solo para que pase.';
 });
 data.sexo=raw.sexo||null;
 if(data.sexo&&!['M','F','X'].includes(data.sexo))errors.sexo='Elegí una opción de la lista.';
 ['motivo_consulta','localizacion_dolor','antecedentes_otros'].forEach(k=>{
 data[k]=String(raw[k]??'').trim()||null;
 if(data[k]&&(/\b(?:DNI|documento|nombre|apellido|domicilio|tel[eé]fono)\b/i.test(data[k])||/[\w.+-]+@[\w.-]+\.[a-z]{2,}/i.test(data[k])||/\b\d{7,}\b/.test(data[k])))errors[k]='Posibles datos identificatorios. Eliminá nombres, documentos y datos de contacto.';
 });
 for(const [k,allowed] of Object.entries(lists)){
 const v=raw[k];data[k]=v==null?null:v;
 if(v!=null&&(!Array.isArray(v)||v.some(x=>!allowed.includes(x))||new Set(v).size!==v.length))errors[k]='Selección inválida.';
 }
 if(!errors.tas&&!errors.tad&&data.tas!=null&&data.tad!=null&&data.tad>=data.tas)errors.tad='La diastólica debe ser menor que la sistólica. Revisá ambas mediciones.';
 const missing=required.filter(k=>data[k]===null);
 return {data,errors,missing,valid:Object.keys(errors).length===0};
}
return {numeric,labels,required,lists,validate};
});
