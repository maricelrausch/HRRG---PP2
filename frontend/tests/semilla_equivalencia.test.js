/* Etapa B (Dario 29/10): las reglas de ejemplo que estaban escritas en sugerencia.js (reglas())
   se pasaron a la base como reglas configurables (backend/datos/reglas_semilla.json).
   Esta prueba verifica que dan EXACTAMENTE el mismo color que el código anterior:
     - con todos los casos de backend/datos/casos_simulados.json, y
     - con 30.000 casos al azar armados con valores justo en los límites (89/90/91, 130/131, etc.),
       datos vacíos, números con coma y banderas marcadas o no.
   Si alguien cambia un umbral en un lado y no en el otro, esta prueba falla.
   Ejecutar: node tests/semilla_equivalencia.test.js */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
require('../js/motor_reglas.js');
const M = globalThis.MotorReglas;

// 1) La función reglas() original, tal como está en sugerencia.js.
const fuente = fs.readFileSync(path.join(__dirname, '..', 'sugerencia.js'), 'utf8').replace(/\r\n/g, '\n');
const ini = fuente.indexOf('function reglas(){');
const fin = fuente.indexOf('\n}\n', ini);
assert.ok(ini >= 0 && fin > ini, 'no se encontró reglas() en sugerencia.js');
const ctx = { st: { rev: {} }, num: (v) => Number(String(v).replace(',', '.')) };   // num() igual que formulario.js
vm.createContext(ctx);
vm.runInContext(fuente.slice(ini, fin + 2) + '\nthis.reglas = reglas;', ctx);
const nivelViejo = (d) => { ctx.st.rev = d; const r = ctx.reglas(); return r.length ? Math.min(...r.map((x) => x.lv)) : 9; };

// 2) Las mismas reglas cargadas desde la semilla, evaluadas por el motor configurable.
const semilla = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'backend', 'datos', 'reglas_semilla.json'), 'utf8'));
const reglas = semilla.reglas.map((r, i) => Object.assign({ codigo: 'R-' + (i + 1), version: 1 }, r));
const nivelNuevo = (d) => { const r = M.evaluar(reglas, d); return r.length ? r[0].lv : 9; };

let n = 0;
const comparar = (d, origen) => {
  const a = nivelViejo(d), b = nivelNuevo(d);
  assert.strictEqual(b, a, origen + ': el código daba ' + a + ' y la semilla da ' + b + '\n' + JSON.stringify(d));
  n++;
};

// Casos simulados del proyecto.
const casos = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'backend', 'datos', 'casos_simulados.json'), 'utf8'));
['casos', 'casos_extraccion', 'casos_api'].forEach((k) => (casos[k] || []).forEach((c) => {
  const d = c.entrada || c.esperado_extraccion || c.datos;
  if (d && typeof d === 'object') comparar(d, k + ' ' + (c.id || ''));
}));
const simulados = n;

// Casos al azar en los límites.
const V = {
  saturacion_o2: ['', 85, 89, '89,5', 90, 91, 98], frecuencia_respiratoria: ['', 6, 7, 8, 9, 30, 31, 40],
  ta_sistolica: ['', 70, 89, 90, 91, 120], frecuencia_cardiaca: ['', 35, 39, 40, 41, 130, 131, 150],
  glasgow: ['', 3, 8, 9, 14, 15], temperatura: ['', 36.5, 37.9, '38', 38, '38,2', 40],
  dolor_intensidad: ['', 0, 7, 8, 10], estado_conciencia: ['', 'Alerta', 'Responde a la voz', 'Responde al dolor', 'No responde'],
  br_convulsion: [true, false, undefined], br_disnea: [true, false, undefined], br_sangrado: [true, false, undefined], ant_inmuno: [true, false, undefined]
};
let semillaAzar = 20261029;
const azar = (m) => { semillaAzar = (semillaAzar * 1103515245 + 12345) % 2147483648; return semillaAzar % m; };
for (let i = 0; i < 30000; i++) {
  const d = {};
  Object.entries(V).forEach(([k, vs]) => { const v = vs[azar(vs.length)]; if (v !== undefined) d[k] = v; });
  comparar(d, 'azar #' + i);
}
console.log('semilla_equivalencia: ' + n + ' casos OK (' + simulados + ' simulados + 30000 al azar en los límites)');
