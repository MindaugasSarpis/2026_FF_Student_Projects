"""Setzt einen abgebrochenen täglichen Lauf (taeglich.py) fort, z. B. nach einem Neustart des Rechners.

    python fortsetzen.py

Fragt für die heutigen Reisetage (heute + 7, 21, 42 Tage) nur die Zeilen aus listen/strecken.csv ab, die heute noch
nicht in daten/abfragen_log.csv stehen (egal mit welchem Status, also keine Wiederholungen). Die Restliste steht in
logs/<heute>_rest-<Reisetag>.csv. Danach laufen wie in taeglich.py die Auswertung und die 6er-Regel.
"""
import csv
import os
import subprocess
import sys
from datetime import date, timedelta

VORLAUF_TAGE = [7, 21, 42]  # wie in taeglich.py
UHRZEIT = "08:00"

os.chdir(os.path.dirname(os.path.abspath(__file__)))
heute = date.today().isoformat()

with open(os.path.join("daten", "abfragen_log.csv"), encoding="utf-8", newline="") as f:
    erledigt = {(r["reise_datum"], r["nr"], r["seite"]) for r in csv.DictReader(f, delimiter=";")
                if r["abfrage_datum"] == heute}
with open(os.path.join("listen", "strecken.csv"), encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f, delimiter=";")
    felder, strecken = reader.fieldnames, list(reader)

for days in VORLAUF_TAGE:
    reisetag = (date.today() + timedelta(days=days)).isoformat()
    rest = [r for r in strecken if (reisetag, r["nr"], r["seite"]) not in erledigt]
    print(f"=== Reisetag {reisetag} (heute + {days} Tage): noch {len(rest)} von {len(strecken)} ===", flush=True)
    if not rest:
        continue
    restliste = os.path.abspath(os.path.join("logs", f"{heute}_rest-{reisetag}.csv"))
    with open(restliste, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=felder, delimiter=";")
        w.writeheader()
        w.writerows(rest)
    subprocess.run([sys.executable, os.path.join("skripte", "alle_strecken.py"), reisetag, UHRZEIT, restliste])

print("=== Auswertung und 6er-Regel ===", flush=True)
with open(os.path.join("logs", f"{heute}_auswertung.txt"), "w", encoding="utf-8") as f:
    subprocess.run([sys.executable, os.path.join("skripte", "auswertung.py")], stdout=f, stderr=subprocess.STDOUT,
                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
subprocess.run([sys.executable, os.path.join("skripte", "unbeteiligte_streichen.py")])
