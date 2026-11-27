"""Gewichtet die Strecken nach Seitenaufrufen: Viel angesehene Strecken laufen täglich, wenig angesehene seltener.

    python skripte/strecken_gewichten.py          listen/takt.csv neu schreiben
    python skripte/strecken_gewichten.py probe    nur anzeigen, nichts ändern

Die Aufrufe je Streckenseite (deutsch + englisch, letzte TAGE Tage) kommen aus der öffentlichen GoatCounter-Statistik.
Maßstab ist der Anteil an allen Aufrufen von Streckenseiten, damit die Grenzen auch bei mehr Besuchern passen.
Der Versatz verteilt die Strecken gleichmäßig auf die Tage. Er bleibt gleich, solange sich der Takt nicht ändert.
Die Gleichpreis-Regel (listen/nur_woechentlich.csv) geht vor: Solche Strecken laufen unabhängig davon nur montags.
Ist GoatCounter nicht erreichbar, bleibt die alte Liste. Die alte Liste kommt nach alte_dateien/.
"""
import collections
import csv
import json
import re
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from pfade import BASIS, STRECKEN
from takt import TAKT, TAKT_NEU, takt_lesen
from webseite import slug, strecke_in

ADRESSE = "https://sametrain.goatcounter.com/load-widget"
TAGE = 90
# (Mindestanteil an den Aufrufen, abfragen alle so viele Tage); darunter TAKT_NEU
STUFEN = [(0.02, 1), (0.01, 2), (0.003, 4)]
# Seiten mit langen Pausen zwischen den Abfragen (PAUSE in alle_strecken.py) kosten etwa dreimal so viel Zeit
KOSTEN = {"db": 3, "cd": 3, "oebb": 3}
probe = len(sys.argv) > 1 and sys.argv[1] == "probe"
sys.stdout.reconfigure(errors="replace")


def aufrufe_holen():
    """Pfad -> Aufrufe; lädt die Seitenliste von GoatCounter stückweise, wie der „Show more“-Knopf auf der Seite."""
    ergebnis, ids = {}, []
    while True:
        adresse = ADRESSE + "?" + urllib.parse.urlencode({
            "widget": 0, "exclude": ",".join(ids), "max": 1, "filter": "",
            "period-start": (date.today() - timedelta(days=TAGE)).isoformat(), "period-end": date.today().isoformat()})
        anfrage = urllib.request.Request(adresse, headers={"User-Agent": "sametrain.eu strecken_gewichten"})
        with urllib.request.urlopen(anfrage, timeout=30) as antwort:
            teil = json.load(antwort)
        zeilen = re.findall(r'<tr id="([^"]+)" data-id="(\d+)" data-count="(\d+)"', teil["html"])
        for pfad, nummer, zahl in zeilen:
            ergebnis[pfad] = int(zahl)
            ids.append(nummer)
        if not teil["more"] or not zeilen:
            return ergebnis


try:
    pfade = aufrufe_holen()
except (OSError, ValueError, KeyError) as e:
    print(f"Gewichtung: GoatCounter nicht lesbar ({type(e).__name__}: {e}), Liste bleibt unverändert.")
    sys.exit()

with open(STRECKEN, encoding="utf-8-sig", newline="") as f:
    zeilen = list(csv.DictReader(f, delimiter=";"))
namen = {r["nr"]: r["strecke"] for r in zeilen}
kosten = collections.Counter()
for r in zeilen:
    kosten[r["nr"]] += KOSTEN.get(r["seite"], 1)
aufrufe = {}
for nr, name in namen.items():
    strecke = name.replace(" - ", " – ")
    aufrufe[nr] = (pfade.get(f"/de/strecken/{slug(strecke_in(strecke, 'de'))}.html", 0)
                   + pfade.get(f"/en/routes/{slug(strecke_in(strecke, 'en'))}.html", 0))
gesamt = sum(aufrufe.values())
if not gesamt:
    print("Gewichtung: keine Aufrufe von Streckenseiten gefunden, Liste bleibt unverändert.")
    sys.exit()

bisher = takt_lesen()
takt = {nr: next((t for anteil, t in STUFEN if aufrufe[nr] / gesamt >= anteil), TAKT_NEU) for nr in namen}

# Die Takte 1, 2, 4, 8 gehen ineinander auf, darum genügt es, die 8 möglichen Tage gleichmäßig zu füllen
last = [0] * TAKT_NEU
versatz = {}
for nr in sorted(namen, key=lambda n: (takt[n], -kosten[n], int(n))):
    tage_im_zyklus = lambda v: [t for t in range(TAKT_NEU) if (t + v) % takt[nr] == 0]
    if nr in bisher and bisher[nr][0] == takt[nr]:
        versatz[nr] = bisher[nr][1]
    else:
        versatz[nr] = min(range(takt[nr]), key=lambda v: (max(last[t] for t in tage_im_zyklus(v)), v))
    for t in tage_im_zyklus(versatz[nr]):
        last[t] += kosten[nr]

for alle_tage in sorted(set(takt.values())):
    print(f"alle {alle_tage} Tage: {sum(t == alle_tage for t in takt.values())} Strecken")
for nr in namen:
    if nr in bisher and bisher[nr][0] != takt[nr]:
        print(f"{namen[nr]}: alle {bisher[nr][0]} -> {takt[nr]} Tage")
print(f"Abfragen im Schnitt je Abfragetag: {sum(sum(r['nr'] == nr for r in zeilen) / takt[nr] for nr in namen):.0f} "
      f"(ohne Takt: {len(zeilen)}); Aufwand je Tag von {min(last)} bis {max(last)}")
if probe:
    sys.exit()

if TAKT.exists():
    shutil.copy(TAKT, BASIS / "alte_dateien" / f"takt_{datetime.now():%Y-%m-%d_%H%M}.csv")
with open(TAKT, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["nr", "strecke", "aufrufe", "alle_tage", "versatz"])
    for nr in sorted(namen, key=int):
        w.writerow([nr, namen[nr], aufrufe[nr], takt[nr], versatz[nr]])
