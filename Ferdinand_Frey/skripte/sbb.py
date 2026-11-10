import re
import sys
import time
from datetime import datetime
from urllib.parse import quote
from preise_csv import VISIBLE, append_rows, guess_date, read_args
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import deep_text, route, save_page, start_driver

# z. B.: python skripte/sbb.py 2026-10-27 08:00
out, headless, datum, uhrzeit = read_args("sbb.png")
if not datum:
    datum, uhrzeit = datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M")

URL = "https://www.sbb.ch/de"
START, ZIEL = route("Zürich HB", "München Hbf")


def parse(text):
    """Jede Verbindung hat bei sbb.ch eine Zusammenfassungszeile:
    'Abfahrt: 09:32, Auf Gl. 34, Zug, EC , Richtung ..., Sparbillette ab CHF 61.00, Ankunft: 13:35,
    Reisedauer 4 Stunden 3 Minuten, 2 mal umsteigen, ...'. Der erste Zug steht danach unter 'Zug'."""
    rows, lines = [], [l.strip() for l in text.splitlines()]
    for i, line in enumerate(lines):
        dep, arr = re.match(r"Abfahrt: (\d{1,2}:\d{2}),", line), re.search(r"Ankunft: (\d{1,2}:\d{2})", line)
        if not (dep and arr):
            continue
        dur = re.search(r"Reisedauer (?:(\d+) Stunden?)?\s*(?:(\d+) Minuten?)?", line)
        changes = re.search(r"(\d+) mal umsteigen", line)
        price = re.search(r", ([^,]*?)\s*ab CHF ([\d.]+)", line)
        zug = ""
        for j in range(i + 1, min(i + 12, len(lines) - 1)):
            if lines[j].startswith("Abfahrt: "):
                break
            if lines[j] == "Zug":
                zug = lines[j + 1]
                break
        rows.append({
            "abfahrt": dep.group(1).zfill(5), "ankunft": arr.group(1).zfill(5),
            "dauer_min": int(dur.group(1) or 0) * 60 + int(dur.group(2) or 0) if dur else "",
            "umstiege": int(changes.group(1)) if changes else 0,
            "tarif": price.group(1) if price else "",
            "preis": f"{float(price.group(2)):.2f}".replace(".", ",") if price else "",
            "bemerkung": "" if price else "kein Preis angezeigt",
            "zuege": zug,  # sbb.ch zeigt in der Liste nur den ersten Zug
        })
    return rows


def reject_cookies(driver):
    try:
        WebDriverWait(driver, 8).until(
            lambda d: d.find_element(By.CSS_SELECTOR, "#onetrust-reject-all-handler")
        ).click()
        print("cookies: abgelehnt")
    except Exception:
        print("cookies: kein Banner erschienen")


driver = start_driver(headless)

try:
    # Die Bahnhofsnamen löst sbb.ch selbst auf und schreibt sie als stops=... in die Adresse
    # (headless liefert sbb.ch nur eine leere Seite, deshalb mit sichtbarem Fenster starten)
    driver.get(f"{URL}?von={quote(START)}&nach={quote(ZIEL)}&date={datum}&time={uhrzeit}&moment=DEPARTURE")
    reject_cookies(driver)
    WebDriverWait(driver, 20).until(lambda d: "stops=" in d.current_url)
    stops = re.search(r"stops=([^&]*)", driver.current_url).group(1)

    # reduction=none: Vollpreis statt der voreingestellten Halbtax-Preise
    driver.get(f"{URL}?date={datum}&time={uhrzeit.replace(':', '_')}&moment=dep&stops={stops}&day={datum}&reduction=none")
    try:
        WebDriverWait(driver, 30).until(lambda d: "Abfahrt: " in deep_text(d))
        # Preise werden einige Sekunden nach den Verbindungen nachgeladen (manche Strecken haben keine)
        try:
            WebDriverWait(driver, 15).until(lambda d: "ab CHF" in deep_text(d))
        except Exception:
            print("Nach 15 s keine Preise auf der Seite.")
        time.sleep(2)
    except Exception:
        print("Nach 30 s noch keine Verbindungen auf der Seite.")

    print("url:", driver.current_url)
    print("title:", driver.title)

    text = save_page(driver, "sbb_ergebnisseite")
    rows = parse(text)
    print("Verbindungen gefunden:", len(rows))
    for r in rows:
        print("  ", r["abfahrt"], "-", r["ankunft"], r["preis"] or r["bemerkung"])

    reise_datum = guess_date(text)
    if reise_datum != datum:
        print(f"NICHT GESPEICHERT: Seite zeigt {reise_datum or 'kein Datum'} statt {datum}.")
    elif rows:
        append_rows(rows, reise_datum, START, ZIEL, quelle="sbb.ch", waehrung="CHF")

    driver.save_screenshot(out)
    if VISIBLE and sys.stdin.isatty():
        input("Drücke Enter, um den Browser zu schließen...")
finally:
    driver.quit()
