"""Streicht unbeteiligte Verkäufer aus listen/strecken.csv, die sich nicht lohnen (6er-Regel).

    python skripte/unbeteiligte_streichen.py          streichen
    python skripte/unbeteiligte_streichen.py probe    nur anzeigen, nichts ändern

Regel: Ein Verkäufer mit Rolle "kein Bezug" (siehe auswertung.py) fliegt raus, wenn er bei mindestens 6 Abfragen
(Reisetagen mit Vergleich in daten/vergleich.csv) nie billiger war als die billigste Start/Ziel-Bahn, also bei jedem
Zug teurer oder höchstens gleich teuer. War er einmal billiger, bleibt er. Liest daten/vergleich.csv, also vorher auswertung.py laufen lassen.
Die alte Liste kommt nach alte_dateien/, jede Streichung wird in logs/gestrichen.csv vermerkt.
"""
import collections
import csv
import shutil
import sys
from datetime import datetime

from pfade import BASIS, LOGS, STRECKEN, VERGLEICH

MIN_ABFRAGEN = 6
# Verkäufer in vergleich.csv -> Kürzel der Seite in strecken.csv
SEITE = {
    "bahn.de": "db", "oebb.at": "oebb", "sbb.ch": "sbb", "ltglink.lt": "ltg", "elron.ee": "elron",
    "intercity.pl": "pkp", "trenitalia.com": "trenitalia", "mav.hu": "mav", "cd.cz": "cd",
    "b-europe.com": "sncb", "ouigo.com": "ouigo", "eurostar.com": "eurostar",
    "nsinternational.com": "ns", "regiojet.com": "regiojet", "cfrcalatori.ro": "cfr",
}
GESTRICHEN = LOGS / "gestrichen.csv"
probe = len(sys.argv) > 1 and sys.argv[1] == "probe"


def key_of(line):
    """Zeile aus strecken.csv -> (nr, seite)."""
    parts = line.split(";")
    return (parts[0], parts[2]) if len(parts) > 2 else None


def euro(text):
    return float(text.replace(",", "."))


with open(VERGLEICH, encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f, delimiter=";"))

# Gleiche Verbindung wie in auswertung.py: Reisetag, Strecke, Abfahrt, Ankunft
groups = collections.defaultdict(list)
for r in rows:
    groups[(r["reise_datum"], r["nr"], r["abfahrt"], r["ankunft"])].append(r)

# (nr, seite) -> Reisetag -> Ergebnisse ("teurer" / "gleich" / "billiger" als die billigste Start/Ziel-Bahn)
results = collections.defaultdict(lambda: collections.defaultdict(set))
for group in groups.values():
    home = [euro(r["preis_eur"]) for r in group if r["rolle"] == "Start/Ziel"]
    if not home:
        continue
    for r in group:
        if r["rolle"] == "kein Bezug" and r["verkaeufer"] in SEITE:
            diff = euro(r["preis_eur"]) - min(home)
            results[(r["nr"], SEITE[r["verkaeufer"]])][r["reise_datum"]].add(
                "teurer" if diff > 0.005 else "billiger" if diff < -0.005 else "gleich")

# Gestrichen wird, wer nie billiger war: immer teurer oder höchstens gleich teuer. Gleich teuer bringt keinen
# Vorteil gegenüber der Heimbahn und kostet nur Abfragezeit. Einmal billiger -> bleibt.
drop = {key: len(days) for key, days in results.items()
        if len(days) >= MIN_ABFRAGEN and all("billiger" not in s for s in days.values())}
grund = {key: "unbeteiligt, immer teurer" if all(s == {"teurer"} for s in results[key].values())
         else "unbeteiligt, nie billiger (teurer oder gleich teuer)" for key in drop}

with open(STRECKEN, encoding="utf-8", newline="") as f:
    lines = f.readlines()
keep = [l for l in lines if key_of(l) not in drop]
removed = [l for l in lines if key_of(l) in drop]

if not removed:
    print("Keine unbeteiligten Verkäufer zu streichen.")
    sys.exit()
for l in removed:
    nr, strecke, seite = l.split(";")[:3]
    print(f"{'Würde streichen' if probe else 'Gestrichen'}: {nr} {strecke} {seite} "
          f"({drop[key_of(l)]} Abfragen, {grund[key_of(l)].split(', ', 1)[1]})")
if probe:
    sys.exit()

now = datetime.now()
backup = BASIS / "alte_dateien" / f"strecken_{now:%Y-%m-%d_%H%M}_vor_streichen.csv"
shutil.copy2(STRECKEN, backup)
with open(STRECKEN, "w", encoding="utf-8", newline="") as f:
    f.writelines(keep)
new_log = not GESTRICHEN.exists()
with open(GESTRICHEN, "a", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter=";")
    if new_log:
        w.writerow(["datum", "nr", "strecke", "seite", "abfragen", "grund"])
    for l in removed:
        w.writerow([f"{now:%Y-%m-%d}", *l.split(";")[:3], drop[key_of(l)], grund[key_of(l)]])
print(f"Alte Liste: {backup}")
