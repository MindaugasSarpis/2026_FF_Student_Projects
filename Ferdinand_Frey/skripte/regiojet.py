"""RegioJet (tschechische Privatbahn, verkauft auch Busse): python skripte/regiojet.py 2026-11-27 08:00
Die Felder "From"/"To" sind React-Select; getippt wird langsam über Chrome (CDP), gewählt wird die Stadt
(z. B. "Prague, Czech Republic"). Danach steht die Suche in der Adresse (departureDate=...), das Datum wird dort gesetzt.
Zug oder Bus erkennt man nur am Symbol: nur Verbindungen mit Zug- und ohne Bussymbol werden gespeichert.
Keine Zugnummern in der Liste, daher zuege = "RegioJet". Läuft mit undetected_chromedriver."""
import json
import re
import time
import undetected_chromedriver as uc
from preise_csv import hide_window
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import click_text, deep_find, deep_text, insert_slowly, route, run, start_uc

# Schreibweise wie in der Vorschlagsliste von regiojet.com (englische Seite): Stadt, nicht einzelne Haltestelle
START, ZIEL = route("Prague, Czech Republic", "Vienna, Austria")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
# Anfang des SVG-Pfads der Symbole in den Ergebniskarten
ZUG, BUS = "M7 2h10v1.5h-3.204", "M5 17.526c0 .788.341 1.49"

# Jede Ergebniskarte (data-id="connection-card-<id>") enthält eine Überschrift mit aria-label
# "Connection 06:01 - 10:21"; Text und Symbolpfade der ganzen Karte auslesen
# Die Liste lädt beim Scrollen weitere Tage nach (Überschrift z. B. "Saturday, 28. November 2026");
# jede Karte bekommt den Tag der Überschrift davor
CARDS = """
const dayRe = /^\\w+, \\d{1,2}\\. \\w+ \\d{4}$/; let day = '';
const out = [];
for (const e of document.querySelectorAll('*')) {
    if (e.children.length === 0 && dayRe.test((e.textContent || '').trim())) { day = e.textContent.trim(); continue; }
    const id = e.getAttribute('data-id') || '';
    const head = /^connection-card-[\\d,]+$/.test(id) && e.querySelector('[aria-label^="Connection "]');
    if (head) out.push({day: day, label: head.getAttribute('aria-label'), text: e.innerText,
        paths: [...e.querySelectorAll('path')].map(p => (p.getAttribute('d') || '').slice(0, 25))});
}
return out;"""


def driver_uc(headless):
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,900")
    hide_window(options)
    options.add_argument("--lang=en-GB")
    return start_uc(options, "regiojet")


def choose_station(driver, field, station):
    """field: 'react-select-2-input' (From) oder 'react-select-3-input' (To)."""
    deep_find(driver, "#" + field)[0].click()
    time.sleep(1)
    insert_slowly(driver, station.split(",")[0])
    for _ in range(10):
        time.sleep(1)
        opts = [o for o in deep_find(driver, f"[id^='{field.replace('-input', '')}-option-']") if o.text.strip() == station]
        if opts:
            opts[0].click()
            print(field, "->", station)
            time.sleep(1.5)
            return
    raise RuntimeError(f"Ort nicht in der Vorschlagsliste: {station}")


def fetch(driver, datum, uhrzeit):
    driver.get("https://regiojet.com/")
    time.sleep(6)
    print("cookies:", click_text(driver, "^Refuse everything$", "button") or "kein Banner")
    time.sleep(2)
    choose_station(driver, "react-select-2-input", START)
    choose_station(driver, "react-select-3-input", ZIEL)
    click_text(driver, "^Search$", "button")
    WebDriverWait(driver, 30).until(lambda d: "departureDate=" in d.current_url)
    # Die Suche läuft zuerst für heute; das Datum in der Adresse ersetzen und neu laden
    driver.get(re.sub(r"departureDate=[\d-]+", f"departureDate={datum}", driver.current_url))
    WebDriverWait(driver, 40).until(lambda d: d.execute_script(CARDS))
    time.sleep(4)

    text = deep_text(driver)
    # Karten als JSON-Zeilen anhängen, damit parse() nur mit dem Text arbeitet (wie bei den anderen Seiten);
    # nur die Karten des ersten Tags (= gesuchter Tag), nachgeladene Folgetage weglassen
    cards = driver.execute_script(CARDS)
    first = cards[0]["day"] if cards else ""
    cards = [c for c in cards if c["day"] == first]
    shown = re.search(r"(\d{1,2})\. (" + "|".join(MONTHS) + r") (\d{4})", first)
    shown = f"{shown.group(3)}-{MONTHS.index(shown.group(2)) + 1:02d}-{int(shown.group(1)):02d}" if shown else ""
    print("Tag der Liste:", first, "| Karten:", len(cards))
    return text + "\n" + "\n".join("#KARTE " + json.dumps(c) for c in cards) + f"\n#AB {uhrzeit}", shown


def parse(text):
    ab = re.search(r"#AB (\d{2}:\d{2})", text)
    ab = ab.group(1) if ab else "00:00"
    rows = []
    for line in text.splitlines():
        if not line.startswith("#KARTE "):
            continue
        c = json.loads(line[7:])
        times = re.search(r"(\d{2}:\d{2}) - (\d{2}:\d{2})", c["label"])
        if not times or times.group(1) < ab:
            continue
        zug, bus = any(p.startswith(ZUG) for p in c["paths"]), any(p.startswith(BUS) for p in c["paths"])
        if not zug or bus:  # Busse und gemischte Verbindungen auslassen
            continue
        t = c["text"]
        price = re.search(r"€\s*(\d+(?:[.,]\d+)?)", t)
        dur = re.search(r"(\d{2}):(\d{2}) h", t)
        changes = 0 if "Direct" in t else int(m.group(1)) if (m := re.search(r"(\d+) transfers?", t)) else ""
        sold_out = "Sold out" in t
        rows.append({
            "abfahrt": times.group(1), "ankunft": times.group(2),
            "dauer_min": int(dur.group(1)) * 60 + int(dur.group(2)) if dur else "",
            "umstiege": changes, "tarif": "",
            "preis": f"{float(price.group(1).replace(',', '.')):.2f}".replace(".", ",") if price and not sold_out else "",
            "bemerkung": "ausverkauft" if sold_out else "" if price else "kein Preis angezeigt",
            "zuege": "RegioJet",
        })
    return rows


if __name__ == "__main__":
    run("regiojet.com", START, ZIEL, fetch, parse, driver_factory=driver_uc)
