import os
import time
from seleniumbase import SB

SESSION_COOKIE = os.getenv("CAVEDUCK_COOKIE", "").strip()

def ejecutar_checkin():
    # uc=True activa el modo Undetected para pasar Cloudflare Turnstile
    with SB(uc=True, headless=True) as sb:
        print("1. Abriendo Caveduck...")
        sb.uc_open_with_reconnect("https://caveduck.io/es/store", 4)
        
        # Inyectar todas las cookies de tu sesión
        if SESSION_COOKIE:
            for item in SESSION_COOKIE.split(";"):
                if "=" in item:
                    name, value = item.strip().split("=", 1)
                    try:
                        sb.driver.add_cookie({
                            "name": name,
                            "value": value,
                            "domain": ".caveduck.io",
                            "path": "/"
                        })
                    except Exception:
                        pass

        print("2. Recargando tienda con tu sesión iniciada...")
        sb.uc_open_with_reconnect("https://caveduck.io/es/store", 5)
        time.sleep(5)

        # Cuando entras a /store con sesión iniciada, Caveduck suele disparar el reclamo automático
        # o mostrar el menú "Caveduck Check-in Diario"
        print("3. Buscando botón de Check-in Diario...")
        sb.execute_script("""
            const elems = Array.from(document.querySelectorAll('div, span, p, button'));
            const menu = elems.find(el => el.textContent.includes('Check-in Diario') || el.textContent.includes('Daily Check-in'));
            if (menu) menu.click();
        """)
        time.sleep(4)

        print("4. Presionando botón de reclamo si está disponible...")
        sb.execute_script("""
            const btns = Array.from(document.querySelectorAll('button'));
            const claimBtn = btns.find(b => {
                const t = b.textContent.toLowerCase();
                return (t.includes('registro') || t.includes('check-in') || t.includes('claim') || t.includes('pluma')) && !t.includes('completado');
            });
            if (claimBtn) claimBtn.click();
        """)
        time.sleep(5)
        print("¡Proceso completado! Título de página:", sb.get_title())

if __name__ == "__main__":
    ejecutar_checkin()