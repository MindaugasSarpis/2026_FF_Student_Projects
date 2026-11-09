"""Polen über koleo.pl (verkauft u. a. PKP Intercity): python skripte/koleo.py 2026-10-27 08:00"""
import re
import time
from selenium_basis import click_text, deep_text, route, run, wait_for_text

# Schreibweise wie in der Adresse von koleo.pl
START, ZIEL = route("warszawa-centralna", "vilnius")
TIME = re.compile(r"^\d{1,2}:\d{2}$")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
DAY = re.compile(r"^(\d{1,2}) (" + "|".join(MONTHS) + ")$")
WEEKDAY = re.compile(r"^(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day$")


def fetch(driver, datum, uhrzeit):
    # Start, Ziel, Datum und Uhrzeit stehen direkt in der Adresse
    year, month, day = datum.split("-")
    driver.get(f"https://koleo.pl/en/rozklad-pkp/{START}/{ZIEL}/{day}-{month}-{year}_{uhrzeit}/all/all")
    time.sleep(4)
    click_text(driver, "^(Reject|Decline|Only necessary)")
    wait_for_text(driver, "Later connections")
    time.sleep(2)

    text = deep_text(driver)
    shown = next((m for m in map(DAY.match, text.splitlines()) if m), None)
    return text, f"{year}-{MONTHS.index(shown.group(2)) + 1:02d}-{int(shown.group(1)):02d}" if shown else ""


def parse(text):
    """Eine Verbindung: Abfahrt / Ankunft / '7h 57min' / 'Direct' oder '1 change' / Zuggattungen /
    ['Buy ticket'] / 'PLN 87.58'. Die Liste läuft in den Folgetag weiter; der wird abgeschnitten."""
    rows, lines, days = [], [l.strip() for l in text.splitlines()], 0
    for i in range(len(lines) - 3):
        if DAY.match(lines[i]):
            days += 1
            if days > 1:
                break
        if not (TIME.match(lines[i]) and TIME.match(lines[i + 1])):
            continue
        dur = re.match(r"(?:(\d+)h)?\s*(?:(\d+)min)?$", lines[i + 2])
        changes = re.match(r"(\d+) changes?$", lines[i + 3])
        brands, price = [], None
        for line in lines[i + 4:i + 12]:
            if TIME.match(line) or DAY.match(line) or WEEKDAY.match(line) or line.endswith("connections"):
                break
            if m := re.match(r"PLN\s*([\d.]+)$", line):
                price = m
                break
            if line != "Buy ticket":
                brands.append(line)
        rows.append({
            "abfahrt": lines[i].zfill(5), "ankunft": lines[i + 1].zfill(5),
            "dauer_min": int(dur.group(1) or 0) * 60 + int(dur.group(2) or 0) if dur else "",
            "umstiege": int(changes.group(1)) if changes else 0,
            "tarif": "", "preis": f"{float(price.group(1)):.2f}".replace(".", ",") if price else "",
            "bemerkung": "" if price else "kein Preis angezeigt",
            "zuege": " + ".join(brands),  # koleo.pl zeigt nur die Zuggattung, keine Zugnummer
        })
    return rows


if __name__ == "__main__":
    run("koleo.pl", START, ZIEL, fetch, parse, waehrung="PLN")
