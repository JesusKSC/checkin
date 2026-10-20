import json
import os
import sys
import time
from seleniumbase import SB

SESSION_COOKIE = os.getenv("CAVEDUCK_COOKIE", "").strip()
STORE_URL = "https://caveduck.io/es/store"
CLAIM_PATH = "/api/point/claim-24h-free-charge-points"

XPATH_MENU = "//button[contains(., 'Caveduck Check-in Diario')]"
XPATH_RECLAMAR = "//button[contains(., 'Registrarse y reclamar')]"
XPATH_COMPLETADO = "//button[contains(., 'Registro diario completado')]"

# Interceptor de fetch + XHR + console. Se registra vía CDP para que exista
# desde el primer script de la página (así también capturamos las llamadas
# /api/ de la carga inicial, donde suele venir el saldo de Plumas).
INTERCEPTOR_JS = r"""
(() => {
  if (window.__cdHooked) return;
  window.__cdHooked = true;
  window.__cdCaptures = [];
  window.__cdConsole = [];

  const MAX_BODY = 4000;
  const push = (entry) => {
    try { window.__cdCaptures.push(entry); } catch (e) {}
  };
  const interesting = (url) => /\/api\//.test(url || '');
  const maskBody = (body) => {
    if (typeof body !== 'string') return body == null ? null : '[non-string body]';
    try {
      const o = JSON.parse(body);
      if (o && typeof o.turnstileToken === 'string') {
        const t = o.turnstileToken;
        o.turnstileToken = t ? `${t.slice(0, 12)}...(len=${t.length})` : '(VACÍO)';
      }
      return JSON.stringify(o).slice(0, MAX_BODY);
    } catch (e) { return body.slice(0, MAX_BODY); }
  };

  const origFetch = window.fetch;
  window.fetch = async function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const method = (init && init.method) || (input && input.method) || 'GET';
    const reqBody = init && init.body;
    const resp = await origFetch.apply(this, arguments);
    if (interesting(url)) {
      try {
        const text = await resp.clone().text();
        push({ via: 'fetch', t: Date.now(), method, url, status: resp.status,
               request: maskBody(reqBody), response: text.slice(0, MAX_BODY) });
      } catch (e) {
        push({ via: 'fetch', t: Date.now(), method, url, status: resp.status, error: String(e) });
      }
    }
    return resp;
  };

  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (method, url) {
    this.__cd = { method, url: String(url) };
    return origOpen.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function (body) {
    const info = this.__cd;
    if (info && interesting(info.url)) {
      this.addEventListener('loadend', () => {
        let text = '';
        try { text = typeof this.responseText === 'string' ? this.responseText : ''; } catch (e) {}
        push({ via: 'xhr', t: Date.now(), method: info.method, url: info.url, status: this.status,
               request: maskBody(body), response: text.slice(0, MAX_BODY) });
      });
    }
    return origSend.apply(this, arguments);
  };

  // Los errores de Turnstile (p.ej. "[Cloudflare Turnstile] Error: 600010")
  // se imprimen en la consola de la página principal.
  for (const level of ['error', 'warn']) {
    const orig = console[level];
    console[level] = function (...args) {
      try {
        const msg = args.map(a => (a && a.message) || String(a)).join(' ');
        window.__cdConsole.push(`[${level}] ${msg}`.slice(0, 500));
      } catch (e) {}
      return orig.apply(this, args);
    };
  }
  window.addEventListener('error', (ev) => {
    window.__cdConsole.push(`[onerror] ${ev.message || ''}`.slice(0, 500));
  });
})();
"""

ESTADO_TURNSTILE_JS = r"""
const inputs = Array.from(document.querySelectorAll('input[name="cf-turnstile-response"]'));
const token = inputs.map(i => i.value).find(v => v) || '';
let apiToken = '';
try { if (window.turnstile && window.turnstile.getResponse) apiToken = window.turnstile.getResponse() || ''; } catch (e) {}
const iframes = Array.from(document.querySelectorAll('iframe'))
  .filter(f => (f.src || '').includes('challenges.cloudflare.com'))
  .map(f => { const r = f.getBoundingClientRect(); return {w: Math.round(r.width), h: Math.round(r.height)}; });
const recursos = performance.getEntriesByType('resource')
  .filter(e => e.name.includes('challenges.cloudflare.com'))
  .map(e => ({url: e.name.split('?')[0].slice(0, 140), status: e.responseStatus || 0}));
return {
  inputs: inputs.length,
  token_len: (token || apiToken).length,
  token_prefix: (token || apiToken).slice(0, 8),
  turnstile_global: !!window.turnstile,
  iframes: iframes,
  recursos_cf: recursos.slice(-15),
};
"""

# Heurística para el saldo: busca números junto a textos/atributos de Plumas.
SALDO_DOM_JS = r"""
const out = [];
const re = /(pluma|feather|point)/i;
for (const el of document.querySelectorAll('header *, nav *, [class*="point" i], [class*="feather" i], img[alt], svg[aria-label]')) {
  const label = [el.getAttribute('alt'), el.getAttribute('aria-label'), el.getAttribute('title'), el.className && el.className.baseVal === undefined ? el.className : ''].join(' ');
  const txt = (el.textContent || '').trim();
  if ((re.test(label) || re.test(txt)) && /\d/.test(txt) && txt.length < 60) out.push(txt);
  if (re.test(label) && el.parentElement) {
    const p = (el.parentElement.textContent || '').trim();
    if (/\d/.test(p) && p.length < 60) out.push(p);
  }
}
return Array.from(new Set(out)).slice(0, 10);
"""


def inyectar_cookies(sb):
    cookies_agregadas = 0
    for item in SESSION_COOKIE.split(";"):
        if "=" in item:
            name, value = item.strip().split("=", 1)
            cookie_data = {
                "name": name,
                "value": value,
                "path": "/",
                "secure": True
            }
            if not name.startswith("__Host-"):
                cookie_data["domain"] = ".caveduck.io"
            try:
                sb.driver.add_cookie(cookie_data)
                cookies_agregadas += 1
            except Exception:
                try:
                    cookie_data.pop("domain", None)
                    sb.driver.add_cookie(cookie_data)
                    cookies_agregadas += 1
                except Exception:
                    pass
    return cookies_agregadas


def asegurar_interceptor(sb):
    if not sb.execute_script("return !!window.__cdHooked;"):
        print("   (interceptor no presente tras la carga; inyectándolo con execute_script)")
        sb.execute_script(INTERCEPTOR_JS)


def capturas(sb):
    try:
        return sb.execute_script("return window.__cdCaptures || [];") or []
    except Exception as e:
        print(f"   No se pudieron leer las capturas: {e}")
        return []


def logs_consola(sb):
    try:
        return sb.execute_script("return window.__cdConsole || [];") or []
    except Exception:
        return []


def buscar_numeros(obj, ruta=""):
    """Devuelve pares (ruta, valor) cuyas claves suenan a saldo de puntos."""
    encontrados = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            r = f"{ruta}.{k}" if ruta else k
            if isinstance(v, (int, float)) and not isinstance(v, bool) and any(
                p in k.lower() for p in ("point", "balance", "feather", "pluma")
            ):
                encontrados.append((r, v))
            else:
                encontrados.extend(buscar_numeros(v, r))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:20]):
            encontrados.extend(buscar_numeros(v, f"{ruta}[{i}]"))
    return encontrados


def imprimir_saldo(sb, etiqueta):
    print(f"--- Saldo de Plumas ({etiqueta}) ---")
    candidatos = []
    for c in capturas(sb):
        try:
            data = json.loads(c.get("response") or "")
        except Exception:
            continue
        for ruta, valor in buscar_numeros(data):
            candidatos.append(f"{c['url'].split('?')[0]} -> {ruta} = {valor}")
    if candidatos:
        for linea in candidatos[:15]:
            print(f"   API: {linea}")
    else:
        print("   API: no se encontraron campos de saldo en las respuestas /api/ capturadas.")
    try:
        dom = sb.execute_script(SALDO_DOM_JS)
        print(f"   DOM: {dom}")
    except Exception as e:
        print(f"   DOM: error leyendo saldo: {e}")
    urls = sorted({c["url"].split("?")[0] for c in capturas(sb)})
    print(f"   Endpoints /api/ vistos: {urls}")


def esperar_turnstile(sb, max_segundos=20):
    """Espera a que Turnstile entregue un token; si aparece un widget visible, intenta clicarlo."""
    print("5. Esperando a Cloudflare Turnstile...")
    intento_click = False
    estado = {}
    for segundo in range(max_segundos):
        try:
            estado = sb.execute_script(ESTADO_TURNSTILE_JS)
        except Exception as e:
            print(f"   Error leyendo estado de Turnstile: {e}")
            estado = {}
        if estado.get("token_len"):
            print(f"   Token Turnstile listo en ~{segundo}s (len={estado['token_len']}, prefijo={estado['token_prefix']}...)")
            return True
        iframes_visibles = [f for f in estado.get("iframes", []) if f["w"] > 0 and f["h"] > 0]
        if iframes_visibles and not intento_click and segundo >= 4:
            print(f"   Widget Turnstile visible {iframes_visibles}; intentando uc_gui_click_captcha()...")
            intento_click = True
            try:
                sb.uc_gui_click_captcha()
            except Exception as e:
                print(f"   uc_gui_click_captcha falló: {e}")
        time.sleep(1)
    print(f"   Sin token tras {max_segundos}s. Último estado: {json.dumps(estado, ensure_ascii=False)}")
    return False


def ejecutar_checkin():
    if not SESSION_COOKIE:
        raise RuntimeError("ERROR: El secret CAVEDUCK_COOKIE está vacío.")

    exito = False
    with SB(uc=True, headless=False, xvfb=True) as sb:
        print("1. Abriendo Caveduck...")
        sb.uc_open_with_reconnect(STORE_URL, 5)

        print(f"Cookies inyectadas: {inyectar_cookies(sb)}")

        try:
            sb.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument", {"source": INTERCEPTOR_JS}
            )
            print("Interceptor registrado vía CDP.")
        except Exception as e:
            print(f"No se pudo registrar el interceptor vía CDP ({e}); se inyectará después de cargar.")

        print("2. Recargando tienda con sesión iniciada...")
        sb.uc_open_with_reconnect(STORE_URL, 6)
        time.sleep(6)
        asegurar_interceptor(sb)
        imprimir_saldo(sb, "ANTES")

        if sb.is_element_present(XPATH_COMPLETADO):
            print("El check-in de hoy ya figura como completado (sin abrir modal).")

        print("3. Abriendo el modal 'Caveduck Check-in Diario'...")
        if not sb.is_element_present(XPATH_MENU):
            sb.save_screenshot("debug.png")
            raise RuntimeError("No se encontró el botón 'Caveduck Check-in Diario'. ¿Sesión caducada?")
        try:
            sb.uc_click(XPATH_MENU)
        except Exception:
            sb.click(XPATH_MENU)

        # Al pulsar el menú, Caveduck muestra primero un widget Turnstile ("Verificando...")
        # y solo abre el modal cuando éste se resuelve.
        print("4. Esperando Turnstile + modal (hasta 60s)...")
        modal_abierto = False
        intento_captcha = False
        estado = {}
        for segundo in range(60):
            if sb.is_element_present(f"{XPATH_RECLAMAR} | {XPATH_COMPLETADO}"):
                print(f"   Modal abierto a los ~{segundo}s.")
                modal_abierto = True
                break
            try:
                estado = sb.execute_script(ESTADO_TURNSTILE_JS)
            except Exception:
                estado = {}
            iframes_visibles = [f for f in estado.get("iframes", []) if f["w"] > 0 and f["h"] > 0]
            if segundo % 10 == 0:
                print(f"   t={segundo}s token_len={estado.get('token_len')} iframes={estado.get('iframes')}")
            if iframes_visibles and not intento_captcha and segundo >= 6:
                print("   Widget Turnstile visible; intentando uc_gui_click_captcha()...")
                intento_captcha = True
                try:
                    sb.uc_gui_click_captcha()
                except Exception as e:
                    print(f"   uc_gui_click_captcha falló: {e}")
            if segundo == 30:
                print("   Reintentando clic en el menú...")
                try:
                    sb.click(XPATH_MENU)
                except Exception:
                    pass
            time.sleep(1)

        if not modal_abierto:
            botones = sb.execute_script(
                "return Array.from(document.querySelectorAll('button')).map(b => b.textContent.trim()).filter(Boolean);"
            )
            print(f"Botones en pantalla: {botones}")
            print(f"Último estado Turnstile: {json.dumps(estado, ensure_ascii=False)}")
            for linea in logs_consola(sb)[-25:]:
                print(f"   consola: {linea}")
            sb.save_screenshot("debug.png")
            raise RuntimeError("El modal no abrió: Turnstile no se resolvió (probable bloqueo de IP de GitHub).")

        if sb.is_element_present(XPATH_COMPLETADO) and not sb.is_element_present(XPATH_RECLAMAR):
            print("✅ 'Registro diario completado': hoy ya se había reclamado. Nada que hacer.")
            sb.save_screenshot("debug.png")
            return True

        # Margen fijo para que Turnstile arranque, y luego sondeo del token.
        time.sleep(8)
        token_ok = esperar_turnstile(sb)
        if not token_ok:
            print("   ⚠️ Se clicará igualmente para registrar la respuesta real de la API.")

        n_antes = len(capturas(sb))
        print("6. Presionando 'Registrarse y reclamar'...")
        try:
            sb.uc_click(XPATH_RECLAMAR)
        except Exception:
            sb.click(XPATH_RECLAMAR)

        print("7. Esperando la respuesta de claim-24h-free-charge-points...")
        respuesta_claim = None
        for _ in range(25):
            nuevas = capturas(sb)[n_antes:]
            respuesta_claim = next((c for c in nuevas if CLAIM_PATH in c.get("url", "")), None)
            if respuesta_claim:
                break
            time.sleep(1)

        if respuesta_claim:
            print("===== RESPUESTA DEL CLAIM =====")
            print(f"   {respuesta_claim['method']} {respuesta_claim['url']} (vía {respuesta_claim['via']})")
            print(f"   Status: {respuesta_claim.get('status')}")
            print(f"   Request (token enmascarado): {respuesta_claim.get('request')}")
            print(f"   Response: {respuesta_claim.get('response')}")
            print("================================")
            exito = 200 <= int(respuesta_claim.get("status") or 0) < 300
        else:
            print("❌ No se capturó ninguna llamada a claim-24h-free-charge-points.")
            otras = [f"{c['method']} {c['url'].split('?')[0]} -> {c['status']}" for c in capturas(sb)[n_antes:]]
            print(f"   Otras llamadas /api/ tras el clic: {otras}")

        consola = logs_consola(sb)
        if consola:
            print("--- Consola (error/warn) de la página ---")
            for linea in consola[-25:]:
                print(f"   {linea}")

        print(f"   Estado del botón tras el clic: completado={sb.is_element_present(XPATH_COMPLETADO)}")
        sb.save_screenshot("debug.png")

        print("8. Recargando para leer el saldo final...")
        sb.uc_open_with_reconnect(STORE_URL, 6)
        time.sleep(6)
        asegurar_interceptor(sb)
        imprimir_saldo(sb, "DESPUÉS")

    return exito


if __name__ == "__main__":
    ok = ejecutar_checkin()
    print("¡Proceso finalizado!" if ok else "Proceso finalizado SIN confirmar el reclamo.")
    sys.exit(0 if ok else 1)
