"""Gleichpreis-Regel: Strecken, auf denen alle Verkäufer immer exakt gleich viel verlangen, nur noch wöchentlich abfragen.

    python skripte/gleichpreis_pruefen.py          Liste listen/nur_woechentlich.csv aktualisieren
    python skripte/gleichpreis_pruefen.py probe    nur anzeigen, nichts ändern

Regel: Hatte eine Strecke an mindestens 6 Reisetagen mit Vergleich (daten/vergleich.csv) bei jedem Zug bei allen
Verkäufern denselben Preis, kommt sie in listen/nur_woechentlich.csv. alle_strecken.py fragt solche Strecken nur noch
montags ab. Zeigt eine spätere Abfrage einen Unterschied, fliegt die Strecke wieder aus der Liste und wird täglich
abgefragt. Die alte Liste kommt dann nach alte_dateien/, jede Änderung steht in logs/gleichpreis.csv.
Liest daten/vergleich.csv, also vorher auswertung.py laufen lassen.
"""
import collections
import csv
import shutil
import sys
from datetime import datetime

from pfade import BASIS, LISTEN, LOGS, VERGLEICH

MIN_TAGE = 6
LISTE = LISTEN / "nur_woechentlich.csv"
PROTOKOLL = LOGS / "gleichpreis.csv"
probe = len(sys.argv) > 1 and sys.argv[1] == "probe"

# Je Strecke: an welchen Reisetagen gab es einen Vergleich, und war jemals ein Zug unterschiedlich teuer?
zuege = collections.defaultdict(lambda: collections.defaultdict(dict))
namen = {}
with open(VERGLEICH, encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f, delimiter=";"):
        if r["preis_eur"]:
            zuege[r["nr"]][(r["reise_datum"], r["abfahrt"], r["ankunft"])][r["verkaeufer"]] = \
                float(r["preis_eur"].replace(",", "."))
            namen[r["nr"]] = r["strecke"]
tage, unterschied = {}, {}
for nr, conns in zuege.items():
    vergleiche = {k: p for k, p in conns.items() if len(p) > 1}
    tage[nr] = len({k[0] for k in vergleiche})
    unterschied[nr] = any(max(p.values()) - min(p.values()) >= 0.01 for p in vergleiche.values())

bisher = {}
if LISTE.exists():
    with open(LISTE, encoding="utf-8-sig", newline="") as f:
        bisher = {r["nr"]: r for r in csv.DictReader(f, delimiter=";")}

neu = {nr: {"nr": nr, "strecke": namen[nr], "seit": datetime.now().strftime("%Y-%m-%d"),
            "grund": f"{tage[nr]} Reisetage, alle Verkäufer immer gleich teuer"}
       for nr in tage if tage[nr] >= MIN_TAGE and not unterschied[nr] and nr not in bisher}
zurueck = {nr: r for nr, r in bisher.items() if unterschied.get(nr)}

for nr, r in neu.items():
    print(f"nur noch wöchentlich: {nr} {r['strecke']} ({r['grund']})")
for nr, r in zurueck.items():
    print(f"wieder täglich: {nr} {r['strecke']} (Preise unterscheiden sich inzwischen)")
if not neu and not zurueck:
    print("Gleichpreis-Regel: keine Änderung.")
if probe or not (neu or zurueck):
    sys.exit()

if LISTE.exists():
    shutil.copy(LISTE, BASIS / "alte_dateien" / f"nur_woechentlich_{datetime.now():%Y-%m-%d_%H%M}.csv")
behalten = [r for nr, r in bisher.items() if nr not in zurueck] + list(neu.values())
with open(LISTE, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["nr", "strecke", "seit", "grund"], delimiter=";")
    w.writeheader()
    w.writerows(sorted(behalten, key=lambda r: int(r["nr"])))
neu_protokoll = not PROTOKOLL.exists()
with open(PROTOKOLL, "a", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter=";")
    if neu_protokoll:
        w.writerow(["datum", "nr", "strecke", "aenderung"])
    for nr, r in neu.items():
        w.writerow([datetime.now().strftime("%Y-%m-%d"), nr, r["strecke"], "nur noch wöchentlich"])
    for nr, r in zurueck.items():
        w.writerow([datetime.now().strftime("%Y-%m-%d"), nr, r["strecke"], "wieder täglich"])
