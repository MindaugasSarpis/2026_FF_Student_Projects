"""Übernimmt getestete neue Strecken aus listen/kandidaten_neu.csv nach listen/strecken.csv.

    python skripte/alle_strecken.py <Datum> 08:00 kandidaten_neu.csv    zuerst testen
    python skripte/kandidaten_uebernehmen.py probe                      nur anzeigen, nichts ändern
    python skripte/kandidaten_uebernehmen.py                            übernehmen

Übernommen wird eine Strecke, sobald mindestens 2 Verkäufer dafür einen ganzen Preis gezeigt haben (Teilpreise zählen
nicht), und zwar nur mit diesen Verkäufern. Die übrigen Zeilen bleiben in der Liste und lassen sich erneut testen.
Neue Strecken laufen zuerst alle 8 Tage, bis skripte/strecken_gewichten.py ihre Aufrufe berücksichtigt.
"""
import ast
import csv
import shutil
import sys
from datetime import datetime

from pfade import BASIS, DATEN, LISTEN, SKRIPTE, STRECKEN

KANDIDATEN_NEU = LISTEN / "kandidaten_neu.csv"
probe = len(sys.argv) > 1 and sys.argv[1] == "probe"
sys.stdout.reconfigure(errors="replace")

# Kürzel -> Verkäufer wie in auswertung.py (dieses Skript lässt sich nicht importieren, es läuft dabei ganz durch)
for knoten in ast.parse((SKRIPTE / "auswertung.py").read_text(encoding="utf-8")).body:
    if isinstance(knoten, ast.Assign) and getattr(knoten.targets[0], "id", "") == "QUELLE":
        QUELLE = ast.literal_eval(knoten.value)

with open(KANDIDATEN_NEU, encoding="utf-8-sig", newline="") as f:
    kandidaten = list(csv.DictReader(f, delimiter=";"))
with open(STRECKEN, encoding="utf-8-sig", newline="") as f:
    leser = csv.DictReader(f, delimiter=";")
    felder, vorhanden = leser.fieldnames, {(r["nr"], r["seite"]) for r in leser}
nummern = {r["nr"] for r in kandidaten}
mit_preis = set()
with open(DATEN / "preise.csv", encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f, delimiter=";"):
        if r["strecke_nr"] in nummern and r["preis"] and "Teilpreis" not in r["bemerkung"]:
            mit_preis.add((r["strecke_nr"], r["quelle"]))

neu = []
for nr in sorted(nummern, key=int):
    zeilen = [r for r in kandidaten if r["nr"] == nr]
    gut = [r for r in zeilen if (nr, QUELLE[r["seite"]]) in mit_preis]
    if len(gut) < 2:
        print(f"bleibt Kandidat: {nr} {zeilen[0]['strecke']} (Preise von {len(gut)} Verkäufer(n))")
        continue
    frisch = [r for r in gut if (nr, r["seite"]) not in vorhanden]
    print(f"{'übernehmen' if frisch else 'schon drin'}: {nr} {zeilen[0]['strecke']} "
          f"({', '.join(r['seite'] for r in gut)})")
    neu += frisch

if probe or not neu:
    sys.exit()
shutil.copy(STRECKEN, BASIS / "alte_dateien" / f"strecken_{datetime.now():%Y-%m-%d_%H%M}_vor_kandidaten.csv")
with open(STRECKEN, "a", encoding="utf-8", newline="") as f:
    csv.DictWriter(f, fieldnames=felder, delimiter=";").writerows(neu)
print(f"{len(neu)} Zeilen in {STRECKEN.name} ergänzt.")
