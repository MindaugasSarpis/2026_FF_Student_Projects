"""Einmalige Testreihe: Woran liegt das „Forbidden“ bei oebb.at? Prüft Cookies (ablehnen/akzeptieren) und
Datum (nach/vor der Suche) in je 2 Durchläufen mit langen Pausen. Fenster außerhalb des Bildschirms.
Die Sicherheitsprüfung wird nur abgewartet. Schreibt nur logs/oebb_varianten.csv, nichts in preise.csv.
Aufruf: python skripte/oebb_varianten_test.py"""
import csv
import time
from datetime import date, datetime, timedelta

import undetected_chromedriver as uc
from pfade import LOGS
from preise_csv import guess_date, hide_window
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import click_text, start_uc

URL = "https://shop.oebbtickets.at/de/ticket"
START, ZIEL = "München Hbf", "Wien Hbf"
UID = '[data-unique-id="{}"]'
PAUSE = 15 * 60  # Sekunden zwischen zwei Durchläufen
ERSTER_REISETAG = date(2026, 12, 1)  # jeder Durchlauf nimmt einen anderen Tag und eine andere Uhrzeit
# (Cookies akzeptieren, Datum vor der Suche)
VARIANTEN = [(False, False), (False, True), (True, False), (True, True)]
ERGEBNIS = LOGS / "oebb_varianten.csv"


def body(driver):
    return driver.find_element(By.TAG_NAME, "body").text


def forbidden(driver):
    return "Forbidden" in body(driver).splitlines()


def station(driver, uid, text):
    inp = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, UID.format(uid))))
    inp.click()
    time.sleep(0.5)
    for ch in text:
        inp.send_keys(ch)
        time.sleep(0.08)
    time.sleep(1)
    option = (By.XPATH, f'//mat-option[contains(., "{text}")]')
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(option)).click()


def datum_setzen(driver, datum, uhrzeit):
    jahr, monat, tag = datum.split("-")
    stunde, minute = uhrzeit.split(":")
    for uid, wert in (("dateComponentInputYear", jahr), ("dateComponentInputMonth", monat),
                      ("dateComponentInputDay", tag), ("timeComponentInputHour", stunde),
                      ("timeComponentInputMinute", minute)):
        inp = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, UID.format(uid))))
        inp.click()
        inp.send_keys(Keys.CONTROL, "a")
        inp.send_keys(wert)
        time.sleep(0.5)


def warte_auf_suche(driver):
    try:
        WebDriverWait(driver, 30).until(lambda d: "€" in body(d) or forbidden(d))
    except Exception:
        pass


def durchlauf(akzeptieren, datum_zuerst, datum, uhrzeit):
    """Gibt (Ergebnis, Stelle) zurück."""
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,800")
    hide_window(options)
    options.add_argument("--lang=de-DE")
    driver = start_uc(options, "oebb")
    stelle = "Start"
    try:
        driver.get(URL)
        time.sleep(3)
        if "Moment" in driver.title:
            stelle = "Sicherheitsprüfung"
            try:
                WebDriverWait(driver, 60).until(lambda d: "Moment" not in d.title)
            except Exception:
                return "Prüfung gibt nicht frei", stelle
            time.sleep(3)

        stelle = "Cookies"
        if akzeptieren:
            for _ in range(10):
                if click_text(driver, "Alle Cookies akzeptieren"):
                    break
                time.sleep(1)
        else:
            btn = (By.CSS_SELECTOR, UID.format("cookieBannerAcceptNonTechnicalCookiesButton"))
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(btn)).click()
        time.sleep(3)
        if forbidden(driver):
            return "Forbidden", stelle

        stelle = "Eingabe"
        station(driver, "travelStationFromInput", START)
        station(driver, "travelStationToInput", ZIEL)
        time.sleep(1)
        if datum_zuerst:
            datum_setzen(driver, datum, uhrzeit)
        stelle = "Suche"
        driver.find_element(By.CSS_SELECTOR, UID.format("travelFindServicesSplitButton")).click()
        warte_auf_suche(driver)
        if forbidden(driver):
            return "Forbidden", stelle

        if not datum_zuerst:
            stelle = "Datum danach"
            datum_setzen(driver, datum, uhrzeit)
            driver.switch_to.active_element.send_keys(Keys.ENTER)
            time.sleep(10)
            if forbidden(driver):
                return "Forbidden", stelle

        stelle = "Ergebnis"
        knopf = driver.find_element(By.CSS_SELECTOR, UID.format("travelDateComponentNextDay"))
        gezeigt = guess_date(knopf.get_attribute("aria-label") or "")
        preise = body(driver).count("€")
        if gezeigt == datum and preise:
            return f"Preise ({preise} Euro-Zeichen)", stelle
        return f"keine Preise für den Tag (Seite zeigt {gezeigt}, {preise} Euro-Zeichen)", stelle
    except Exception as e:
        return f"Fehler {type(e).__name__}", stelle
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def main():
    laeufe = VARIANTEN + VARIANTEN[::-1]  # andere Reihenfolge in Runde 2, damit die Tageszeit nicht mitspielt
    for i, (akzeptieren, datum_zuerst) in enumerate(laeufe):
        if i:
            time.sleep(PAUSE)
        datum = (ERSTER_REISETAG + timedelta(days=i)).isoformat()
        uhrzeit = f"{7 + i:02d}:{10 + i * 5:02d}"
        ergebnis, stelle = durchlauf(akzeptieren, datum_zuerst, datum, uhrzeit)
        zeile = [datetime.now().strftime("%Y-%m-%d %H:%M"), "akzeptiert" if akzeptieren else "abgelehnt",
                 "vor der Suche" if datum_zuerst else "nach der Suche", datum, uhrzeit, ergebnis, stelle]
        print(*zeile, sep=" | ", flush=True)
        neu = not ERGEBNIS.exists()
        with open(ERGEBNIS, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            if neu:
                w.writerow(["zeit", "cookies", "datum_gesetzt", "reise_datum", "uhrzeit", "ergebnis", "stelle"])
            w.writerow(zeile)


if __name__ == "__main__":
    main()
