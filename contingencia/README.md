# Plan B: si Cloudflare bloquea a GitHub Actions

Cómo saber si estás en este caso: en el log de Actions, `checkin.py` imprime
`Sin token tras 20s` y/o la respuesta del claim es `400 SIGNUP_INVALID_PARAMS`,
y en "Consola (error/warn)" aparecen errores `[Cloudflare Turnstile] Error: 6000xx`.
Eso significa que Turnstile no confía en la IP de Azure/GitHub.

Turnstile **necesita un navegador real con IP residencial**. No existe una forma de
que funcione con 0 RAM y todo apagado: algo tiene que abrir la página una vez al día.
Estas son las opciones, de más ligera a más pesada.

## Opción 1 — Userscript en el celular (recomendada)

`caveduck-autoclaim.user.js`: cuando abres `https://caveduck.io/es/store`, abre solo
el Check-in Diario, espera el token de Turnstile, pulsa **Registrarse y reclamar** y te
muestra un aviso verde/rojo con el resultado. Solo actúa una vez por día.

- **Via Browser** (pesa ~1 MB, ideal para el A22): Ajustes → Scripts → `+` → pega el
  contenido del archivo.
- **Firefox Android / Kiwi** + extensión **Tampermonkey**: crear script nuevo y pegar.

Para no tener que acordarte, automatiza la apertura con **MacroDroid** (gratis, muy ligero):
Disparador *Día/Hora* 19:05 todos los días → Acción *Abrir sitio web*
`https://caveduck.io/es/store` con Via. El navegador se abre ~30 s y luego puedes cerrarlo.

> Inicia sesión en Caveduck dentro del mismo navegador donde instales el script.

## Opción 2 — Tarea programada en Windows

Corre el mismo `checkin.py` desde tu PC (IP residencial). Ver instrucciones al inicio de
`programar_tarea_windows.ps1`. Si el PC está apagado a las 19:15, se ejecuta al encenderlo
(`StartWhenAvailable`). `cookie.txt` está en `.gitignore`.
