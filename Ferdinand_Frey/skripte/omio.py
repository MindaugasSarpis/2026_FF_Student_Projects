"""Omio (Vermittler, verkauft Tickets vieler Bahnen): python skripte/omio.py 2026-11-09 08:00
Läuft mit undetected_chromedriver in einem Fenster außerhalb des Bildschirms. Omio zeigt die Züge ab 8:00 Uhr;
eine andere Uhrzeit lässt sich nicht vorgeben. Mit 'View trains after' werden weitere Züge nachgeladen."""
import re
import time
from datetime import date
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from preise_csv import hide_window
from selenium_basis import click_text, deep_text, route, run, start_uc, type_slowly

# Englische Städtenamen wie in der Vorschlagsliste von omio.com; gewählt wird die ganze Stadt (erster Vorschlag),
# nicht ein einzelner Halt - der zweite Vorschlag ist manchmal ein Busbahnhof oder Flughafen
START, ZIEL = route("Munich", "Vienna")
WEITERE = 2  # so oft "View trains after" klicken (je Klick etwa 4 Züge mehr)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Cookie-Banner (Usercentrics, im Shadow-DOM): ablehnen, wenn es einen solchen Knopf gibt
DENY = """
const host = document.querySelector('#usercentrics-cmp-ui');
const root = host && (host.shadowRoot || host);
if (!root) return null;
const b = [...root.querySelectorAll('button')].find(x =>
    /^(Deny|Deny all|Reject|Reject all|Decline|Only essential|Ablehnen|Alle ablehnen)$/i.test((x.innerText || '').trim()));
if (b) { b.click(); return b.innerText.trim(); }
return null;
"""


def driver_uc(headless):
    import undetected_chromedriver as uc
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,900")
    hide_window(options)
    return start_uc(options, "omio")


def js_click(driver, element):
    driver.execute_script("arguments[0].click()", element)


def choose_station(driver, e2e, station):
    """Tippen und den ersten Vorschlag ('Munich, Germany') per Enter übernehmen (Mausklicks fängt die Liste ab)."""
    inp = driver.find_element(By.CSS_SELECTOR, f"[data-e2e='{e2e}']")
    driver.execute_script("arguments[0].click(); arguments[0].focus();", inp)
    type_slowly(inp, station)
    for _ in range(8):
        time.sleep(1)
        if [o for o in driver.find_elements(By.XPATH, f"//*[starts-with(normalize-space(text()), '{station.split()[0]}')]")
                if o.is_displayed()]:
            break
    inp.send_keys(Keys.ENTER)
    time.sleep(1)
    print(e2e, "->", inp.get_attribute("value"))


def fetch(driver, datum, uhrzeit):
    d = date.fromisoformat(datum)
    driver.get("https://www.omio.com/?locale=en")
    time.sleep(8)
    if "captcha" in driver.page_source.lower():
        raise RuntimeError("Omio verlangt ein Captcha - Abfrage abgebrochen")
    # Sprachvorschlag-Fenster schließen
    lang = [e for e in driver.find_elements(By.XPATH, "//*[normalize-space(text())='English (US)']") if e.is_displayed()]
    if lang:
        js_click(driver, lang[0])
    time.sleep(1)
    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    print("Cookies:", driver.execute_script(DENY) or "kein Ablehnen-Knopf, Banner bleibt unbeantwortet")

    choose_station(driver, "departurePositionInput", START)
    choose_station(driver, "arrivalPositionInput", ZIEL)

    # Kalender: jeder Tag ist ein <li date="Mon Nov 09 2026 ...">; monatsweise vorblättern
    js_click(driver, driver.find_element(By.CSS_SELECTOR, "[data-e2e='buttonDepartureDate']"))
    time.sleep(2)
    key = f"{DAYS[d.weekday()]} {MONTHS[d.month - 1]} {d.day:02d} {d.year}"
    for _ in range(12):
        day = [e for e in driver.find_elements(By.CSS_SELECTOR, f"li[data-e2e='calendarDay'][date^='{key}']")
               if e.is_displayed()]
        if day:
            break
        js_click(driver, driver.find_element(By.CSS_SELECTOR, "[data-e2e='calendarNavigateForward']"))
        time.sleep(1)
    else:
        raise RuntimeError(f"Tag {datum} nicht im Kalender gefunden")
    if day[0].get_attribute("data-disabled-cy") != "false":
        raise RuntimeError(f"Omio verkauft für {datum} nicht")
    js_click(driver, day[0])
    time.sleep(1)
    shown_text = driver.find_element(By.CSS_SELECTOR, "[data-e2e='buttonDepartureDateText']").text  # "Mon, Nov 09"
    print("Datum ->", shown_text)

    # Häkchen "Find my accommodation" aus, sonst öffnet die Suche zusätzlich Booking.com
    for box in driver.find_elements(By.CSS_SELECTOR, "input[type=checkbox]"):
        if "accommodation" in (box.get_attribute("aria-label") or "").lower() and box.is_selected():
            js_click(driver, box)
    click_text(driver, "^Search$", "button")
    for _ in range(40):
        time.sleep(1)
        if "/results/" in driver.current_url and "One-way" in deep_text(driver):
            break
    time.sleep(3)
    # Omio öffnet je nach Strecke den Reiter Busse oder Flüge; verglichen werden nur Züge
    if m := re.search(r"/results/(\w+)/(bus|flight)\b", driver.current_url):
        driver.get(driver.current_url.replace(f"/{m.group(2)}", "/train", 1))
        for _ in range(30):
            time.sleep(1)
            if "One-way" in deep_text(driver) or "No trains found" in deep_text(driver):
                break
        time.sleep(2)
    if "/train" not in driver.current_url:
        # Omio springt zurück zu Bussen oder Flügen, wenn es auf der Strecke keine Züge verkauft
        print("Omio verkauft hier keine Züge (zeigt " + driver.current_url.split("?")[0].rsplit("/", 1)[-1] + ")")
        return "", ""
    for _ in range(WEITERE):
        if not click_text(driver, "^View trains after", "button,a,div,span"):
            break
        time.sleep(5)

    m = re.match(r"\w{3}, (\w{3}) (\d{1,2})", shown_text)
    shown = f"{d.year}-{MONTHS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}" if m else ""
    return deep_text(driver), shown


def to24(clock, half):
    h, m = map(int, clock.split(":"))
    if half == "PM" and h != 12:
        h += 12
    if half == "AM" and h == 12:
        h = 0
    return f"{h:02d}:{m:02d}"


def parse(text):
    """Ein Zug: Betreiber / Zugnummern / '8:03' / 'AM' / '4' / 'h' / '44' / 'm' / '12:47' / 'PM' /
    Bahnhof / Bahnhof / 'Direct' oder '1 transfer' / '€49' / '1' / '•' / 'One-way'"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    rows = []
    for i in range(1, len(lines) - 12):
        if not (re.fullmatch(r"\d{1,2}:\d{2}", lines[i]) and lines[i + 1] in ("AM", "PM")
                and lines[i + 3] == "h" and lines[i + 5] == "m"):
            continue
        if not (re.fullmatch(r"\d{1,2}:\d{2}", lines[i + 6]) and lines[i + 7] in ("AM", "PM")):
            continue
        changes = lines[i + 10]
        n = 0 if changes == "Direct" else int(m.group(1)) if (m := re.match(r"(\d+) transfer", changes)) else ""
        price = re.fullmatch(r"€([\d,]+(?:\.\d{2})?)", lines[i + 11]) if i + 11 < len(lines) else None
        trains, operator = lines[i - 1], lines[i - 2]
        if trains == "Bus" or operator == "+":
            continue  # Fahrt mit Busabschnitt
        rows.append({
            "abfahrt": to24(lines[i], lines[i + 1]), "ankunft": to24(lines[i + 6], lines[i + 7]),
            "dauer_min": int(lines[i + 2]) * 60 + int(lines[i + 4]), "umstiege": n, "tarif": "",
            "preis": f"{float(price.group(1).replace(',', '')):.2f}".replace(".", ",") if price else "",
            "bemerkung": "" if price else "kein Preis angezeigt",
            "zuege": train_names(trains, operator),
        })
    return rows


def train_names(trains, operator):
    """'RJ 113 • RJX19975' -> 'RJ 113 + RJX 19975'. Bei RegioJet steht 'RJ 1029/1014 (Warsaw -> Prague)';
    daraus wird 'RegioJet 1029', damit es nicht mit Railjet-Zügen (auch 'RJ') verwechselt wird."""
    names = []
    for part in trains.split("•"):
        part = re.sub(r"\(.*?\)", "", part).strip()
        if not part:
            continue
        part = re.sub(r"(?i)^FRECCIAROSSA( 1000)?\s+", "FR ", part)  # "FRECCIAROSSA 1000 6651": 1000 ist der Zugtyp
        part = re.sub(r"^([A-Za-z]+)\s*(\d+)(/\d+)?$", r"\1 \2", part)
        if "RegioJet" in operator:
            part = re.sub(r"^RJ ", "RegioJet ", part)
        names.append(part)
    return " + ".join(names)


if __name__ == "__main__":
    run("omio.com", START, ZIEL, fetch, parse, driver_factory=driver_uc)
