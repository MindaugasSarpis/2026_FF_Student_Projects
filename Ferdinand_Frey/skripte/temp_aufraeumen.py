"""Löscht übrig gebliebene Chrome-Profile der Selenium-Abfragen aus %TEMP%.

    python skripte/temp_aufraeumen.py          Ordner älter als 1 Stunde
    python skripte/temp_aufraeumen.py 0        alle (nur, wenn gerade kein Browser der Skripte läuft)

chromedriver legt pro Start einen Ordner scoped_dir*, undetected_chromedriver einen Ordner tmp* mit einem ganzen
Chrome-Profil (~40 MB) an. Wird Chrome hart beendet (taskkill nach 5 min in alle_strecken.py) oder ist er beim
Beenden noch nicht ganz zu, bleiben sie liegen: bis 26.10.2026 waren es ~2.200 Ordner, ~750.000 Dateien, ~47 GB.
Gelöscht werden nur Ordner, die nach einem Chrome-Profil aussehen; Ergebnis in logs/temp_aufraeumen.csv.
Läuft automatisch am Ende von taeglich.py.
"""
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime

from pfade import LOGS

MINDESTALTER = 3600  # Sekunden; jüngere Ordner gehören evtl. zu einem gerade laufenden Browser
PROFIL_MERKMALE = ("Local State", "Default", "Crashpad")


def ist_chrome_ordner(pfad, name):
    if name.startswith("scoped_dir"):
        return True
    return name.startswith("tmp") and any(os.path.exists(os.path.join(pfad, m)) for m in PROFIL_MERKMALE)


def groesse(pfad):
    summe = 0
    for wurzel, _, dateien in os.walk(pfad):
        for d in dateien:
            try:
                summe += os.path.getsize(os.path.join(wurzel, d))
            except OSError:
                pass
    return summe


def aufraeumen(mindestalter=MINDESTALTER):
    temp = tempfile.gettempdir()
    jetzt = time.time()
    geloescht, uebrig, frei = 0, 0, 0
    for eintrag in os.scandir(temp):
        if not eintrag.is_dir(follow_symlinks=False) or not ist_chrome_ordner(eintrag.path, eintrag.name):
            continue
        if jetzt - eintrag.stat().st_mtime < mindestalter:
            continue
        bytes_ = groesse(eintrag.path)
        shutil.rmtree(eintrag.path, ignore_errors=True)
        if os.path.exists(eintrag.path):  # Dateien noch von einem Chrome belegt: beim nächsten Mal
            uebrig += 1
        else:
            geloescht += 1
            frei += bytes_
    neu = not os.path.exists(LOGS / "temp_aufraeumen.csv")
    with open(LOGS / "temp_aufraeumen.csv", "a", encoding="utf-8") as f:
        if neu:
            f.write("zeit;geloescht;nicht_loeschbar;frei_mb\n")
        f.write(f"{datetime.now():%Y-%m-%d %H:%M};{geloescht};{uebrig};{frei / 2**20:.0f}\n")
    print(f"Temp aufgeräumt: {geloescht} Chrome-Ordner gelöscht ({frei / 2**30:.1f} GB), {uebrig} noch belegt.")


if __name__ == "__main__":
    aufraeumen(int(sys.argv[1]) if len(sys.argv) > 1 else MINDESTALTER)
