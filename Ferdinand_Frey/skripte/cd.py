"""České dráhy (Tschechien): python skripte/cd.py 2026-10-27 08:00
Preise in tschechischen Kronen (CZK)."""
import json
import re
import time
from datetime import date
from selenium.common.exceptions import (ElementClickInterceptedException, StaleElementReferenceException,
                                        WebDriverException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import route, run, type_slowly

# Schreibweise wie in der Vorschlagsliste von cd.cz
START, ZIEL = route("Praha hl.n.", "Berlin Hbf")
SET_VALUE = ("arguments[0].value = arguments[1];"
             "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
             "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));")
# Jede Verbindung der Ergebnisliste als Datensatz: Zeiten und Bahnhöfe aller Halte, Dauer, Datum, Preis, Züge
READ_CONNECTIONS = r"""
return JSON.stringify([...document.querySelectorAll('.overview-connection')].map(c => ({
    zeiten: [...c.querySelectorAll('.schedule__text--time')].map(e => e.textContent.trim()),
    dauer: (c.querySelector('.overview-connection__footer-duration') || {textContent: ''}).textContent.trim(),
    datum: (c.querySelector('.overview-connection__footer-date') || {textContent: ''}).textContent.trim(),
    preis: (c.querySelector('button.btn--green[aria-label]') || {getAttribute: () => ''}).getAttribute('aria-label'),
    zuege: [...new Set((c.textContent.match(/Go to train details ([A-Za-z]+ ?\d+)/g) || [])
        .map(s => s.replace('Go to train details ', '')))],
})));
"""


def fetch(driver, datum, uhrzeit):
    days = (date.fromisoformat(datum) - date.today()).days
    if days < 0:
        raise ValueError("Reisedatum liegt in der Vergangenheit")
    # Seit 21.10.2026 abends antwortete cd.cz der Adresse des WLANs gar nicht mehr (Handy über andere Adresse ging):
    # eine Sperre der Adresse, kein Fehler im Skript. alle_strecken.py setzt ČD dann einige Stunden aus.
    # Chrome meldet das mal als Ausnahme, mal still mit einer eigenen Fehlerseite (chrome-error://), und mal lädt
    # die Seite gar nicht, bis limit_page_load nach 60 s abbricht (leere Seite ohne Text)
    fehler = ""
    try:
        driver.get("https://www.cd.cz/en/")
    except WebDriverException as e:
        fehler = str(e)
    leer = not fehler and driver.execute_script("return document.body ? document.body.innerText.trim().length : 0") < 20
    if (leer or driver.current_url.startswith("chrome-error") or re.search(r"ERR_(CONNECTION|TIMED_OUT)", fehler)
            or re.search(r"ERR_(CONNECTION_\w+|TIMED_OUT)", driver.page_source[:20000])):
        print("BLOCKIERT: cd.cz nicht erreichbar (Verbindung abgelehnt oder Zeitüberschreitung), "
              "vermutlich SPERRE DER ADRESSE.", flush=True)
        raise RuntimeError("cd.cz nicht erreichbar")
    if fehler:
        raise WebDriverException(fehler)
    time.sleep(6)
    try:
        driver.find_element(By.ID, "consentBtnrefuse").click()
        print("cookies: nur notwendige")
    except Exception:
        print("cookies: kein Banner erschienen")
    time.sleep(2)

    for field, station in (("connection-from", START), ("connection-to", ZIEL)):
        inp = driver.find_element(By.ID, field)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].focus();", inp)
        type_slowly(inp, station)
        option = (By.XPATH, "//li[contains(@class,'ui-menu-item')][.//div[contains(@class,'suggestion-options__text--primary')]"
                            f"[normalize-space()='{station}']]")
        # Die Vorschlagsliste wird beim Tippen neu aufgebaut und teils kurz überdeckt: mehrfach versuchen
        for attempt in range(6):
            time.sleep(1)
            try:
                [o for o in driver.find_elements(*option) if o.is_displayed()][0].click()
                break
            except (IndexError, StaleElementReferenceException, ElementClickInterceptedException):
                if attempt == 5:
                    raise RuntimeError(f"Bahnhof nicht wählbar: {station}")
        time.sleep(1)
        print(field, "->", inp.get_attribute("value"))

    # Datum tageweise vorblättern, Uhrzeit direkt setzen
    next_day = driver.find_element(By.ID, "nextday")
    for _ in range(days):
        next_day.click()
        time.sleep(0.3)
    driver.execute_script(SET_VALUE, driver.find_element(By.CSS_SELECTOR, "input.timepicker"), uhrzeit)
    form = driver.find_element(By.ID, "connection-from").find_element(By.XPATH, "./ancestor::form")
    [b for b in form.find_elements(By.XPATH, ".//button[normalize-space()='Search']") if b.is_displayed()][0].click()

    WebDriverWait(driver, 40).until(lambda d: "spojeni-tam" in d.current_url)
    try:
        WebDriverWait(driver, 30).until(lambda d: d.find_elements(By.CSS_SELECTOR, ".overview-connection .schedule__text--time"))
    except Exception:
        print("Nach 30 s noch keine Verbindungen auf der Seite.")
    time.sleep(6)  # Preise werden nachgeladen

    text = driver.execute_script(READ_CONNECTIONS)
    # Gibt es am gewünschten Tag nichts, zeigt die Seite den nächsten Tag: der zählt dann nicht
    dates = {iso_date(c["datum"]) for c in json.loads(text)}
    return text, datum if datum in dates else (sorted(dates)[0] if dates else "")


def iso_date(text):
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""


def parse(text):
    """Liest die von READ_CONNECTIONS gelieferten Datensätze; behält nur den häufigsten (gesuchten) Tag."""
    connections = [c for c in json.loads(text) if len(c["zeiten"]) >= 2]
    days = [iso_date(c["datum"]) for c in connections]
    wanted = max(set(days), key=days.count) if days else ""
    rows = []
    for c, day in zip(connections, days):
        if day != wanted:
            continue
        dur = re.search(r"(\d+):(\d{2})\s*h", c["dauer"])
        price = re.search(r"([\d\s]+)\s*CZK", c["preis"] or "")
        rows.append({
            "abfahrt": c["zeiten"][0].zfill(5), "ankunft": c["zeiten"][-1].zfill(5),
            "dauer_min": int(dur.group(1)) * 60 + int(dur.group(2)) if dur else "",
            "umstiege": max(len(c["zuege"]) - 1, 0) if c["zuege"] else "",
            "tarif": "", "preis": f"{int(re.sub(r'\\s', '', price.group(1)))},00" if price else "",
            "bemerkung": "" if price else "kein Preis angezeigt",
            "zuege": " + ".join(c["zuege"]),
        })
    return rows


if __name__ == "__main__":
    run("cd.cz", START, ZIEL, fetch, parse, waehrung="CZK")
