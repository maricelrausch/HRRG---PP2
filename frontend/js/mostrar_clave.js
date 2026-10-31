/* [Propuesta Barby 26/10] Botón "Mostrar / Ocultar" en todos los campos de contraseña
   (login, cambiar contraseña y exportar del auditor), para ver lo que se está escribiendo.
   También funciona con los campos que se dibujan después (MutationObserver).
   Al enviar el formulario o perder la página, la contraseña vuelve a quedar oculta. */
(function () {
  function agregar(inp) {
    if (inp.dataset.mostrarClave) return;
    inp.dataset.mostrarClave = '1';
    const caja = document.createElement('span');
    caja.className = 'clave';
    inp.parentNode.insertBefore(caja, inp);
    caja.appendChild(inp);
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'ver-clave';
    b.textContent = 'Mostrar';
    b.setAttribute('aria-label', 'Mostrar la contraseña');
    b.setAttribute('aria-pressed', 'false');
    b.addEventListener('click', function (e) {
      e.preventDefault();
      const ver = inp.type === 'password';
      inp.type = ver ? 'text' : 'password';
      b.textContent = ver ? 'Ocultar' : 'Mostrar';
      b.setAttribute('aria-label', ver ? 'Ocultar la contraseña' : 'Mostrar la contraseña');
      b.setAttribute('aria-pressed', String(ver));
      inp.focus();
    });
    caja.appendChild(b);
  }
  function revisar(raiz) {
    (raiz.querySelectorAll ? raiz : document).querySelectorAll('input[type=password]').forEach(agregar);
  }
  /* Antes de enviar, se vuelve a ocultar (así el navegador no la guarda como texto común). */
  document.addEventListener('submit', function (e) {
    e.target.querySelectorAll('input[data-mostrar-clave]').forEach(function (i) {
      i.type = 'password';
      const b = i.parentNode.querySelector('.ver-clave');
      if (b) { b.textContent = 'Mostrar'; b.setAttribute('aria-pressed', 'false'); }
    });
  }, true);
  function iniciar() {
    revisar(document);
    new MutationObserver(function (cambios) {
      cambios.forEach(function (c) { c.addedNodes.forEach(function (n) { if (n.nodeType === 1) { if (n.matches && n.matches('input[type=password]')) agregar(n); else revisar(n); } }); });
    }).observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar); else iniciar();
})();
