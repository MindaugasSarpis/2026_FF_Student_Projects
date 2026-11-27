"""Zerlegt den Text einer Ergebnisseite in Verbindungen und hängt sie an die Preis-CSV an."""
import csv
import faulthandler
import os
import re
import sys
from datetime import datetime

from pfade import KANDIDATEN, SCREENSHOTS, STRECKEN, in_daten, in_listen

# BAHN_CSV und BAHN_LISTE setzt alle_strecken.py, wenn es mit einer anderen Streckenliste läuft
CSV_PATH = in_daten(os.environ.get("BAHN_CSV", "preise.csv"))
# strecke_nr und strecke stammen aus strecken.csv und sind für alle Verkäufer gleich;
# start und ziel stehen in der Schreibweise der jeweiligen Seite
HEADER = [
    "abfrage_datum", "abfrage_uhrzeit", "reise_datum", "strecke_nr", "strecke", "quelle", "start", "ziel",
    "abfahrt", "ankunft", "dauer_min", "umstiege", "zuege", "klasse", "tarif", "preis", "waehrung", "bemerkung",
]

VISIBLE = "sichtbar" in sys.argv  # Fenster zeigen und am Ende auf Enter warten

if os.environ.get("BAHN_SEITE"):
    # alle_strecken.py bricht eine Abfrage nach 300 s ab; kurz vorher in die Fehlerausgabe schreiben,
    # an welcher Stelle das Skript gerade hängt
    faulthandler.dump_traceback_later(280)

TIME = re.compile(r"^(\d{1,2}:\d{2})(?:\s*Uhr)?$")
DURATION = re.compile(r"(?:(\d+)\s*(?:h|Std\.?))?\s*(?:(\d+)\s*min)?", re.IGNORECASE)
CHANGES = re.compile(r"(\d+)\s*(?:Umstieg|Umst\.|x umsteigen)", re.IGNORECASE)
PRICE = re.compile(r"(\d{1,4}(?:[.,]\d{2})?)\s*€|€\s*(\d{1,4}(?:[.,]\d{2})?)")
DATE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
DATE_NAME = re.compile(r"(\d{1,2})\.\s*(" + "|".join(MONTHS) + r")\w*\.?\s*(\d{4})")
TRAIN = re.compile(r"^(?:ICE|IC|EC|ECE|RJX|RJ|NJ|EN|D|WB|REX|RE|RB|BRB|M|S)\s?\d+$")
TARIF = re.compile(r"^(Sparschiene|Super Sparpreis|Sparpreis|Flexpreis|Standard-Ticket)")


def parse_duration(line):
    if not re.search(r"\d\s*(h|Std|min)", line, re.IGNORECASE) or ":" in line:
        return None
    m = DURATION.search(line[re.search(r"\d", line).start():])
    hours, minutes = int(m.group(1) or 0), int(m.group(2) or 0)
    return hours * 60 + minutes or None


LONG_NAMES = [
    ("Intercity Express", "ICE"), ("Railjet Xpress", "RJX"), ("Railjet", "RJ"), ("Intercity", "IC"),
    ("Eurocity", "EC"), ("Nightjet", "NJ"), ("EuroNight", "EN"), ("WESTbahn", "WB"),
]


def trains_from_details(line):
    """ÖBB: 'Verbindungsdetails Intercity Express 211, Railjet Xpress 19957 + Railjet Xpress 19917'."""
    trains = []
    for part in line.removeprefix("Verbindungsdetails").split(","):
        name = part.split("+")[0].strip()  # bei gekuppelten Zügen nur den ersten
        for long, short in LONG_NAMES:
            if name.startswith(long):
                name = short + name[len(long):]
                break
        if name:
            trains.append(name)
    return trains


def parse(text):
    """Zerlegt den Seitentext in Verbindungen. Eine neue Verbindung beginnt mit der ersten
    Uhrzeit nach einer Dauerangabe; Abfahrt steht vor dem Strich '–', Ankunft danach."""
    rows, cur, partial, collect = [], None, "", 0

    def new():
        return {"dep": [], "arr": [], "dash": False, "zuege": []}

    def emit():
        if cur and cur["dep"] and cur["arr"]:
            if cur.get("teil") and "preis" in cur:
                # ÖBB: 'Ticket nur für Teilstrecke: A ⮕ B' - der Preis gilt nicht für die ganze Verbindung
                cur["bemerkung"] = f"nur Teilpreis ({cur.pop('preis')}; {cur['teil']})"
            bemerkung = cur.get("bemerkung", "") or ("" if "preis" in cur else "kein Preis angezeigt")
            # Ohne Umstiegsangabe und mit genau einem Zug ist es eine Direktverbindung
            direkt = 0 if len(cur["zuege"]) == 1 else ""
            rows.append({
                "abfahrt": cur["dep"][0], "ankunft": cur["arr"][0],
                "dauer_min": cur.get("dauer", ""), "umstiege": cur.get("umstiege", direkt),
                "tarif": cur.get("tarif", ""), "preis": cur.get("preis", ""),
                "bemerkung": bemerkung, "zuege": " + ".join(cur["zuege"]),
            })

    for line in (l.strip() for l in text.splitlines()):
        if not line:
            continue
        if m := re.match(r"Ticket nur für Teilstrecke:?\s*(.*)", line):
            # steht vor der Verbindung, für die es gilt; manchmal folgt die Strecke erst in den
            # nächsten Zeilen ("Krakow Glowny" / "⮕" / "Wien Hbf")
            if m.group(1):
                partial, collect = m.group(1), 0
            elif not partial:
                partial, collect = "Teilstrecke", 3
            continue
        if collect and not TIME.match(line):
            partial = line if partial == "Teilstrecke" else f"{partial} {line}"
            collect -= 1
            continue
        collect = 0
        if m := TIME.match(line):
            if cur is None or "dauer" in cur:
                emit()
                cur = new()
                cur["teil"], partial = partial, ""
            cur["arr" if cur["dash"] else "dep"].append(m.group(1).zfill(5))
            continue
        if cur is None:
            continue
        if line in ("–", "-"):
            cur["dash"] = True
        elif TRAIN.match(line):
            if line not in cur["zuege"]:
                cur["zuege"].append(line)
        elif line.startswith("Verbindungsdetails"):
            cur["zuege"] += [t for t in trains_from_details(line) if t not in cur["zuege"]]
        elif m := TARIF.match(line):
            cur["tarif"] = m.group(1)
        elif re.search(r"Preis(auskunft)?.*nicht (möglich|verfügbar)", line, re.IGNORECASE):
            cur["bemerkung"] = "kein Preis angezeigt"
        elif (m := PRICE.search(line)) and "preis" not in cur:
            cur["preis"] = f"{float((m.group(1) or m.group(2)).replace(',', '.')):.2f}".replace(".", ",")
        else:
            # bahn.de schreibt Dauer und Umstiege in eine Zeile: "4h 43min2 Umstiege"
            if "dauer" not in cur and (d := parse_duration(line)):
                cur["dauer"] = d
            if m := CHANGES.search(line):
                cur["umstiege"] = int(m.group(1))
            elif re.search(r"\bDirekt", line, re.IGNORECASE) and "umstiege" not in cur:
                cur["umstiege"] = 0
    emit()
    return rows


def guess_date(text):
    """Erstes Datum im Text als JJJJ-MM-TT, sonst leer. Versteht 13.10.2026 und 13. Okt. 2026."""
    found = []
    if m := DATE.search(text):
        found.append((m.start(), int(m.group(3)), int(m.group(2)), int(m.group(1))))
    if m := DATE_NAME.search(text):
        found.append((m.start(), int(m.group(3)), MONTHS.index(m.group(2)) + 1, int(m.group(1))))
    if not found:
        return ""
    _, year, month, day = min(found)
    return f"{year}-{month:02d}-{day:02d}"


def hide_window(options):
    """Schiebt das Browserfenster aus dem Bildschirm, außer das Skript wurde mit 'sichtbar' gestartet."""
    if not VISIBLE:
        options.add_argument("--window-position=-2400,-2400")
        # sonst pausiert Chrome das Laden in Fenstern, die niemand sieht
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-features=CalculateNativeWinOcclusion")


def read_args(default_out):
    """Argumente in beliebiger Reihenfolge: Screenshot-Datei, 'headless', 'sichtbar', JJJJ-MM-TT, HH:MM."""
    out, headless, datum, uhrzeit = str(SCREENSHOTS / default_out), False, "", "06:00"
    for arg in sys.argv[1:]:
        if arg == "headless":
            headless = True
        elif arg in ("sichtbar", "ohne-tarife", "mit-tarife"):
            pass  # Schalter, die die Skripte selbst auswerten
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", arg):
            datum = datetime.strptime(arg, "%Y-%m-%d").strftime("%Y-%m-%d")
        elif re.fullmatch(r"\d{1,2}:\d{2}", arg):
            uhrzeit = arg.zfill(5)
        else:
            out = arg
    return out, headless, datum, uhrzeit


def route_of(start, ziel):
    """Nummer und Name der Strecke aus strecken.csv; Start und Ziel in der Schreibweise der Seite."""
    lists = [in_listen(os.environ["BAHN_LISTE"])] if os.environ.get("BAHN_LISTE") else []
    for liste in lists + [STRECKEN, KANDIDATEN]:
        try:
            with open(liste, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f, delimiter=";"):
                    if (r["start"], r["ziel"]) == (start, ziel):
                        return r["nr"], r["strecke"]
        except OSError:
            pass
    return "", ""


def keep_text(text):
    """Hebt den Seitentext zusätzlich dort auf, wo alle_strecken.py ihn pro Abfrage haben will (BAHN_SEITE)."""
    if path := os.environ.get("BAHN_SEITE"):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def append_rows(rows, reise_datum, start, ziel, quelle, klasse="2", waehrung="EUR", csv_path=CSV_PATH):
    now = datetime.now()
    nr, strecke = route_of(start, ziel)
    new_file = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        if new_file:
            writer.writerow(HEADER)
        for r in rows:
            writer.writerow([
                now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), reise_datum, nr, strecke, quelle, start, ziel,
                r["abfahrt"], r["ankunft"], r["dauer_min"], r["umstiege"], r["zuege"],
                klasse, r["tarif"], r["preis"], waehrung, r["bemerkung"],
            ])
    print(f"{len(rows)} Zeile(n) in {csv_path} gespeichert.")
