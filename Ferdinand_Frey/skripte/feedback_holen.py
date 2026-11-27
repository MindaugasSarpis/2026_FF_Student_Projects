"""Holt die Nachrichten aus dem Feedback-Formular der Website (D1-Datenbank sametrain-feedback bei Cloudflare)
und schreibt sie nach daten/feedback.csv (immer alle, Datei wird neu geschrieben). Braucht npx wrangler login.

Aufruf: python skripte/feedback_holen.py"""
import csv
import json
import subprocess
import sys
import time

from pfade import DATEN

SPALTEN = ["id", "zeit", "sprache", "seite", "art", "nachricht", "email"]
VERSUCHE = 3      # Cloudflare lehnt die Abfrage gelegentlich einmalig ab (Fehler 7403, 30.10.2026), kurz danach geht sie wieder
PAUSE = 20        # Sekunden zwischen den Versuchen


def fehlertext(erg):
    """Mit --json steht der echte Fehler als JSON in stdout; stderr enthält oft nur npm-Hinweise."""
    try:
        fehler = json.loads(erg.stdout)["error"]
        return " - ".join([fehler["text"]] + [n["text"] for n in fehler.get("notes", [])])
    except (ValueError, KeyError, TypeError):
        return f"{erg.stdout}\n{erg.stderr}".strip()


def abfragen():
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    befehl = [npx, "--yes", "wrangler", "d1", "execute", "sametrain-feedback", "--remote", "--json",
              "--command", "SELECT * FROM feedback ORDER BY id"]
    for versuch in range(1, VERSUCHE + 1):
        erg = subprocess.run(befehl, cwd=DATEN.parent, capture_output=True, text=True, encoding="utf-8")
        if not erg.returncode:
            return json.loads(erg.stdout)[0]["results"]
        print(f"Versuch {versuch}/{VERSUCHE} gescheitert: {fehlertext(erg)}", file=sys.stderr)
        if versuch < VERSUCHE:
            time.sleep(PAUSE)
    sys.exit("wrangler-Fehler: Nachrichten nicht abgeholt, daten/feedback.csv bleibt unverändert.")


def main():
    zeilen = abfragen()
    ziel = DATEN / "feedback.csv"
    with open(ziel, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, SPALTEN, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(zeilen)
    print(f"{len(zeilen)} Nachrichten -> {ziel}")
    for z in zeilen[-5:]:
        print(f"  {z['zeit'][:16]} [{z['art']}] {z['nachricht'][:80]!r}")


if __name__ == "__main__":
    main()
