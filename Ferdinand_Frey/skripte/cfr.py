"""CFR Călători (Rumänien), internationale Fahrten: python skripte/cfr.py 2026-12-08 08:00
Auf cfrcalatori.ro/en den Umschalter "International journeys" wählen; die Suche öffnet in einem neuen Tab
bileteinternationale.cfrcalatori.ro. Bahnhöfe müssen aus der Vorschlagsliste gewählt werden ("Please select both
locations from the suggestions"). Läuft mit undetected_chromedriver.
Preise je Verbindung über "Show offers" -> 2. Klasse (vorgewählt) -> "Get offers"; der billigste Tarif zählt.
Preise in Lei (RON); Umrechnung in der Auswertung zum EZB-Kurs."""
import re
import sys
import time
import undetected_chromedriver as uc
from preise_csv import hide_window
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import click_text, deep_click_text, deep_text, route, run, start_uc, wait_for_text

# Schreibweise wie in der internationalen Vorschlagsliste (ohne Land), z. B. "Bucuresti Nord", "Budapest-Keleti"
START, ZIEL = route("Bucuresti Nord", "Budapest-Keleti")


def driver_uc(headless):
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,900")
    hide_window(options)
    return start_uc(options, "cfr")


def choose_station(driver, field, station):
    inp = driver.find_element(By.ID, field)
    # Die Vorschlagsliste kommt nicht immer: dann Feld leeren und neu tippen (höchstens dreimal)
    for _ in range(3):
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].value = '';", inp)
        time.sleep(0.5)
        inp.click()
        for ch in station[:6]:
            inp.send_keys(ch)
            time.sleep(0.25)
        # Vorschlag z. B. "Budapest-Keleti Hungary 🇭🇺": Text vor dem Land muss genau der Bahnhof sein
        for _ in range(6):
            time.sleep(1)
            items = [li for li in driver.find_elements(By.CSS_SELECTOR, "li.ui-menu-item") if li.is_displayed()]
            hit = [li for li in items if re.match(re.escape(station) + r"\s+[A-Z][a-z]", li.text.strip())]
            if hit:
                hit[0].click()
                time.sleep(1.5)
                if inp.get_attribute("value") == station:
                    print(field, "->", station)
                    return
    raise RuntimeError(f"Bahnhof nicht übernommen: {station} (Feld zeigt {inp.get_attribute('value')!r})")


def fetch(driver, datum, uhrzeit):
    year, month, day = datum.split("-")
    driver.get("https://www.cfrcalatori.ro/en/")
    time.sleep(6)
    print("cookies:", click_text(driver, "^(Reject all|Reject)$", "button,a") or "kein Banner")
    tab = driver.find_element(By.ID, "cfr-international-tab")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", tab)
    time.sleep(0.5)
    tab.click()
    time.sleep(2)
    choose_station(driver, "intl-departure-name", START)
    choose_station(driver, "intl-arrival-name", ZIEL)
    # Datumsfeld ist versteckt (Datepicker); Wert direkt setzen, Uhrzeit dahinter bleibt
    field = driver.find_element(By.ID, "intlDataPlecare")
    old = field.get_attribute("value")
    driver.execute_script("arguments[0].value = arguments[1];"
                          "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
                          "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                          field, f"{day}.{month}.{year}" + old[10:])
    print("Datum ->", field.get_attribute("value"))
    [b for b in driver.find_elements(By.CSS_SELECTOR, "button.search-journey") if b.is_displayed()][0].click()
    WebDriverWait(driver, 20).until(lambda d: len(d.window_handles) > 1)
    driver.switch_to.window(driver.window_handles[-1])
    wait_for_text(driver, "Departure From", 40)
    time.sleep(3)
    text = deep_text(driver)
    shown = re.search(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", text)  # "Outward journey ... 08.12.2026"
    shown = f"{shown.group(3)}-{shown.group(2)}-{shown.group(1)}" if shown else ""
    # Je Verbindung: "Show offers" -> Seite mit Wagenart (2. Klasse ist vorgewählt) -> "Get offers" -> Tarife mit Preis.
    # Danach zurück zur Liste. Die Uhrzeit wird erst in parse() gefiltert.
    n = len(offer_links(driver))
    print("Verbindungen mit 'Show offers':", n)
    for i in range(n):
        if i:
            driver.back()
            driver.back()
            wait_for_text(driver, "Departure From", 30)
            time.sleep(3)
        links = offer_links(driver)
        if i >= len(links):
            break
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", links[i])
        time.sleep(0.5)
        links[i].click()
        if not wait_for_text(driver, "Get offers", 30):
            continue
        time.sleep(2)
        deep_click_text(driver, "Get offers$")
        if wait_for_text(driver, "Lei", 30):
            time.sleep(2)
            text += "\n#ANGEBOT\n" + deep_text(driver)
    return text + f"\n#AB {uhrzeit}", shown


def offer_links(driver):
    return [e for e in driver.find_elements(By.XPATH, "//*[normalize-space(text())='Show offers']") if e.is_displayed()]


def parse(text):
    """Je Angebotsseite eine Verbindung. Nach "Change selected options" steht die Zusammenfassung:
    'Outward journey' / 'BUCURESTI NORD' / '08.12.26' / '18:24' / 'BUDAPEST-KELETI' / '09.12.26' / '08:50',
    darüber im Wagenteil die Zugnummern; die Tarife als 'Price 213.57 Lei'. Gezählt wird der billigste Tarif."""
    ab = re.search(r"#AB (\d{2}:\d{2})", text)
    ab = ab.group(1) if ab else "00:00"
    rows = []
    for block in text.split("\n#ANGEBOT\n")[1:]:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if "Change selected options" not in lines:
            continue
        k = lines.index("Change selected options")
        times = [l for l in lines[k:k + 12] if re.fullmatch(r"\d{2}:\d{2}", l)]
        days = [l for l in lines[k:k + 12] if re.fullmatch(r"\d{2}\.\d{2}\.\d{2}", l)]
        if len(times) < 2 or times[0] < ab:
            continue
        dep, arr = times[0], times[1]
        mins = int(arr[:2]) * 60 + int(arr[3:]) - int(dep[:2]) * 60 - int(dep[3:])
        if len(days) >= 2 and days[1] != days[0]:
            mins += 24 * 60
        prices = [float(m) for m in re.findall(r"Price ([\d.]+) Lei", block)]
        changes = next((int(m.group(1)) for l in lines if (m := re.fullmatch(r"(\d+) Changes?", l))), "")
        # Zugnummern stehen im Wagenteil zwischen Abfahrts- und Ankunftszeit (Zeilen nur aus Ziffern)
        p = lines.index("Place type options") if "Place type options" in lines else 0
        trains = [l for l in lines[p:k] if re.fullmatch(r"\d{2,5}", l)]
        rows.append({
            "abfahrt": dep, "ankunft": arr, "dauer_min": mins, "umstiege": changes, "tarif": "",
            "preis": f"{min(prices):.2f}".replace(".", ",") if prices else "",
            "bemerkung": "" if prices else "kein Preis angezeigt",
            "zuege": " + ".join(dict.fromkeys(trains)),
        })
    return rows


if __name__ == "__main__":
    run("cfrcalatori.ro", START, ZIEL, fetch, parse, waehrung="RON", driver_factory=driver_uc)
