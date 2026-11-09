"""Elron (Estland): python skripte/elron.py 2026-10-27
Die Seite listet alle Züge des Tages, eine Uhrzeit lässt sich nicht vorgeben."""
import re
import time
from urllib.parse import quote
from preise_csv import guess_date
from selenium_basis import click_text, deep_text, route, run, wait_for_text

START, ZIEL = route("Tallinn", "Tartu")
TIME = re.compile(r"^\d{1,2}:\d{2}$")


def fetch(driver, datum, uhrzeit):
    # Start, Ziel und Datum stehen direkt in der Adresse
    driver.get(f"https://elron.pilet.ee/en/otsing/{quote(START)}/{quote(ZIEL)}/{datum}")
    time.sleep(5)
    print("cookies:", click_text(driver, "^(Keeldu|Deny)") or "kein Banner erschienen")
    wait_for_text(driver, "Search result")
    time.sleep(3)

    text = deep_text(driver)
    text = text[text.rfind("Search result"):]  # davor stehen Cookie-Texte und die Bahnhofsliste
    return text, guess_date(text)


def parse(text):
    """Eine Verbindung: Abfahrt / Ankunft / '2h 34 min' / '16,00€' / 'Choose' / Zugnummer / Strecke."""
    rows, lines = [], [l.strip() for l in text.splitlines()]
    for i in range(len(lines) - 5):
        if not (TIME.match(lines[i]) and TIME.match(lines[i + 1])):
            continue
        dur = re.match(r"(?:(\d+)h)?\s*(?:(\d+) min)?$", lines[i + 2])
        price = re.match(r"(\d+,\d{2})€$", lines[i + 3])
        rest = lines[i + 4:i + 7] if price else lines[i + 3:i + 6]
        zug = next((l for l in rest if re.match(r"^[\d/]+$", l)), "")
        rows.append({
            "abfahrt": lines[i].zfill(5), "ankunft": lines[i + 1].zfill(5),
            "dauer_min": int(dur.group(1) or 0) * 60 + int(dur.group(2) or 0) if dur else "",
            "umstiege": "",  # in der Liste nicht pro Verbindung angegeben
            "tarif": "", "preis": price.group(1) if price else "",
            "bemerkung": "" if price else "kein Preis angezeigt", "zuege": zug,
        })
    return rows


if __name__ == "__main__":
    run("elron.ee", START, ZIEL, fetch, parse)
