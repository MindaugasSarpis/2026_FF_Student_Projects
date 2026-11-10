"""Lädt den Open-Data-Datensatz „Tarifs TGV INOUI et OUIGO“ von SNCF Voyageurs nach daten/sncf_tarife.csv
(Preisspanne min–max des vollen Tarifs je Verbindung, Klasse und Tarifprofil; nur Inlandsverbindungen) und das
Datum der letzten Änderung nach daten/sncf_tarife_stand.txt. webseite.py zeigt daraus auf französischen Strecken
die SNCF-Spanne, weil sich SNCF Connect nicht automatisch abfragen lässt. Lizenz: ODbL.
Hinweis von Jean-Baptiste Marie (1.2.Train), 26.10.2026. Nur bei Bedarf neu laden, z. B. wenn SNCF neue Tarife
veröffentlicht: python skripte/sncf_tarife_holen.py"""
import json
import urllib.request

from pfade import DATEN

API = "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/tarifs-tgv-inoui-ouigo"

with urllib.request.urlopen(API, timeout=60) as antwort:
    stand = json.load(antwort)["metas"]["default"]["modified"][:10]
with urllib.request.urlopen(API + "/exports/csv?delimiter=%3B", timeout=120) as antwort:
    (DATEN / "sncf_tarife.csv").write_bytes(antwort.read())
(DATEN / "sncf_tarife_stand.txt").write_text(stand, encoding="utf-8")
print(f"SNCF-Tarife gespeichert (Stand {stand}) -> {DATEN / 'sncf_tarife.csv'}")
