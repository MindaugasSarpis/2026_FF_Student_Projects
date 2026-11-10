"""Euro-Referenzkurse der Europäischen Zentralbank für die Umrechnung von CHF, PLN, CZK usw.

Die Kurse kommen von https://www.ecb.europa.eu (tägliche Referenzkurse, werktags gegen 16 Uhr veröffentlicht)
und werden in daten/kurse.csv zwischengespeichert. Für Tage ohne Kurs (Wochenende, Feiertag, heute vor der
Veröffentlichung) gilt der letzte Kurs davor.

    python skripte/kurse.py    zeigt die neuesten Kurse
"""
import csv
import os
import re
import ssl
import urllib.request
from datetime import date

import certifi  # Zertifikatsliste; wird mit Selenium installiert

from pfade import KURSE

CACHE = KURSE
RECENT = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"  # letzte 90 Tage
FULL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"        # seit 1999
_rates = None  # {datum: {waehrung: Einheiten Fremdwährung je 1 Euro}}
_refreshed = False


def _load():
    rates = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                rates.setdefault(r["datum"], {})[r["waehrung"]] = float(r["je_euro"])
    return rates


def _download(url):
    """Liest die Kurstabelle der EZB und ergänzt den Zwischenspeicher."""
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(url, timeout=30, context=context) as response:
        xml = response.read().decode("utf-8")
    for day, block in re.findall(r"<Cube time=['\"](\d{4}-\d{2}-\d{2})['\"]>(.*?)</Cube>\s*(?=<Cube time|</Cube>)", xml, re.S):
        for currency, rate in re.findall(r"currency=['\"](\w{3})['\"] rate=['\"]([\d.]+)['\"]", block):
            _rates.setdefault(day, {})[currency] = float(rate)
    with open(CACHE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["datum", "waehrung", "je_euro"])
        for day in sorted(_rates):
            for currency, rate in sorted(_rates[day].items()):
                writer.writerow([day, currency, rate])


def euro_rate(currency, day):
    """Wert einer Einheit der Währung in Euro am genannten Tag (JJJJ-MM-TT) und das Datum des benutzten Kurses."""
    global _rates, _refreshed
    if currency == "EUR":
        return 1.0, day
    if _rates is None:
        _rates = _load()
    if not _refreshed and (not _rates or max(_rates) < day):
        # einmal pro Aufruf nachsehen, ob die EZB inzwischen neuere Kurse veröffentlicht hat
        _refreshed = True
        try:
            _download(RECENT)
        except OSError:
            pass  # dann gilt der letzte gespeicherte Kurs, sofern er höchstens fünf Tage alt ist
    for url in (None, RECENT, FULL):
        if url:
            try:
                _download(url)
            except OSError as e:
                raise RuntimeError(f"EZB-Kurse nicht abrufbar ({e}); ohne Kurs keine Umrechnung von {currency}") from e
        known = [d for d in _rates if d <= day and currency in _rates[d]]
        # ein Kurs zählt, wenn er höchstens fünf Tage vor dem gesuchten Tag liegt (Wochenende, Feiertage)
        if known and (date.fromisoformat(day) - date.fromisoformat(max(known))).days <= 5:
            return 1 / _rates[max(known)][currency], max(known)
    raise RuntimeError(f"Kein EZB-Kurs für {currency} in den fünf Tagen bis {day}")


if __name__ == "__main__":
    today = date.today().isoformat()
    for cur in ("CHF", "PLN", "CZK"):
        value, used = euro_rate(cur, today)
        print(f"1 {cur} = {value:.5f} EUR (EZB-Kurs vom {used})")
