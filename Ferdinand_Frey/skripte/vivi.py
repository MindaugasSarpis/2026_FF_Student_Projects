"""Vivi (Lettland): python skripte/vivi.py 2026-10-27
Eine Uhrzeit lässt sich nicht vorgeben."""
import re
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import deep_text, route, run, type_slowly, wait_for_text

START, ZIEL = route("Riga", "Jelgava")
TIME = re.compile(r"^\d{1,2}:\d{2}$")
DATE_FIELD = "routes_search_departureDate"


def fetch(driver, datum, uhrzeit):
    year, month, day = datum.split("-")
    driver.get("https://www.vivi.lv/en/")
    time.sleep(4)
    try:
        driver.find_element(By.ID, "cookie-agree-necessary").click()
        print("cookies: nur notwendige")
    except Exception:
        print("cookies: kein Banner erschienen")

    for field, station in (("from", START), ("to", ZIEL)):
        inp = driver.find_element(By.ID, field)
        inp.clear()
        inp.click()
        type_slowly(inp, station[:4])
        option = (By.XPATH, f"//li[contains(@class,'ui-menu-item')][normalize-space()='{station}']")
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(option)).click()
        print(field, "->", inp.get_attribute("value"))

    # Das Datumsfeld ist schreibgeschützt (Kalender); der Wert wird direkt gesetzt
    driver.execute_script(
        "const f = document.getElementById(arguments[0]); f.value = arguments[1];"
        "f.dispatchEvent(new Event('change', {bubbles: true}));",
        DATE_FIELD, f"{day}.{month}.{year}",
    )
    driver.find_element(By.ID, "btn-route-search").click()
    WebDriverWait(driver, 30).until(lambda d: "/routes/list" in d.current_url)
    wait_for_text(driver, "By schedule")
    time.sleep(3)

    # Auf der Ergebnisseite steht das gewählte Datum als TT/MM im Datumsfeld
    shown = (driver.find_element(By.ID, DATE_FIELD).get_attribute("value") or "").replace(".", "/").split("/")
    shown = f"{year}-{shown[1]}-{shown[0]}" if len(shown) >= 2 else ""
    return deep_text(driver), shown


def parse(text):
    """Eine Verbindung: Abfahrt / Ankunft / Gleis / Strecke / Zugnummer / '47min' / ['2.80€'] / ...
    Danach folgt die Haltestellenliste; dort stehen nie zwei Uhrzeiten direkt hintereinander."""
    rows, lines = [], [l.strip() for l in text.splitlines()]
    for i in range(len(lines) - 6):
        if not (TIME.match(lines[i]) and TIME.match(lines[i + 1])):
            continue
        block = lines[i + 2:i + 9]
        dur = next((m for m in (re.match(r"(?:(\d+)h)?\s*(?:(\d+)min)?$", l) for l in block) if m and m.group(0)), None)
        price = next((m for m in (re.match(r"([\d.]+)€$", l) for l in block) if m), None)
        zug = next((l for l in block[1:] if re.match(r"^\d{2,5}$", l)), "")
        rows.append({
            "abfahrt": lines[i].zfill(5), "ankunft": lines[i + 1].zfill(5),
            "dauer_min": int(dur.group(1) or 0) * 60 + int(dur.group(2) or 0) if dur else "",
            "umstiege": "",  # in der Liste nicht pro Verbindung angegeben
            "tarif": "", "preis": f"{float(price.group(1)):.2f}".replace(".", ",") if price else "",
            "bemerkung": "" if price else "kein Preis angezeigt", "zuege": zug,
        })
    return rows


if __name__ == "__main__":
    run("vivi.lv", START, ZIEL, fetch, parse)
