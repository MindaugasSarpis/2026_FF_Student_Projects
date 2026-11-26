"""Trenitalia (Italien): python skripte/trenitalia.py 2026-10-27 08:00
Die Uhrzeit wird auf die volle Stunde abgerundet."""
import re
import time
from preise_csv import MONTHS
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import deep_text, route, run, type_slowly, wait_for_text

# Schreibweise wie in der Vorschlagsliste von trenitalia.com
START, ZIEL = route("Verona Porta Nuova", "Bolzano Bozen")


def fetch(driver, datum, uhrzeit):
    year, month, day = datum.split("-")
    driver.get("https://www.trenitalia.com/de.html")
    time.sleep(4)
    try:
        driver.find_element(By.ID, "onetrust-reject-all-handler").click()
        print("cookies: abgelehnt")
    except Exception:
        print("cookies: kein Banner erschienen")
    time.sleep(1)

    for field, station in (("partenza", START), ("arrivo", ZIEL)):
        inp = driver.find_element(By.ID, field)
        inp.click()
        type_slowly(inp, station[:9])
        option = (By.XPATH, f"//li[@role='option'][normalize-space()='{station}']")
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(option)).click()
        print(field, "->", inp.get_attribute("value"))

    # Datum (MM/TT/JJJJ) und Stunde stehen in zwei Formularfeldern
    driver.execute_script(
        "for (const [id, v] of [['calendarAndata', arguments[0]], ['left-time-input', arguments[1]]]) {"
        "  const f = document.getElementById(id); f.value = v;"
        "  f.dispatchEvent(new Event('input', {bubbles: true})); f.dispatchEvent(new Event('change', {bubbles: true})); }",
        f"{month}/{day}/{year}", uhrzeit[:2] + ":00",
    )
    driver.find_element(By.ID, "searchBtn").click()
    WebDriverWait(driver, 30).until(lambda d: "lefrecce.it" in d.current_url)
    wait_for_text(driver, "Soluzione n. 1")
    time.sleep(3)

    # Die Ergebnisseite nennt das gesuchte Datum als "27 Okt 08:00"
    text = deep_text(driver)
    shown = re.search(r"\n(\d{1,2}) (" + "|".join(MONTHS) + r")\w* \d{2}:\d{2}\n", text)
    return text, f"{year}-{MONTHS.index(shown.group(2)) + 1:02d}-{int(shown.group(1)):02d}" if shown else ""


def parse(text):
    """Eine Verbindung: 'Soluzione n. 2 ; partenza ore 17:01' / 'arrivo ore 18:31' / 'Treno:' /
    'Rail jet DB AG;DB AG 80,' / 'Prezzi a partire da 32,20€' ... '1Std 30Min'."""
    LEG = re.compile(r"^.+ \(\d{1,2}:\d{2}\) - .+ \(\d{1,2}:\d{2}\)$", re.M)
    rows = []
    blocks = re.split(r"\nSoluzione n\. \d+ ; partenza ore ", text)[1:]
    for block in blocks:
        dep, arr = re.match(r"(\d{1,2}:\d{2})", block), re.search(r"arrivo ore (\d{1,2}:\d{2})", block)
        if not (dep and arr):
            continue
        head = block[:block.find("Einzelheiten")] if "Einzelheiten" in block else block[:400]
        trains = re.findall(r";([^;,\n]+),", head)  # 'Gattung;Zugnummer,'
        price = re.search(r"Prezzi a partire da (\d+,\d{2})€", head)
        dur = re.search(r"\n(?:(\d+)Std )?(\d+)Min\n", block)
        # Bei Umstiegen listet die Seite jeden Abschnitt einzeln ('Villach Hbf (19:34) - Udine (21:13)').
        # Hat ein Abschnitt keinen eigenen Preis, ist der 'ab'-Preis nur ein Teilpreis und zählt nicht.
        legs = list(LEG.finditer(block))
        parts = [block[m.end():legs[i + 1].start() if i + 1 < len(legs) else len(block)] for i, m in enumerate(legs)]
        partial = bool(price) and any(not re.search(r"von\n\d+,\d{2}€", part) for part in parts)
        partial = partial or bool(price and price.group(1) == "0,00")  # 0,00 € heißt: kein Abschnitt bepreist
        rows.append({
            "abfahrt": dep.group(1).zfill(5), "ankunft": arr.group(1).zfill(5),
            "dauer_min": int(dur.group(1) or 0) * 60 + int(dur.group(2)) if dur else "",
            "umstiege": max(len(trains) - 1, 0),
            "tarif": "", "preis": price.group(1) if price and not partial else "",
            "bemerkung": "nur Teilpreis" if partial else "" if price else (
                "nicht buchbar" if "non vendibile" in head else "kein Preis angezeigt"),
            "zuege": " + ".join(t.strip() for t in trains),
        })
    return rows


if __name__ == "__main__":
    run("trenitalia.com", START, ZIEL, fetch, parse)
