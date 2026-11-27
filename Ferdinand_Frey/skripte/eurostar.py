"""Eurostar: python skripte/eurostar.py 2026-10-27
Die Seite listet alle Züge des Tages, eine Uhrzeit lässt sich nicht vorgeben. Gespeichert wird der Preis
der günstigsten Klasse "Eurostar Standard". Ohne Fenster (headless) verlangt die Seite ein Captcha;
das Skript läuft deshalb nur mit normalem Fenster außerhalb des Bildschirms."""
import re
import time
from preise_csv import MONTHS
from selenium.webdriver.common.by import By
from selenium_basis import deep_text, route, run, wait_for_text

START, ZIEL = route("Köln Hbf", "Paris Nord")
# Bahnhofsnummern für die Adresse der Suche
STATIONS = {
    "Köln Hbf": "8015458", "Paris Nord": "8727100", "Bruxelles-Midi": "8814001",
    "Amsterdam Centraal": "8400058", "London St Pancras": "7015400",
}


def fetch(driver, datum, uhrzeit):
    # Start, Ziel und Datum stehen direkt in der Adresse
    driver.get(f"https://www.eurostar.com/search/de-de?adult=1&origin={STATIONS[START]}"
               f"&destination={STATIONS[ZIEL]}&outbound={datum}")
    time.sleep(6)
    try:
        driver.find_element(By.ID, "didomi-notice-disagree-button").click()
        print("cookies: nur erforderliche")
    except Exception:
        print("cookies: kein Banner erschienen")
    if "Challenge" in driver.title:
        raise RuntimeError("Eurostar verlangt ein Captcha - Abfrage abgebrochen")
    wait_for_text(driver, "Reiseangaben")
    time.sleep(3)

    # Der gewählte Tag ist der markierte Reiter der Datumsleiste, z. B. "So., 25. Okt."
    selected = driver.execute_script(
        "const e = document.querySelector('[data-testid=\"calendarDays\"] [aria-current]');"
        "return e ? e.innerText : '';") or ""
    shown = re.search(r"(\d{1,2})\. (" + "|".join(MONTHS) + ")", selected)
    shown = f"{datum[:4]}-{MONTHS.index(shown.group(2)) + 1:02d}-{int(shown.group(1)):02d}" if shown else ""
    return deep_text(driver), shown


def parse(text):
    """Eine Verbindung: 'Reiseangaben' / 'Abfahrt um:' / '06:39' / 'Ankunft um:' / '10:20' / 'Reisedauer:' /
    '3' / 'St.' / 'Stunden' / '41' / 'Min.' / 'Minuten' / 'Direktzug' / '85' / '€' / ... /
    'Abfahrt um: 06:39, Eurostar Standard, ...' / ... / 'ER 9414'."""
    rows = []
    for block in text.split("\nReiseangaben\n")[1:]:
        dep, arr = re.search(r"Abfahrt um:\n(\d{1,2}:\d{2})", block), re.search(r"Ankunft um:\n(\d{1,2}:\d{2})", block)
        if not (dep and arr):
            continue
        hours, minutes = re.search(r"\n(\d+)\nSt\.\n", block), re.search(r"\n(\d+)\nMin\.\n", block)
        changes = re.search(r"(\d+) Umstieg", block)
        # Der Standard-Preis steht direkt vor der Zeile '..., Eurostar Standard, ...'
        before = block[:block.find("Eurostar Standard,")] if "Eurostar Standard," in block else ""
        marks = list(re.finditer(r"(\d+(?:,\d{2})?)\n€|Nicht verfügbar", before))
        price = marks[-1].group(1) if marks and marks[-1].group(1) else ""
        rows.append({
            "abfahrt": dep.group(1).zfill(5), "ankunft": arr.group(1).zfill(5),
            "dauer_min": int(hours.group(1) if hours else 0) * 60 + int(minutes.group(1) if minutes else 0),
            "umstiege": int(changes.group(1)) if changes else 0,
            "tarif": "Eurostar Standard" if price else "",
            "preis": f"{float(price.replace(',', '.')):.2f}".replace(".", ",") if price else "",
            "bemerkung": "" if price else "Standard nicht verfügbar",
            "zuege": " + ".join(dict.fromkeys(re.findall(r"^ER \d+$", block, re.M))),
        })
    return rows


if __name__ == "__main__":
    run("eurostar.com", START, ZIEL, fetch, parse)
