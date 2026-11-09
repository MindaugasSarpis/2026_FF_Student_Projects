"""SNCB / NMBS International (Belgien, b-europe.com): python skripte/sncb.py 2026-10-27 08:00
Die Uhrzeit wird auf die volle Stunde abgerundet. Die Liste zeigt keine Zugnummern."""
import re
import time
from urllib.parse import parse_qs, urlencode, urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import click_text, deep_text, route, run, type_slowly, wait_for_text

# Schreibweise wie in der Vorschlagsliste von b-europe.com, mit Länderkürzel
START, ZIEL = route("Bruxelles-Midi (Be)", "Koln Hbf (De)")
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember"]


def choose_station(driver, field, station):
    inp = driver.find_element(By.ID, field)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].focus();", inp)
    inp.click()
    type_slowly(inp, station.rsplit(" (", 1)[0][:12])
    for _ in range(10):
        time.sleep(1)
        options = [o for o in driver.find_elements(By.CSS_SELECTOR, ".autocomplete-suggestion") if o.is_displayed()]
        match = [o for o in options if o.find_element(By.CSS_SELECTOR, ".tt-station-name").text.strip() == station]
        if match:
            match[0].click()
            print(field, "->", inp.get_attribute("value"))
            return
    raise RuntimeError(f"Bahnhof nicht in der Vorschlagsliste: {station}")


def fetch(driver, datum, uhrzeit):
    year, month, day = datum.split("-")
    driver.get("https://www.b-europe.com/DE")
    time.sleep(6)
    click_text(driver, "^(Alle ablehnen|Ablehnen|Nur notwendige|Nur erforderliche)", "button,a")
    choose_station(driver, "departure-station", START)
    choose_station(driver, "return-station", ZIEL)

    # Irgendein Datum wählen, damit die Suche startet; das richtige Datum kommt danach in die Adresse
    driver.find_element(By.ID, "departure-date").click()
    time.sleep(1)
    [b for b in driver.find_elements(By.CSS_SELECTOR, "button.pika-button") if b.is_displayed()][-1].click()
    driver.find_element(By.ID, "QsmSearch").click()
    WebDriverWait(driver, 30).until(lambda d: "origin=" in d.current_url)

    # Die Ergebnisseite lässt sich direkt über die Adresse aufrufen: einfache Fahrt, Datum, Stunde
    parts = urlparse(driver.current_url)
    query = {k: v[0] for k, v in parse_qs(parts.query).items()}
    query.update(traveltype="OneWay", outbound=f"{day}/{month}/{year}", outboundt=str(int(uhrzeit[:2])),
                 outboundtp="DepartureTime", inbound="", autoactivatestep2="true")
    driver.get(f"{parts.scheme}://{parts.netloc}{parts.path}?{urlencode(query)}")
    wait_for_text(driver, "Reisedatum:", 40)
    time.sleep(4)

    text = deep_text(driver)
    shown = re.search(r"Reisedatum:\n\S+ (\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})", text)
    return text, f"{shown.group(3)}-{MONTHS.index(shown.group(2)) + 1:02d}-{int(shown.group(1)):02d}" if shown else ""


def parse(text):
    """Eine Verbindung: 'Reisedatum:' / Tag / Abfahrt / Ankunft / 'direkt' oder '1 Umstieg' / '1:51' / ... /
    '2. Klasse' / '2. Klasse' / 'ab' / '33.99 €' / ... / '33.99 €' / 'Non Flex' ..."""
    rows = []
    for block in text.split("\nReisedatum:\n")[1:]:
        times = re.findall(r"^(\d{1,2}:\d{2})$", block, re.M)
        if len(times) < 2:
            continue
        dur = re.search(r"^(\d{1,2}):(\d{2})$", block.split(times[1], 1)[1], re.M)
        changes = re.search(r"^(\d+) Umstieg", block, re.M)
        price = re.search(r"2\. Klasse\n2\. Klasse\nab\n([\d.]+) €", block)
        tarif = re.search(r"\n" + re.escape(price.group(1)) + r" €\n(\w[\w ]*Flex)\n", block) if price else None
        rows.append({
            "abfahrt": times[0].zfill(5), "ankunft": times[1].zfill(5),
            "dauer_min": int(dur.group(1)) * 60 + int(dur.group(2)) if dur else "",
            "umstiege": int(changes.group(1)) if changes else (0 if re.search(r"^direkt$", block, re.M) else ""),
            "tarif": tarif.group(1) if tarif else "",
            "preis": f"{float(price.group(1)):.2f}".replace(".", ",") if price else "",
            "bemerkung": "" if price else "kein Preis angezeigt", "zuege": "",
        })
    return rows


if __name__ == "__main__":
    run("b-europe.com", START, ZIEL, fetch, parse)
