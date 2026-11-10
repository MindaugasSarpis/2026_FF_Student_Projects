"""Wo welche Dateien liegen. Alle Skripte benutzen diese Pfade, egal aus welchem Ordner sie gestartet werden."""
from pathlib import Path

BASIS = Path(__file__).resolve().parent.parent
SKRIPTE = BASIS / "skripte"
LISTEN = BASIS / "listen"      # Streckenlisten (was abgefragt wird)
DATEN = BASIS / "daten"        # gesammelte Preise und Hilfsdaten
LOGS = BASIS / "logs"          # Protokolle der Läufe
SEITEN = LOGS / "seiten"       # zuletzt gelesene Ergebnisseiten, zum Nachprüfen
SCREENSHOTS = LOGS / "screenshots"
WEBSEITE = BASIS / "webseite"  # erzeugte Website (skripte/webseite.py)

PREISE = DATEN / "preise.csv"
ABFRAGEN_LOG = DATEN / "abfragen_log.csv"
VERGLEICH = DATEN / "vergleich.csv"
BILLIGSTE_FAHRT = DATEN / "billigste_fahrt.csv"  # je Strecke und Reisetag die billigste Fahrt über alle Züge
KURSE = DATEN / "kurse.csv"
STRECKEN = LISTEN / "strecken.csv"
KANDIDATEN = LISTEN / "kandidaten.csv"
LAENDER = LISTEN / "strecken_laender.csv"

for folder in (DATEN, LISTEN, LOGS, SEITEN, SCREENSHOTS):
    folder.mkdir(parents=True, exist_ok=True)


def in_daten(name):
    """Dateiname aus BAHN_CSV o. Ä.: ohne Ordnerangabe liegt die Datei in daten/."""
    p = Path(name)
    return p if p.is_absolute() or len(p.parts) > 1 else DATEN / p


def in_listen(name):
    p = Path(name)
    return p if p.is_absolute() or len(p.parts) > 1 else LISTEN / p
