import os
import sys
import time
from datetime import date
import undetected_chromedriver as uc
from pfade import SEITEN
from preise_csv import VISIBLE, append_rows, guess_date, hide_window, keep_text, parse, read_args
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import click_text, start_uc

# Argumente einlesen
# z. B.: python skripte/oebb.py 2026-10-27 08:00
out, headless, datum, uhrzeit = read_args("oebb.png")

URL = "https://shop.oebbtickets.at/de/ticket"
# Strecke: Vorgabe hier, oder von alle_strecken.py über BAHN_START / BAHN_ZIEL gesetzt
START = START_TEXT = os.environ.get("BAHN_START", "München Hbf")
ZIEL = ZIEL_TEXT = os.environ.get("BAHN_ZIEL", "Wien Hbf")

UID = '[data-unique-id="{}"]'

def body_text(driver):
    return driver.find_element(By.TAG_NAME, "body").text


def dump_page(driver, path):
    """Speichert das HTML der Seite, damit man die Feldnamen nachsehen kann."""
    with open(SEITEN / path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("Seite gespeichert:", path)


def wait_for_security_check(driver):
    """Die Cloudflare-Prüfung wird nicht umgangen: im Fenster selbst bestätigen, das Skript wartet.
    Gibt False zurück, wenn sie nicht freigibt (zählt dann als blockiert, nicht als Fehler)."""
    if "Moment" not in driver.title:
        return True
    seconds = 120 if VISIBLE else 60  # ohne Fenster bestätigt niemand; was nicht von selbst durchgeht, bleibt hängen
    print(f"Sicherheitsprüfung: wartet bis zu {seconds} s (mit 'sichtbar' starten, um selbst zu bestätigen)...")
    try:
        WebDriverWait(driver, seconds).until(lambda d: "Moment" not in d.title)
    except TimeoutException:
        return False
    time.sleep(3)
    return True


def accept_cookies(driver):
    for _ in range(10):
        if click_text(driver, "Alle Cookies akzeptieren"):
            print("cookies: alle akzeptiert")
            return
        time.sleep(1)
    print("cookies: kein Banner erschienen")


def stop_if_forbidden(driver):
    # Seit 27.10.2026 abends lehnt der ÖBB-Server Abfragen oft mit dem Fenster „Forbidden – Ein Fehler ist aufgetreten“
    # ab, meist bei der Suche, manchmal schon auf der Startseite. Das ist eine Sperre, kein Fehler im Skript;
    # alle_strecken.py setzt ÖBB dann einige Stunden aus. Nicht umgehen.
    if "Forbidden" in body_text(driver).splitlines():
        print("BLOCKIERT: oebb.at antwortet mit „Forbidden“, vermutlich SPERRE DER ADRESSE.", flush=True)
        driver.save_screenshot(out)
        sys.exit()


def fill_station(driver, uid, text, station):
    inp = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, UID.format(uid))))
    inp.click()
    time.sleep(0.5)

    # Menschlicheres Tippen
    for ch in text:
        inp.send_keys(ch)
        time.sleep(0.08)

    time.sleep(1)
    option = (By.XPATH, f'//mat-option[contains(., "{station}")]')
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(option)).click()
    print(uid, "->", inp.get_attribute("value"))


def wait_for_results(driver):
    try:
        WebDriverWait(driver, 30).until(lambda d: "€" in body_text(d))
    except Exception:
        print("Nach 30 s noch keine Preise auf der Seite.")


def shown_date(driver):
    """Das gewählte Reisedatum steht im Knopf 'nächster Tag' der Ergebnisseite."""
    btn = driver.find_element(By.CSS_SELECTOR, UID.format("travelDateComponentNextDay"))
    return guess_date(btn.get_attribute("aria-label") or "")


def set_date(driver, datum, uhrzeit):
    """Trägt Datum und Uhrzeit vor der Suche ein; die Felder erscheinen, sobald beide Bahnhöfe gewählt sind."""
    year, month, day = datum.split("-")
    hour, minute = uhrzeit.split(":")
    # Erst den Tag auf 01: Am 31.10. nahm die Seite Monat 11 sonst vermutlich nicht an („31.11.“) und suchte am 01.10.
    fields = [
        ("dateComponentInputDay", "01"), ("dateComponentInputYear", year), ("dateComponentInputMonth", month),
        ("dateComponentInputDay", day),
        ("timeComponentInputHour", hour), ("timeComponentInputMinute", minute),
    ]
    for uid, value in fields:
        inp = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, UID.format(uid))))
        inp.click()
        inp.send_keys(Keys.CONTROL, "a")
        inp.send_keys(value)
        time.sleep(0.5)


# Browser konfigurieren
options = uc.ChromeOptions()
if headless:
    options.add_argument("--headless=new")
options.add_argument("--window-size=1280,800")
hide_window(options)
options.add_argument("--lang=de-DE")

# Starten
driver = start_uc(options, "oebb")

try:
    driver.get(URL)
    if not wait_for_security_check(driver):
        print("BLOCKIERT: oebb.at hat die Sicherheitsprüfung nicht freigegeben.")
        driver.save_screenshot(out)
        sys.exit()
    accept_cookies(driver)
    time.sleep(3)
    stop_if_forbidden(driver)

    try:
        fill_station(driver, "travelStationFromInput", START_TEXT, START)
        fill_station(driver, "travelStationToInput", ZIEL_TEXT, ZIEL)
        time.sleep(1)
        if datum:
            set_date(driver, datum, uhrzeit)
        driver.find_element(By.CSS_SELECTOR, UID.format("travelFindServicesSplitButton")).click()
    except Exception as e:
        print("Automatisches Ausfüllen fehlgeschlagen:", type(e).__name__)
        dump_page(driver, "oebb_suchseite.html")
        if not (VISIBLE and sys.stdin.isatty()):
            raise
        input(f"Bitte {START} -> {ZIEL} im Browserfenster selbst suchen, dann hier Enter drücken...")

    wait_for_results(driver)
    stop_if_forbidden(driver)

    print("url:", driver.current_url)
    print("title:", driver.title)

    body = body_text(driver)
    dump_page(driver, "oebb_ergebnisseite.html")
    with open(SEITEN / "oebb_ergebnisseite.txt", "w", encoding="utf-8") as f:
        f.write(body)
    keep_text(body)
    rows = parse(body)
    print("Verbindungen gefunden:", len(rows))
    for r in rows:
        print("  ", r["abfahrt"], "-", r["ankunft"], r["preis"] or r["bemerkung"])
    try:
        reise_datum = shown_date(driver) or date.today().isoformat()
    except Exception:
        reise_datum = date.today().isoformat()
    if datum and reise_datum != datum:
        print(f"NICHT GESPEICHERT: Seite zeigt {reise_datum} statt {datum}.")
    elif rows:
        append_rows(rows, reise_datum, START, ZIEL, quelle="oebb.at")

    driver.save_screenshot(out)
    if VISIBLE and sys.stdin.isatty():
        input("Drücke Enter, um den Browser zu schließen...")
finally:
    driver.quit()
