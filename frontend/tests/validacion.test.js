/* Pruebas de frontend/validacion.js · correr con:  node frontend/tests/validacion.test.js
   Reflejan los controles de backend/docs/controles_validacion.md (C04). */
const assert = require('assert');
const V = require('../validacion.js');
let n = 0;
const t = (nombre, fn) => { fn(); n++; console.log('ok -', nombre); };

const base = { edad: '58', sexo: 'Femenino', motivo_categoria: 'Dolor abdominal', tiempo_evolucion_valor: '6',
  tiempo_evolucion_unidad: 'horas', motivo_consulta: 'Dolor abdominal con náuseas', dolor_localizacion: 'Epigastrio',
  ta_sistolica: '130', ta_diastolica: '85', frecuencia_cardiaca: '96', frecuencia_respiratoria: '18',
  saturacion_o2: '97', temperatura: '37,8', dolor_intensidad: '7' };

t('caso completo es válido y sin faltantes', () => { const r = V.validate(base); assert.ok(r.valid); assert.deepStrictEqual(r.missing, []); });
t('1 · coma decimal', () => assert.strictEqual(V.validate(base).data.temperatura, 37.8));
t('1 · texto o unidades en un número', () => { assert.ok(V.validate({ saturacion_o2: '94 %' }).errors.saturacion_o2); assert.ok(V.validate({ edad: 'noventa' }).errors.edad); });
t('2 · entero', () => assert.ok(V.validate({ dolor_intensidad: '7,5' }).errors.dolor_intensidad));
t('3 · rangos', () => { assert.ok(V.validate({ edad: '121' }).errors.edad); assert.ok(!V.validate({ edad: '120' }).errors.edad); assert.ok(V.validate({ saturacion_o2: '140' }).errors.saturacion_o2); assert.ok(V.validate({ glucemia: '900' }).errors.glucemia); });
t('4 · opciones cerradas', () => { assert.ok(V.validate({ sexo: 'Otro' }).errors.sexo); assert.ok(V.validate({ tiempo_evolucion_unidad: 'semanas' }).errors.tiempo_evolucion_unidad); assert.ok(!V.validate({ estado_conciencia: 'Alerta' }).errors.estado_conciencia); });
t('5 · diastólica >= sistólica', () => assert.ok(V.validate({ ta_sistolica: '90', ta_diastolica: '95' }).errors.ta_diastolica));
t('6 · privacidad en textos libres', () => {
  for (const [k, v] of [['motivo_consulta', 'Me llamo Ana'], ['sintomas_asociados', 'DNI 30123456'], ['alergias', 'tel 2964-123456'], ['aspecto_general', 'vive en calle 9'], ['dolor_caracteristicas', 'ana@mail.com']])
    assert.ok(V.validate({ [k]: v }).errors[k], k + ': ' + v);
  assert.ok(!V.validate({ motivo_consulta: 'Dolor de panza' }).errors.motivo_consulta);
});
t('8 · formato de códigos', () => { assert.ok(!V.validate({ codigo_episodio: 'EPI-004818' }).errors.codigo_episodio); assert.ok(V.validate({ codigo_paciente: '12345' }).errors.codigo_paciente); });
t('9 · faltantes por etapa no bloquean', () => {
  const r = V.validate({ edad: '40' }, 'ingreso'); assert.ok(r.valid); assert.ok(r.missing.includes('sexo')); assert.ok(!r.missing.includes('ta_sistolica'));
  assert.deepStrictEqual(V.validate({}, 'medicion').missing, V.required.medicion);
  assert.ok(!V.validate({}).missing.includes('glasgow'), 'glasgow no es obligatorio');
});
t('10 · vacío ≠ cero', () => { const r = V.validate({ dolor_intensidad: '0', glucemia: '' }); assert.strictEqual(r.data.dolor_intensidad, 0); assert.strictEqual(r.data.glucemia, null); });
t('banderas y antecedentes sí/no', () => { const r = V.validate({ br_disnea: 'sí', ant_diabetes: true }); assert.strictEqual(r.data.br_disnea, true); assert.strictEqual(r.data.br_sangrado, false); assert.ok(V.validate({ br_trauma: 'tal vez' }).errors.br_trauma); });
t('nombres viejos se traducen', () => { const r = V.validate({ tas: 150, tad: 95, saturacion: 94, sexo: 'F', banderas_rojas: ['dificultad_respiratoria'], antecedentes: ['diabetes'] });
  assert.ok(r.valid); assert.strictEqual(r.data.ta_sistolica, 150); assert.strictEqual(r.data.sexo, 'Femenino'); assert.strictEqual(r.data.br_disnea, true); assert.strictEqual(r.data.ant_diabetes, true); });
t('PAM calculada', () => assert.strictEqual(V.validate({ ta_sistolica: '120', ta_diastolica: '80' }).data.pam, 93));
console.log('\n' + n + ' pruebas OK');
