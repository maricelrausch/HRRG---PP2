/* Pruebas del motor de reglas del hospital (js/motor_reglas.js). Ejecutar: node tests/motor_reglas.test.js */
const assert = require('assert');
require('../js/motor_reglas.js');
const M = globalThis.MotorReglas;
const R = (color, combinacion, condiciones, codigo = 'R-001') => ({ codigo, nombre: 'x', version: 1, explicacion: 'e', color, combinacion, condiciones });
let n = 0; const t = (nombre, fn) => { fn(); n++; };

t('numérico con coma y umbral', () => {
  const r = [R('NARANJA', 'todas', [{ campo: 'saturacion_o2', operador: '<', valor: 92 }])];
  assert.strictEqual(M.evaluar(r, { saturacion_o2: '91' }).length, 1);
  assert.strictEqual(M.evaluar(r, { saturacion_o2: '92' }).length, 0);
  assert.strictEqual(M.evaluar([R('AMARILLO', 'todas', [{ campo: 'temperatura', operador: '>=', valor: 38.5 }])], { temperatura: '38,5' }).length, 1);
});
t('un dato vacío nunca cumple', () => {
  const r = [R('NARANJA', 'todas', [{ campo: 'saturacion_o2', operador: '<', valor: 92 }])];
  assert.strictEqual(M.evaluar(r, { saturacion_o2: '' }).length, 0);
  assert.strictEqual(M.evaluar([R('VERDE', 'todas', [{ campo: 'estado_conciencia', operador: 'no_es', valor: 'Alerta' }])], { estado_conciencia: '' }).length, 0);
});
t('todas / alguna', () => {
  const c = [{ campo: 'br_disnea', operador: 'si' }, { campo: 'frecuencia_respiratoria', operador: '>', valor: 30 }];
  assert.strictEqual(M.evaluar([R('ROJO', 'todas', c)], { br_disnea: true, frecuencia_respiratoria: '20' }).length, 0);
  assert.strictEqual(M.evaluar([R('ROJO', 'alguna', c)], { br_disnea: true, frecuencia_respiratoria: '20' }).length, 1);
});
t('PAM calculada con la TA', () => {
  const r = [R('NARANJA', 'todas', [{ campo: 'pam', operador: '<', valor: 65 }])];
  assert.strictEqual(M.evaluar(r, { ta_sistolica: '80', ta_diastolica: '50' }).length, 1);   // (80+100)/3 = 60
  assert.strictEqual(M.evaluar(r, { ta_sistolica: '120', ta_diastolica: '80' }).length, 0);
});
t('opciones y booleanos', () => {
  assert.strictEqual(M.evaluar([R('AMARILLO', 'todas', [{ campo: 'motivo_categoria', operador: 'es', valor: 'Dolor torácico' }])], { motivo_categoria: 'Dolor torácico' }).length, 1);
  assert.strictEqual(M.evaluar([R('AMARILLO', 'todas', [{ campo: 'ant_resp', operador: 'no' }])], { ant_resp: false }).length, 1);
});
t('ordena de la más urgente a la menos urgente', () => {
  const r = [R('AMARILLO', 'todas', [{ campo: 'edad', operador: '>=', valor: 65 }], 'R-002'),
             R('ROJO', 'todas', [{ campo: 'glasgow', operador: '<=', valor: 8 }], 'R-003')];
  assert.deepStrictEqual(M.evaluar(r, { edad: '70', glasgow: '7' }).map(x => x.codigo), ['R-003', 'R-002']);
});
t('describir', () => {
  assert.strictEqual(M.describir({ campo: 'saturacion_o2', operador: '<=', valor: 92.5 }, { saturacion_o2: { etiqueta: 'SpO₂', unidad: '%' } }), 'SpO₂ ≤ 92,5 %');
});
t('origen y validación pasan al resultado sin cambiar el cálculo (Dario 29/10)', () => {
  const base = { saturacion_o2: '85' };
  const r = (origen, validada_por) => Object.assign(R('NARANJA', 'todas', [{ campo: 'saturacion_o2', operador: '<', valor: 90 }]), { origen, validada_por });
  const m = M.evaluar([r('manchester', 'Enfermería')], base)[0];
  assert.strictEqual(m.origen, 'manchester'); assert.strictEqual(m.validada_por, 'Enfermería'); assert.strictEqual(m.lv, 1);
  // Una regla provisoria también fija piso (decisión del equipo: nos equivocamos hacia lo más urgente).
  assert.strictEqual(M.evaluar([r('provisoria', '')], base)[0].lv, 1);
  // Sin origen (reglas anteriores) se toma como provisoria.
  assert.strictEqual(M.evaluar([R('NARANJA', 'todas', [{ campo: 'saturacion_o2', operador: '<', valor: 90 }])], base)[0].origen, 'provisoria');
});
console.log('motor_reglas: ' + n + ' pruebas OK');
