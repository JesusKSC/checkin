import os
import time
from seleniumbase import SB

SESSION_COOKIE = os.getenv("CAVEDUCK_COOKIE", "").strip()

def ejecutar_checkin():
    # headless=False junto con xvfb=True permite pasar Cloudflare Turnstile en Linux
    with SB(uc=True, headless=False, xvfb=True) as sb:
        print("1. Abriendo Caveduck...")
        sb.uc_open_with_reconnect("https://caveduck.io/es/store", 5)

        if not SESSION_COOKIE:
            raise RuntimeError("ERROR: El secret CAVEDUCK_COOKIE está vacío.")

        # Inyectar todas las cookies de sesión (incluyendo soporte para __Secure- y __Host-)
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
                    except Exception as e:
                        print(f"No se pudo agregar cookie {name}: {e}")

        print(f"Cookies inyectadas: {cookies_agregadas}")
        print("2. Recargando tienda con sesión iniciada...")
        sb.uc_open_with_reconnect("https://caveduck.io/es/store", 6)
        time.sleep(5)

        print("3. Abriendo modal 'Caveduck Check-in Diario'...")
        abierto = sb.execute_script("""
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            let node;
            while ((node = walker.nextNode())) {
                if (node.nodeValue && node.nodeValue.includes('Caveduck Check-in Diario')) {
                    const clickable = node.parentElement.closest('button, a, div[role="button"], div');
                    if (clickable) {
                        clickable.click();
                        return node.nodeValue.trim();
                    }
                }
            }
            return null;
        """)
        print(f"Elemento de menú clicado: {abierto}")

        # Esperar 7 segundos a que cargue el modal y Cloudflare Turnstile genere el token
        time.sleep(7)

        print("4. Buscando botón 'Registrarse y reclamar'...")
        resultado_boton = sb.execute_script("""
            const btns = Array.from(document.querySelectorAll('button'));
            const textos = btns.map(b => b.textContent.trim()).filter(Boolean);
            const target = btns.find(b => {
                const t = b.textContent.trim().toLowerCase();
                return (
                    t.includes('registrarse y reclamar') ||
                    t.includes('reclamar') ||
                    t.includes('registrarse') ||
                    t.includes('claim')
                ) && !t.includes('completado');
            });
            if (target) {
                target.click();
                return {clicado: true, texto: target.textContent.trim(), todos: textos};
            }
            return {clicado: false, todos: textos};
        """)
        print(f"Resultado de búsqueda de botón: {resultado_boton}")

        time.sleep(8)
        print("¡Proceso finalizado!")

if __name__ == "__main__":
    ejecutar_checkin()