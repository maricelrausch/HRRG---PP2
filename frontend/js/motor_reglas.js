/* frontend/js/motor_reglas.js · Motor de las REGLAS DEL HOSPITAL (propuesta Barby 28/10).
   Lo usan la sugerencia (sugerencia.js) y la pantalla de la Jefatura de Guardia (reglas.html, para probar).
   Las reglas las carga la Jefatura en el servidor (/api/reglas). Cada regla:
     { codigo, nombre, version, explicacion, color: 'ROJO'|'NARANJA'|'AMARILLO'|'VERDE',
       combinacion: 'todas'|'alguna', condiciones: [{campo, operador, valor}] }
   Una regla que se cumple fija un PISO: la sugerencia no puede quedar por debajo de su color.
   Un dato que falta NUNCA cumple una condición (no se adivina: si no se midió, la regla no salta). */
(function (root) {
  'use strict';
  const NIVEL = { ROJO: 0, NARANJA: 1, AMARILLO: 2, VERDE: 3 };
  /* [Dario 29/10] Origen de la regla (pedido de Francisco Navoni). No cambia el cálculo: las tres fijan piso. */
  const ORIGEN = { manchester: 'Manchester', local: 'Adaptación HRRG', provisoria: 'Provisoria' };
  const OPS_NUM = {
    '<': (a, b) => a < b, '<=': (a, b) => a <= b, '>': (a, b) => a > b,
    '>=': (a, b) => a >= b, '=': (a, b) => a === b, '!=': (a, b) => a !== b
  };
  const SIMBOLO = { '<': '<', '<=': '≤', '>': '>', '>=': '≥', '=': '=', '!=': '≠' };

  function numero(v) {
    if (v === null || v === undefined || v === '' || typeof v === 'boolean') return null;
    const n = Number(String(v).trim().replace(',', '.'));
    return Number.isFinite(n) ? n : null;
  }
  /* [Dario 29/10 · D1] Grupo etario calculado con la edad (mismos cortes que backend/src/reglas_hospital.py). */
  const GRUPOS = [['Lactante', 0, 0], ['Niño', 1, 11], ['Adolescente', 12, 17], ['Adulto', 18, 64], ['Adulto mayor', 65, 200]];
  function grupoEtario(edad) {
    const a = numero(edad);
    if (a === null || a < 0) return null;
    const g = GRUPOS.find(([, min, max]) => a >= min && a < max + 1);
    return g ? g[0] : null;
  }
  /* Valor de un dato del caso. La PAM se calcula con la TA si no viene cargada; el grupo etario, con la edad. */
  function valor(datos, campo) {
    if (campo === 'grupo_etario') return datos.grupo_etario || grupoEtario(datos.edad);
    if (campo === 'pam') {
      const p = numero(datos.pam);
      if (p !== null) return p;
      const s = numero(datos.ta_sistolica), d = numero(datos.ta_diastolica);
      return s !== null && d !== null ? Math.round((s + 2 * d) / 3) : null;
    }
    return datos[campo];
  }
  function cumple(cond, datos) {
    const v = valor(datos, cond.campo), op = cond.operador;
    if (OPS_NUM[op]) {
      const a = numero(v), b = numero(cond.valor);
      return a !== null && b !== null && OPS_NUM[op](a, b);
    }
    if (op === 'es') return v === cond.valor;
    if (op === 'no_es') return v !== undefined && v !== null && v !== '' && v !== cond.valor;
    if (op === 'si') return v === true;
    if (op === 'no') return v === false;
    return false;
  }
  /* Texto legible de una condición, con el catálogo de campos (GET /api/reglas/campos) si se tiene. */
  function describir(cond, campos) {
    const c = (campos && campos[cond.campo]) || { etiqueta: cond.campo };
    if (cond.operador === 'si') return c.etiqueta + ': sí';
    if (cond.operador === 'no') return c.etiqueta + ': no';
    if (cond.operador === 'es') return c.etiqueta + ' es «' + cond.valor + '»';
    if (cond.operador === 'no_es') return c.etiqueta + ' no es «' + cond.valor + '»';
    return c.etiqueta + ' ' + (SIMBOLO[cond.operador] || cond.operador) + ' ' +
      String(cond.valor).replace('.', ',') + (c.unidad ? ' ' + c.unidad : '');
  }
  /* Devuelve las reglas que se cumplen, de la más urgente a la menos urgente. */
  function evaluar(reglas, datos) {
    const out = [];
    (reglas || []).forEach(function (r) {
      const conds = r.condiciones || [];
      if (!conds.length || !(r.color in NIVEL)) return;
      const ok = r.combinacion === 'alguna' ? conds.some(c => cumple(c, datos)) : conds.every(c => cumple(c, datos));
      if (ok) out.push({ codigo: r.codigo, nombre: r.nombre, version: r.version, color: r.color,
        lv: NIVEL[r.color], texto: r.explicacion,
        origen: r.origen in ORIGEN ? r.origen : 'provisoria', validada_por: r.validada_por || '',
        discriminador: r.discriminador || '',
        cumplidas: conds.filter(c => cumple(c, datos)) });
    });
    return out.sort((a, b) => a.lv - b.lv);
  }
  root.MotorReglas = { evaluar: evaluar, cumple: cumple, describir: describir, NIVEL: NIVEL, ORIGEN: ORIGEN, grupoEtario: grupoEtario };
})(typeof globalThis !== 'undefined' ? globalThis : this);
