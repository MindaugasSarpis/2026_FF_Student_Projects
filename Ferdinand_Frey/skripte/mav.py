"""MÁV (Ungarn): python skripte/mav.py 2026-10-27 08:00
Die Liste zeigt keine Zugnummern; Preise stehen in Euro und Forint, gespeichert wird der Euro-Preis."""
import re
import time
from datetime import date
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import click_text, deep_text, route, run, type_slowly, wait_for_text

# Schreibweise wie in der Vorschlagsliste von jegy.mav.hu
START, ZIEL = route("Budapest-Keleti", "Wien Hbf")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


def visible(driver, css):
    """Sichtbare Elemente; Elemente, die die Seite gerade neu aufbaut ("stale"), werden übersprungen."""
    result = []
    for e in driver.find_elements(By.CSS_SELECTOR, css):
        try:
            if e.is_displayed():
                result.append(e)
        except StaleElementReferenceException:
            pass
    return result


def wait_visible(driver, css, seconds=20):
    """Wartet, bis mindestens ein passendes Element sichtbar ist (unter Last dauert das Laden länger)."""
    WebDriverWait(driver, seconds).until(lambda d: visible(d, css))
    return visible(driver, css)


def close_notices(driver):
    """Schließt Cookie-Hinweis und Ankündigungen (z. B. zur MÁVPlusz-App); sie kommen manchmal erst spät."""
    for pattern, tags in (("^Acknowledge$", "button"), ("^Accept$", ".cdk-overlay-container button")):
        if click_text(driver, pattern, tags):
            time.sleep(1)


def click_field(driver, field):
    """Klickt ins Eingabefeld; liegt noch ein Hinweis darüber, wird er erst geschlossen."""
    for _ in range(3):
        inp = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, field)))
        try:
            inp.click()
            return inp
        except ElementClickInterceptedException:
            close_notices(driver)
            time.sleep(2)
    driver.execute_script("arguments[0].focus()", inp)
    return inp


def fetch(driver, datum, uhrzeit):
    days = (date.fromisoformat(datum) - date.today()).days
    if days < 0:
        raise ValueError("Reisedatum liegt in der Vergangenheit")
    driver.get("https://jegy.mav.hu/")
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "startStation-input")))
    time.sleep(5)
    close_notices(driver)

    for field, station in (("startStation-input", START), ("endStation-input", ZIEL)):
        inp = click_field(driver, field)
        type_slowly(inp, station)
        time.sleep(2)
        wait_visible(driver, "div.ng-option")[0].click()
        time.sleep(1)
        print(field, "->", inp.get_attribute("value"))

    # Datum und Uhrzeit stehen in der Detailsuche; das Datum wird tageweise vorgeblättert
    WebDriverWait(driver, 20).until(lambda d: click_text(d, "^Detailed search$", "button,a"))
    try:
        wait_visible(driver, "button.later-button")
    except TimeoutException:
        close_notices(driver)
        click_text(driver, "^Detailed search$", "button,a")
        wait_visible(driver, "button.later-button")
    time.sleep(2)
    for _ in range(days):
        # Die Detailsuche baut sich nach dem Öffnen teils noch einmal neu auf: Knopf jedes Mal frisch suchen.
        # Ist er veraltet, wurde nicht geklickt, also einfach noch einmal versuchen
        for _ in range(5):
            try:
                wait_visible(driver, "button.later-button")[0].click()
                break
            except StaleElementReferenceException:
                time.sleep(1)
        else:
            raise RuntimeError("Datum ließ sich nicht weiterblättern")
        time.sleep(0.3)
    clock = driver.find_element(By.ID, "travelStartTime-input")
    clock.click()
    clock.send_keys(Keys.CONTROL, "a")
    clock.send_keys(Keys.BACKSPACE)
    type_slowly(clock, uhrzeit.replace(":", ""))  # den Doppelpunkt setzt das Feld selbst
    clock.send_keys(Keys.ENTER)
    time.sleep(1)
    print("Uhrzeit ->", clock.get_attribute("value"))

    search = [b for b in driver.find_elements(By.XPATH, "//button[normalize-space()='Search']") if b.is_displayed()]
    driver.execute_script("arguments[0].click()", search[-1])
    wait_for_text(driver, "Results matching")
    time.sleep(3)

    # Die Ergebnisseite nennt das Datum als "Outbound: / 23 October 2026"
    text = deep_text(driver)
    shown = re.search(r"Outbound:\n(\d{1,2}) (\w+) (\d{4})", text)
    if not (shown and shown.group(2) in MONTHS):
        return text, ""
    return text, f"{shown.group(3)}-{MONTHS.index(shown.group(2)) + 1:02d}-{int(shown.group(1)):02d}"


def parse(text):
    """Eine Verbindung: '1st option' / ... / 'Actual departure time:' / '05:30' / 'Actual arrival time:' /
    '08:20' / 'travel time:' / '02:50' / 'transfers:' / '0' / ... / '37 €' / '13 690  HUF'."""
    text = text.split("Offers for dates that are different")[0]  # danach folgen Angebote anderer Tage
    rows = []
    for block in re.split(r"\n\d+(?:st|nd|rd|th) option\n", text)[1:]:
        dep = re.search(r"Actual departure time:\n(\d{1,2}:\d{2})", block)
        arr = re.search(r"Actual arrival time:\n(\d{1,2}:\d{2})", block)
        if not (dep and arr):
            continue
        dur = re.search(r"travel time:\n(\d{1,2}):(\d{2})", block)
        changes = re.search(r"transfers:\n(\d+)", block)
        price = re.search(r"\n([\d\s]+(?:,\d+)?)\s*€\n", block)
        rows.append({
            "abfahrt": dep.group(1).zfill(5), "ankunft": arr.group(1).zfill(5),
            "dauer_min": int(dur.group(1)) * 60 + int(dur.group(2)) if dur else "",
            "umstiege": int(changes.group(1)) if changes else "",
            "tarif": "",
            "preis": f"{float(re.sub(r'\\s', '', price.group(1)).replace(',', '.')):.2f}".replace(".", ",") if price else "",
            "bemerkung": "" if price else "kein Preis angezeigt",
            "zuege": "",
        })
    return rows


if __name__ == "__main__":
    run("mav.hu", START, ZIEL, fetch, parse)
