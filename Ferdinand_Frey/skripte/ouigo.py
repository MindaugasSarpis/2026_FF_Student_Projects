"""OUIGO (französische Billigzüge der SNCF, Inland und Belgien): python skripte/ouigo.py 2026-10-27
Die Seite listet alle Züge des Tages; eine Uhrzeit lässt sich nicht vorgeben. Keine Zugnummern.
Seit etwa 20.10.2026 steckt das Suchformular im Shadow-DOM: "Départ"/"Arrivée" sind Knöpfe, die ein Suchfeld
öffnen; getippt wird langsam über Chrome (CDP), wie bei ns.py. Läuft mit undetected_chromedriver."""
import re
import time
import undetected_chromedriver as uc
from preise_csv import hide_window
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import (click_text, deep_click_text, deep_find, deep_text, insert_slowly, route, run, start_uc,
                            wait_for_text)

# Schreibweise wie in der Vorschlagsliste von ouigo.com
START, ZIEL = route("Paris Gare de Lyon", "Lyon Part Dieu")
MONTHS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre",
          "Novembre", "Décembre"]


def driver_uc(headless):
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,900")
    hide_window(options)
    return start_uc(options, "ouigo")


def choose_station(driver, label, station):
    """label: 'Départ' oder 'Arrivée' (Anfang der aria-label des Knopfs im Suchformular)."""
    deep_find(driver, f"button[aria-label^='{label}']")[0].click()
    time.sleep(2)
    insert_slowly(driver, station[:10])
    for _ in range(10):
        time.sleep(1)
        if deep_click_text(driver, "^" + re.escape(station) + "$"):
            print(label, "->", station)
            time.sleep(1)
            return
    raise RuntimeError(f"Bahnhof nicht in der Vorschlagsliste: {station}")


def fetch(driver, datum, uhrzeit):
    year, month, day = datum.split("-")
    driver.get("https://www.ouigo.com/")
    time.sleep(6)
    click_text(driver, "^(Continuer sans accepter|Tout refuser|Refuser)", "button,a,span")
    if "captcha-delivery" in driver.page_source:
        raise RuntimeError("OUIGO verlangt ein Captcha - Abfrage abgebrochen")
    choose_station(driver, "Départ", START)
    choose_station(driver, "Arrivée", ZIEL)

    # Kalender: erst "Aller simple", sonst zählt der Klick als Rückreisetag. Jeder Tag heißt z. B.
    # "mardi 24 novembre 2026, à partir de 19 €"; bei Bedarf monatsweise vorblättern
    deep_find(driver, "button[aria-label^='Aller']")[0].click()
    time.sleep(2)
    deep_click_text(driver, "^Aller simple$")
    time.sleep(1)
    label = f" {int(day)} {MONTHS[int(month) - 1].lower()} {year}"
    for _ in range(12):
        cells = deep_find(driver, f"button[aria-label*='{label}']")
        if cells:
            cells[0].click()
            break
        nxt = deep_find(driver, "button[aria-label*='suivant']")
        if not nxt:
            raise RuntimeError(f"Tag {datum} nicht im Kalender gefunden")
        nxt[0].click()
        time.sleep(1)
    else:
        raise RuntimeError(f"Tag {datum} nicht im Kalender gefunden")
    time.sleep(1)
    if not deep_click_text(driver, "^Valider ma date$"):
        raise RuntimeError("Knopf 'Valider ma date' nicht gefunden")
    time.sleep(2)
    deep_click_text(driver, "^Rechercher$")
    WebDriverWait(driver, 40).until(lambda d: "journey-results" in d.current_url)
    wait_for_text(driver, "€", 30)
    time.sleep(3)

    text = deep_text(driver)
    shown = re.search(r"\S+ (\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})", text)
    return text, f"{shown.group(3)}-{MONTHS.index(shown.group(2)) + 1:02d}-{int(shown.group(1)):02d}" if shown else ""


def parse(text):
    """Eine Verbindung: Abfahrt / Bahnhof / Ankunft / Bahnhof / '35€' / '1h56' / 'Grande Vitesse'."""
    text = text[text.find("Nouveaux prix") if "Nouveaux prix" in text else 0:]
    lines = [l.strip() for l in text.splitlines()]
    rows = []
    for i in range(len(lines) - 5):
        if not (re.fullmatch(r"\d{1,2}:\d{2}", lines[i]) and re.fullmatch(r"\d{1,2}:\d{2}", lines[i + 2])):
            continue
        price = re.fullmatch(r"(\d+(?:,\d{2})?)\s*€", lines[i + 4])
        dur = re.fullmatch(r"(\d+)h(\d{2})", lines[i + 5]) or re.fullmatch(r"(\d+)h(\d{2})", lines[i + 4])
        # Unter „Trains avec correspondances“ steht nach der Dauer z. B. „1 correspondance“ (bis 26.10.2026 als
        # Direktzug mit 0 Umstiegen gespeichert, z. B. Lyon 16:06 – Paris 20:26 für 104–158 €)
        umst = next((re.match(r"(\d+) correspondance", l) for l in lines[i + 5:i + 8]
                     if re.match(r"\d+ correspondance", l)), None)
        rows.append({
            "abfahrt": lines[i].zfill(5), "ankunft": lines[i + 2].zfill(5),
            "dauer_min": int(dur.group(1)) * 60 + int(dur.group(2)) if dur else "",
            "umstiege": int(umst.group(1)) if umst else 0, "tarif": "",
            "preis": f"{float(price.group(1).replace(',', '.')):.2f}".replace(".", ",") if price else "",
            "bemerkung": "" if price else "kein Preis angezeigt",
            "zuege": f"{lines[i + 1]} - {lines[i + 3]}",  # Bahnhöfe, da OUIGO keine Zugnummern zeigt
        })
    return rows


if __name__ == "__main__":
    run("ouigo.com", START, ZIEL, fetch, parse, driver_factory=driver_uc)
