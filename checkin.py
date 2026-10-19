import os
import cloudscraper

URL_CHECKIN = "https://caveduck.io/api/point/claim-24h-free-charge-points"
SESSION_COOKIE = os.getenv("CAVEDUCK_COOKIE")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Cookie": SESSION_COOKIE,
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://caveduck.io",
    "Referer": "https://caveduck.io/es/store"
}

scraper = cloudscraper.create_scraper()

# Enviamos json={} por si el POST espera un cuerpo vacío ({})
response = scraper.post(URL_CHECKIN, headers=headers, json={})
print(f"Estado: {response.status_code}")
print(f"Respuesta: {response.text}")