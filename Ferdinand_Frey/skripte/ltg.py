"""LTG Link (Litauen): python skripte/ltg.py 2026-10-27
Die Seite listet alle Züge des Tages, eine Uhrzeit lässt sich nicht vorgeben."""
import re
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import click_text, deep_text, route, run, type_slowly, wait_for_text

START, ZIEL = route("Vilnius", "Kaunas")
TIME = re.compile(r"^\d{1,2}:\d{2}$")
PRICE = re.compile(r"^(\d+,\d{2})\s*€$")


def fetch(driver, datum, uhrzeit):
    driver.get("https://ltglink.lt/en")
    time.sleep(5)
    print("cookies:", click_text(driver, "Decline all") or "kein Banner erschienen")

    for key, station in (("origin", START), ("destination", ZIEL)):
        field = (By.CSS_SELECTOR, f"input[aria-labelledby='stop-search-select-label-ticket-{key}']")
        inp = WebDriverWait(driver, 20).until(EC.element_to_be_clickable(field))
        inp.click()
        type_slowly(inp, station.split("/")[0])  # z. B. "Talinas/Tallinn"
        option = (By.XPATH, f"//*[@id='stop-search-select-list-ticket-{key}']//li[normalize-space()='{station}']")
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(option)).click()
        print(key, "->", inp.get_attribute("value"))

    click_text(driver, "^Search$", "button")
    WebDriverWait(driver, 30).until(lambda d: "oStop=" in d.current_url)
    # Das Reisedatum steht als oDate=... in der Adresse der Ergebnisseite
    driver.get(re.sub(r"oDate=[^&]*", f"oDate={datum}", driver.current_url))
    wait_for_text(driver, "klasė")
    time.sleep(2)

    text = deep_text(driver)
    shown = re.search(r"Filtras\n\S+ (\d{2})-(\d{2})\n", text)
    return text, f"{datum[:4]}-{shown.group(1)}-{shown.group(2)}" if shown else ""


def parse(text):
    """Eine Verbindung: Abfahrt / Bahnhof / Ankunft / Bahnhof / '1 val' / '31 min' / 'Vagono numeris' /
    Zugnummer / ... / '2 klasė' / Preis oder 'Išparduota' / Strecke / 'Pasirinkite klasę'."""
    rows, lines = [], [l.strip() for l in text.splitlines()]
    for i in range(len(lines) - 3):
        if not (TIME.match(lines[i]) and TIME.match(lines[i + 2])):
            continue
        block = []
        for line in lines[i + 4:i + 24]:
            if line == "Pasirinkite klasę":
                break
            block.append(line)
        joined = "\n".join(block)
        hours, minutes = re.search(r"^(\d+) val$", joined, re.M), re.search(r"^(\d+) min$", joined, re.M)
        zug = re.search(r"Vagono numeris\n(\S+)", joined)
        second = re.search(r"2 klasė\n(.+)", joined)
        price = PRICE.match(second.group(1)) if second else None
        sold_out = "Išparduota" in joined and not price
        rows.append({
            "abfahrt": lines[i].zfill(5), "ankunft": lines[i + 2].zfill(5),
            "dauer_min": int(hours.group(1) if hours else 0) * 60 + int(minutes.group(1) if minutes else 0),
            "umstiege": 1 if "persėdimu" in joined else 0,
            "tarif": "", "preis": price.group(1) if price else "",
            "bemerkung": "" if price else ("ausverkauft" if sold_out else "kein Preis angezeigt"),
            "zuege": zug.group(1) if zug else "",
        })
    return rows


if __name__ == "__main__":
    run("ltglink.lt", START, ZIEL, fetch, parse)
