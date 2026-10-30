/* Copia CONGELADA de la función reglas() que estaba en frontend/sugerencia.js hasta el 30/10/2026.
   Ya no se usa en la app (las reglas están en la base y se administran en reglas.html).
   Se conserva solo como referencia para tests/semilla_equivalencia.test.js: comprueba que
   backend/datos/reglas_semilla.json da exactamente los mismos colores que este código. No modificar. */
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
