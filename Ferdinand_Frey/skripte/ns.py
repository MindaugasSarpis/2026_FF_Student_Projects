"""NS International (Niederlande): python skripte/ns.py 2026-11-20 08:00
Die Eingabefelder stecken in mehreren Shadow-DOM-Ebenen (nes-fromto > nes-autosuggest > nes-search-input).
Normales send_keys ersetzt dort bei jedem Buchstaben den ganzen Text (am Ende steht nur der letzte Buchstabe);
deshalb wird langsam über Chrome selbst getippt (CDP Input.insertText). Keine Zugnummern, nur Zugarten (ICE, IC)."""
import re
import time
import undetected_chromedriver as uc
from preise_csv import hide_window
from selenium_basis import (click_text, deep_click_text, deep_find, deep_text, insert_slowly, route, run, start_uc,
                            wait_for_text)

# Schreibweise wie in der Vorschlagsliste von nsinternational.com
START, ZIEL = route("Amsterdam Central", "Frankfurt (Main) Hbf")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]

def driver_uc(headless):
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,900")
    hide_window(options)
    options.add_argument("--lang=en-GB")
    return start_uc(options, "ns")


def choose_station(driver, field, station):
    deep_find(driver, f"input#{field}")[0].click()
    time.sleep(0.8)
    insert_slowly(driver, station.split(" (")[0][:12])  # z. B. "Frankfurt" statt "Frankfurt (Main) Hbf"
    for _ in range(10):
        time.sleep(1)
        if deep_click_text(driver, "^" + re.escape(station) + "$"):
            time.sleep(1)
            print(field, "->", deep_find(driver, f"input#{field}")[0].get_attribute("value"))
            return
    raise RuntimeError(f"Bahnhof nicht in der Vorschlagsliste: {station}")


def fetch(driver, datum, uhrzeit):
    driver.get("https://www.nsinternational.com/en")
    time.sleep(6)
    print("cookies:", click_text(driver, "^Decline$", "button") or "kein Banner")
    time.sleep(2)
    choose_station(driver, "fromfrom", START)
    choose_station(driver, "toto", ZIEL)

    deep_click_text(driver, "^Select travel date$")
    time.sleep(2)
    deep_click_text(driver, "^One way$")
    time.sleep(1)
    days = deep_find(driver, ".t-day-selection--" + datum.replace("-", ""))
    if not days:
        raise RuntimeError(f"Tag {datum} nicht im Kalender gefunden")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", days[0])
    time.sleep(1)
    days[0].click()
    time.sleep(2)
    deep_click_text(driver, "^Continue$")
    time.sleep(2)
    deep_find(driver, "button.t-search-button")[0].click()
    wait_for_text(driver, "€", 40)
    time.sleep(5)
    # Die Liste beginnt etwa um 7 Uhr und zeigt nur wenige Züge; "later" lädt weitere nach
    for _ in range(4):
        if len(parse(deep_text(driver) + f"\n#AB {uhrzeit}")) >= 5:
            break
        later = deep_find(driver, ".t-later")
        if not later:
            break
        driver.execute_script("arguments[0].click()", later[0])
        time.sleep(5)

    text = deep_text(driver)
    shown = re.search(r"\b(\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})", text)
    shown = f"{shown.group(3)}-{MONTHS.index(shown.group(2)) + 1:02d}-{int(shown.group(1)):02d}" if shown else ""
    # Nur Verbindungen ab der gewünschten Uhrzeit, wie bei den anderen Verkäufern
    return text + f"\n#AB {uhrzeit}", shown


def parse(text):
    """Eine Verbindung: 'Departure time, 6:54,' / '06:54' / 'Arrival time, ...' / '11:51' / ... / '4h 57m' /
    'with total number of 3' / 'transfers' / '.' / '3' / '€ 55.99' / 'You travel with' / Zugarten."""
    ab = re.search(r"#AB (\d{2}:\d{2})", text)
    ab = ab.group(1) if ab else "00:00"
    lines = [l.strip() for l in text.splitlines()]
    rows, seen = [], set()
    for i, line in enumerate(lines):
        if not line.startswith("Departure time,") or i + 3 >= len(lines):
            continue
        dep, arr = lines[i + 1], lines[i + 3]
        if not (re.fullmatch(r"\d{2}:\d{2}", dep) and re.fullmatch(r"\d{2}:\d{2}", arr)) or dep < ab:
            continue
        block = lines[i + 4:i + 40]
        # Block endet beim nächsten Zug oder am Ende der Liste ("later", darunter der Warenkorb mit "€ 0.00")
        end = next((k for k, l in enumerate(block) if l.startswith("Departure time,") or l in ("later", "Booking details")),
                   len(block))
        block = block[:end]
        dur = next((re.fullmatch(r"(\d+)h (\d+)m", l) for l in block if re.fullmatch(r"(\d+)h (\d+)m", l)), None)
        changes = next((re.search(r"total number of (\d+)", l) for l in block if "total number of" in l), None)
        price = next((re.fullmatch(r"€ (\d+(?:[.,]\d{2})?)", l) for l in block if re.fullmatch(r"€ \d+(?:[.,]\d{2})?", l)), None)
        if price and float(price.group(1).replace(",", ".")) == 0:  # 0,00 ist nie ein Ticketpreis
            price = None
        k = block.index("You travel with") if "You travel with" in block else None
        kinds = [l for l in block[k + 1:] if re.fullmatch(r"[A-Z]{2,4}|Regional|Eurostar", l)] if k is not None else []
        if (dep, arr) in seen:  # derselbe Zug steht manchmal doppelt (z. B. unter "Featured")
            continue
        seen.add((dep, arr))
        rows.append({
            "abfahrt": dep, "ankunft": arr,
            "dauer_min": int(dur.group(1)) * 60 + int(dur.group(2)) if dur else "",
            "umstiege": int(changes.group(1)) if changes else "", "tarif": "",
            "preis": f"{float(price.group(1).replace(',', '.')):.2f}".replace(".", ",") if price else "",
            "bemerkung": "" if price else "kein Preis angezeigt",
            "zuege": " + ".join(dict.fromkeys(kinds)),  # nur Zugarten, NS zeigt keine Nummern
        })
    return rows


if __name__ == "__main__":
    run("nsinternational.com", START, ZIEL, fetch, parse, driver_factory=driver_uc)
