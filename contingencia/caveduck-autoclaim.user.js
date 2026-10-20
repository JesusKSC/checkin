// ==UserScript==
// @name         Caveduck Auto Check-in
// @namespace    https://github.com/JesusKSC/checkin
// @version      1.0.0
// @description  Abre el Check-in Diario de Caveduck y pulsa "Registrarse y reclamar" cuando Turnstile entrega el token.
// @match        https://caveduck.io/*
// @run-at       document-start
// @grant        none
// ==/UserScript==

(function () {
  'use strict';

  // Si es true, al entrar a cualquier página de Caveduck sin haber reclamado hoy,
  // te lleva a la tienda automáticamente.
  const REDIRIGIR_A_TIENDA = false;
  const CLAIM_PATH = '/api/point/claim-24h-free-charge-points';
  const TXT_MENU = 'Caveduck Check-in Diario';
  const TXT_RECLAMAR = 'Registrarse y reclamar';
  const TXT_COMPLETADO = 'Registro diario completado';

  // El check-in se reinicia a las 9:00 KST = 00:00 UTC, así que la fecha UTC sirve de "día".
  const claveHoy = () => 'cd_autoclaim_' + new Date().toISOString().slice(0, 10);
  const yaHecho = () => { try { return localStorage.getItem(claveHoy()) === '1'; } catch (e) { return false; } };
  const marcarHecho = () => { try { localStorage.setItem(claveHoy(), '1'); } catch (e) {} };

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function aviso(msg, color) {
    console.log('[Caveduck Auto Check-in]', msg);
    const pinta = () => {
      let el = document.getElementById('cd-autoclaim-toast');
      if (!el) {
        el = document.createElement('div');
        el.id = 'cd-autoclaim-toast';
        el.style.cssText = 'position:fixed;left:8px;right:8px;bottom:12px;z-index:2147483647;' +
          'padding:10px 12px;border-radius:10px;font:14px system-ui,sans-serif;color:#fff;' +
          'box-shadow:0 4px 16px rgba(0,0,0,.3);pointer-events:none';
        document.body.appendChild(el);
      }
      el.style.background = color || '#333';
      el.textContent = 'Auto Check-in: ' + msg;
    };
    if (document.body) pinta(); else document.addEventListener('DOMContentLoaded', pinta);
  }

  // Interceptor del POST de reclamo: se instala en document-start, antes que la app.
  const origFetch = window.fetch;
  window.fetch = async function (input) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const resp = await origFetch.apply(this, arguments);
    if (url.includes(CLAIM_PATH)) {
      resp.clone().text().then((t) => {
        if (resp.ok) { marcarHecho(); aviso('¡Plumas reclamadas! (' + resp.status + ')', '#1b8a3a'); }
        else aviso('Error ' + resp.status + ': ' + t.slice(0, 120), '#b3261e');
      });
    }
    return resp;
  };

  const botonCon = (texto) =>
    Array.from(document.querySelectorAll('button')).find((b) => (b.textContent || '').includes(texto));

  async function esperar(fn, ms) {
    const fin = Date.now() + ms;
    while (Date.now() < fin) {
      const v = fn();
      if (v) return v;
      await sleep(500);
    }
    return null;
  }

  const tokenTurnstile = () => {
    const input = Array.from(document.querySelectorAll('input[name="cf-turnstile-response"]')).find((i) => i.value);
    if (input) return input.value;
    try { return (window.turnstile && window.turnstile.getResponse && window.turnstile.getResponse()) || ''; } catch (e) { return ''; }
  };

  async function main() {
    if (yaHecho()) return;
    if (!location.pathname.includes('/store')) {
      if (REDIRIGIR_A_TIENDA) location.href = 'https://caveduck.io/es/store';
      return;
    }

    aviso('buscando el Check-in Diario...');
    const menu = await esperar(() => botonCon(TXT_MENU), 20000);
    if (!menu) return aviso('no encontré el botón de Check-in (¿sesión iniciada?)', '#b3261e');
    menu.click();

    // Antes del modal aparece el widget de Cloudflare "Verificando...".
    aviso('verificando con Cloudflare (si aparece la casilla, tócala)...');
    const boton = await esperar(() => botonCon(TXT_RECLAMAR) || botonCon(TXT_COMPLETADO), 60000);
    if (!boton) return aviso('el modal no abrió', '#b3261e');
    if (boton.textContent.includes(TXT_COMPLETADO)) {
      marcarHecho();
      return aviso('hoy ya estaba reclamado ✔', '#1b8a3a');
    }

    aviso('esperando a Cloudflare (si aparece la casilla, tócala)...');
    const token = await esperar(tokenTurnstile, 60000);
    if (!token) aviso('sin token de Turnstile; intento igualmente...', '#a15c00');

    const reclamar = botonCon(TXT_RECLAMAR);
    if (reclamar) reclamar.click();
    // El resultado lo muestra el interceptor de fetch.
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', main);
  else main();
})();
