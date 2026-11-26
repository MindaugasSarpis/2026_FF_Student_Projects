"""PKP Intercity (Polen): python skripte/pkp.py 2026-10-27 08:00"""
import re
import time
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import deep_text, route, run, type_slowly, wait_for_text

# So eintippen, dass der gewünschte Bahnhof der erste Vorschlag ist (z. B. "Berlin Hbf" -> "Berlin Gł./Berlin Hbf")
START, ZIEL = route("Warszawa Centralna", "Berlin Hbf")
SET_VALUE = ("arguments[0].value = arguments[1];"
             "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
             "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));")


def visible_options(driver):
    return [o for o in driver.find_elements(By.CSS_SELECTOR, "ul.typeahead.dropdown-menu li a") if o.is_displayed()]


def fetch(driver, datum, uhrzeit):
    driver.get("https://www.intercity.pl/en/")
    WebDriverWait(driver, 30).until(lambda d: d.find_elements(By.ID, "stname-0"))  # lädt unter Last langsamer
    time.sleep(5)
    try:
        driver.find_element(By.ID, "CybotCookiebotDialogBodyButtonDecline").click()
        print("cookies: nur notwendige")
    except Exception:
        print("cookies: kein Banner erschienen")
    time.sleep(1)

    for i, station in enumerate((START, ZIEL)):
        inp = driver.find_element(By.ID, f"stname-{i}")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", inp)
        inp.click()
        inp.send_keys(Keys.CONTROL, "a")  # das Feld ist mit der letzten Suche vorbelegt
        inp.send_keys(Keys.BACKSPACE)
        type_slowly(inp, station)
        # Die Vorschlagsliste wird beim Tippen mehrfach neu aufgebaut; klicken, bis die Bahnhofs-ID gesetzt ist
        station_id = driver.find_element(By.NAME, f"stid[{i}]")
        for _ in range(10):
            time.sleep(1)
            try:
                visible_options(driver)[0].click()
            except (IndexError, StaleElementReferenceException):
                continue
            if station_id.get_attribute("value"):
                break
        else:
            raise RuntimeError(f"Bahnhof nicht gefunden: {station}")
        time.sleep(1)
        print(f"stname-{i} ->", inp.get_attribute("value"))

    driver.execute_script(SET_VALUE, driver.find_element(By.ID, "date_picker"), datum)
    driver.execute_script(SET_VALUE, driver.find_element(By.ID, "ic-seek-time"), uhrzeit)
    driver.find_element(By.CSS_SELECTOR, "button[name=search]").click()
    time.sleep(3)
    driver.switch_to.window(driver.window_handles[-1])
    # Die Ergebnisse liegen auf ebilet.intercity.pl; das Datum steht dort als dwyj=... in der Adresse
    WebDriverWait(driver, 30).until(lambda d: "dwyj=" in d.current_url)
    wait_for_text(driver, "Travel time:")
    # Die Preise werden einzeln nachgeladen: warten, bis keine neuen mehr dazukommen
    text, count = deep_text(driver), -1
    for _ in range(10):
        if text.count("PLN") == count and count > 0:
            break
        count = text.count("PLN")
        time.sleep(2)
        text = deep_text(driver)
    in_url = re.search(r"dwyj=(\d{4}-\d{2}-\d{2})", driver.current_url).group(1)
    on_page = re.search(r"Showing connections for \S+ (\d{1,2}) ", text)
    return text, in_url if on_page and int(on_page.group(1)) == int(in_url[-2:]) else ""


def parse(text):
    """Eine Verbindung: 'Connection to  09:00 ...' / 'Direct' / ... / 'Travel time:' / '5h 25min' / '09:00' /
    '14:25' / 'Route' / Bahnhöfe / '48 Berlin-Warszawa Express' / 'Class' / '1' / Preis / 'PLN' / 'Class' / '2' / Preis / 'PLN'."""
    rows = []
    for block in re.split(r"\nConnection to\s+(?=\d{1,2}:\d{2} )", text)[1:]:
        block = block.split("Buy a ticket")[0]
        times = re.search(r"Travel time:\n(?:(\d+)h\s*)?(?:(\d+)min)?\n(\d{1,2}:\d{2})\n(\d{1,2}:\d{2})", block)
        if not times:
            continue
        changes = re.search(r"(\d+) (?:change|transfer)", block)
        price = re.search(r"Class\n2\n([\d\s]+,\d{2})\nPLN", block)
        trains = list(dict.fromkeys(re.findall(r"^(\d{2,6} \S.*)$", block.split("Class")[0], re.M)))
        rows.append({
            "abfahrt": times.group(3).zfill(5), "ankunft": times.group(4).zfill(5),
            "dauer_min": int(times.group(1) or 0) * 60 + int(times.group(2) or 0),
            "umstiege": int(changes.group(1)) if changes else (0 if re.search(r"^Direct$", block, re.M) else ""),
            "tarif": "", "preis": re.sub(r"\s", "", price.group(1)) if price else "",
            "bemerkung": "" if price else "kein Preis angezeigt",
            "zuege": " + ".join(trains),
        })
    return rows


if __name__ == "__main__":
    run("intercity.pl", START, ZIEL, fetch, parse, waehrung="PLN")
