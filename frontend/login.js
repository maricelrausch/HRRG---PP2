const form = document.getElementById("loginForm");
const error = document.getElementById("loginErr");
const boton = form.querySelector('button[type="submit"]');

form.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  error.hidden = true;
  boton.disabled = true;

  try {
    const respuesta = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        usuario: document.getElementById("lgUser").value.trim(),
        password: document.getElementById("lgPass").value
      })
    });

    const datos = await respuesta.json();

    if (!respuesta.ok) {
      throw new Error(
        datos.mensaje || "No se pudo iniciar sesión."
      );
    }

    window.location.replace("/formulario.html");
  } catch (e) {
    error.textContent =
      e.message || "No se pudo conectar con el servidor.";
    error.hidden = false;
  } finally {
    document.getElementById("lgPass").value = "";
    boton.disabled = false;
  }
});