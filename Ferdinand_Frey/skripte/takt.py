"""Wie oft eine Strecke abgefragt wird (listen/takt.csv, geschrieben von skripte/strecken_gewichten.py).

Eine Strecke läuft, wenn (Tagesnummer + versatz) durch alle_tage teilbar ist. Dieser Takt ist bewusst nie 7: Bei
festem Wochentag der Abfrage läge auch der Reisetag immer auf denselben Wochentagen (Vorlauf 1, 7, 21, 42).
"""
import csv
import os
from datetime import date

from pfade import LISTEN

TAKT = LISTEN / "takt.csv"
TAKT_NEU = 8  # Strecken, die noch nicht in takt.csv stehen
IMMER_TAEGLICH = LISTEN / "immer_taeglich.csv"


def lauftag():
    """Der Tag, für den der Takt gilt: taeglich.py hält ihn fest, damit ein Lauf über Mitternacht einheitlich bleibt."""
    return date.fromisoformat(os.environ.get("BAHN_LAUFTAG") or date.today().isoformat())


def takt_lesen():
    """nr -> (alle_tage, versatz); leer, wenn es keine Liste gibt (dann läuft alles täglich)."""
    if not TAKT.exists():
        return {}
    with open(TAKT, encoding="utf-8-sig", newline="") as f:
        return {r["nr"]: (int(r["alle_tage"]), int(r["versatz"])) for r in csv.DictReader(f, delimiter=";")}


def immer_taeglich():
    """Strecken aus listen/immer_taeglich.csv laufen auf Wunsch des Nutzers jeden Tag, egal was die Gewichtung sagt."""
    if not IMMER_TAEGLICH.exists():
        return set()
    with open(IMMER_TAEGLICH, encoding="utf-8-sig", newline="") as f:
        return {r["nr"] for r in csv.DictReader(f, delimiter=";")}


def faellig(nr, takt, tag=None):
    """Ist die Strecke an diesem Tag dran? Ohne Liste immer."""
    if not takt or nr in immer_taeglich():
        return True
    alle_tage, versatz = takt.get(nr, (TAKT_NEU, int(nr) % TAKT_NEU))
    return ((tag or lauftag()).toordinal() + versatz) % alle_tage == 0
