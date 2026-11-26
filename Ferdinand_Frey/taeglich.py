"""Täglicher Sammellauf für die Frage "welcher Verkäufer ist am billigsten".

Fragt alle Strecken aus listen/strecken.csv für mehrere Reisetage mit festem Abstand zu heute ab. Dadurch ist
jeder Lauf ein neuer Reisetag (keine Wiederholungen), und es gibt Vergleiche für kurze und lange Vorlaufzeiten.

    python taeglich.py           alle Strecken
    python taeglich.py mav 25    nur bestimmte Seiten oder Streckennummern (wie bei skripte/alle_strecken.py)

Die Ausgabe jedes Reisetags steht wie bei alle_strecken.py in logs/<heute>_reise-<Reisetag>/konsole.txt.
Am Ende laufen skripte/auswertung.py und skripte/unbeteiligte_streichen.py (Streichungen in logs/gestrichen.csv)
sowie skripte/temp_aufraeumen.py (löscht übrig gebliebene Chrome-Profile aus %TEMP%), danach wird die Website erzeugt und zu Cloudflare Pages hochgeladen (Protokoll in logs/<heute>_hochladen.txt).
Zuletzt fragt skripte/oebb_von_hand.py ÖBB im sichtbaren Chrome ab (Protokoll in logs/<heute>_oebb_von_hand.txt).
"""
import ctypes
import msvcrt
import os
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta

VORLAUF_TAGE = [1, 7, 21, 42]  # Reisetage: heute + so viele Tage (1 = morgen, Kauf am Vortag)
HOCHLADEN = True            # lädt webseite/ nach jedem Lauf zu Cloudflare hoch (Einstellungen in wrangler.toml)
# Schlägt das Hochladen fehl (am 24. und 27.10. nachts war das WLAN weg), so oft im Abstand von HOCHLADEN_PAUSE
# Sekunden erneut versuchen: 13 Versuche = sofort und dann 2 Stunden lang alle 10 Minuten
HOCHLADEN_VERSUCHE, HOCHLADEN_PAUSE = 13, 10 * 60
UHRZEIT = "08:00"           # Verbindungen ab dieser Abfahrtszeit

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Nur ein Lauf gleichzeitig: die Sperre auf logs/taeglich.lock hält Windows, solange dieser Prozess lebt,
# und gibt sie bei jedem Ende frei, auch bei einem Absturz
_sperre = open(os.path.join("logs", "taeglich.lock"), "a+")
try:
    _sperre.seek(0)
    msvcrt.locking(_sperre.fileno(), msvcrt.LK_NBLCK, 1)
except OSError:
    print("Ein anderer täglicher Lauf läuft noch - dieser wird nicht gestartet.", flush=True)
    sys.exit(0)

# Laptop wach halten, solange der Lauf dauert: verhindert den Standby bei Leerlauf (am 19.10. schlief er
# 16:44-17:39 und 18:04-22:50, der Lauf stand so lange still). Gilt nur für diesen Prozess und endet mit ihm;
# Windows-Einstellungen werden nicht geändert. Deckel zuklappen oder manuelles Schlafenlegen hält es nicht auf.
ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED

# Startdatum einmal festhalten: läuft der Lauf über Mitternacht, verschieben sich die Reisetage sonst um einen Tag
# (am 19.10. wurden so 10.11./01.12. statt 09.11./30.11. abgefragt, und der Lauf am 20.10. ließ sie als erledigt aus)
START = date.today()
os.environ["BAHN_LAUFTAG"] = START.isoformat()  # auch der Takt der Strecken (skripte/takt.py) gilt für den ganzen Lauf
for days in VORLAUF_TAGE:
    reisetag = (START + timedelta(days=days)).isoformat()
    print(f"=== Reisetag {reisetag} (heute + {days} Tage) ===", flush=True)
    # "nachholen": wird der Lauf am selben Tag neu gestartet (z. B. nach einem Abbruch), fragt er nur ab,
    # was heute noch fehlt, statt alles doppelt
    subprocess.run([sys.executable, os.path.join("skripte", "alle_strecken.py"), reisetag, UHRZEIT, "nachholen",
                    *sys.argv[1:]])

# Danach vergleich.csv neu schreiben (Ausgabe in logs/<heute>_auswertung.txt) und unbeteiligte Verkäufer,
# die bei mindestens 6 Abfragen immer teurer waren, aus listen/strecken.csv streichen (6er-Regel)
print("=== Auswertung und 6er-Regel ===", flush=True)
with open(os.path.join("logs", f"{date.today().isoformat()}_auswertung.txt"), "w", encoding="utf-8") as f:
    subprocess.run([sys.executable, os.path.join("skripte", "auswertung.py")], stdout=f, stderr=subprocess.STDOUT,
                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
subprocess.run([sys.executable, os.path.join("skripte", "unbeteiligte_streichen.py")])
# Gleichpreis-Regel: Strecken, auf denen alle Verkäufer immer gleich viel verlangen, nur noch montags abfragen
subprocess.run([sys.executable, os.path.join("skripte", "gleichpreis_pruefen.py")])
# Einmal pro Woche den Takt der Strecken nach den Seitenaufrufen neu festlegen (listen/takt.csv)
if START.weekday() == 0:
    subprocess.run([sys.executable, os.path.join("skripte", "strecken_gewichten.py")])
# Übrig gebliebene Chrome-Profile aus %TEMP% löschen (bis 26.10. ~47 GB; Protokoll in logs/temp_aufraeumen.csv)
subprocess.run([sys.executable, os.path.join("skripte", "temp_aufraeumen.py")])
# Daten und Skripte per Git sichern (Ausgabe auch bei Fehlern nur hier; der Lauf geht in jedem Fall weiter)
subprocess.run([sys.executable, os.path.join("skripte", "sichern.py")], env={**os.environ, "PYTHONIOENCODING": "utf-8"})

# Website neu erzeugen und zu Cloudflare hochladen (Worker "sametrain", Domain sametrain.eu, siehe wrangler.toml).
# Hochgeladen wird nur, wenn die Seite fehlerfrei erzeugt wurde; sonst bleibt die Version vom Vortag online.
# Voraussetzung: einmalig "npx wrangler login" (Anmeldung bleibt auf dem Laptop gespeichert).
print("=== Website erzeugen und hochladen ===", flush=True)
with open(os.path.join("logs", f"{date.today().isoformat()}_hochladen.txt"), "w", encoding="utf-8") as f:
    erzeugt = subprocess.run([sys.executable, os.path.join("skripte", "webseite.py")], stdout=f,
                             stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    npx = shutil.which("npx")
    if erzeugt.returncode != 0:
        print("Website-Erzeugung fehlgeschlagen - nichts hochgeladen.", file=f, flush=True)
    elif not HOCHLADEN:
        print("Website lokal erzeugt; Hochladen ist ausgeschaltet (HOCHLADEN = False in taeglich.py).", file=f, flush=True)
    elif not npx:
        print("npx nicht gefunden (Node.js fehlt?) - nichts hochgeladen.", file=f, flush=True)
    else:
        for versuch in range(1, HOCHLADEN_VERSUCHE + 1):
            print(f"--- Versuch {versuch} um {datetime.now():%H:%M} ---", file=f, flush=True)
            # CI=true: wrangler fragt nichts nach, sondern bricht bei Problemen (z. B. nicht angemeldet) mit Fehler ab
            hoch = subprocess.run([npx, "--yes", "wrangler", "deploy"],
                                  stdout=f, stderr=subprocess.STDOUT, env={**os.environ, "CI": "true"})
            if hoch.returncode == 0:
                print("Hochgeladen.", file=f, flush=True)
                break
            print(f"Hochladen fehlgeschlagen (Code {hoch.returncode}).", file=f, flush=True)
            if versuch < HOCHLADEN_VERSUCHE:
                print(f"Nächster Versuch in {HOCHLADEN_PAUSE // 60} min.", file=f, flush=True)
                time.sleep(HOCHLADEN_PAUSE)
        # Bing & Co. per IndexNow Bescheid geben, dass die Seiten neu sind (nur nach erfolgreichem Hochladen)
        if hoch.returncode == 0:
            subprocess.run([sys.executable, os.path.join("skripte", "indexnow.py")], stdout=f,
                           stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8"})

# Zum Schluss ÖBB im normalen Chrome (skripte/oebb_von_hand.py, laut Nutzer von ÖBB erlaubt): öffnet sichtbar Seiten
# und drückt Strg+A/C/W, bis zu einige Stunden lang. Die Preise kommen mit dem nächsten Lauf in Auswertung und Website.
# Vorher die Sperre freigeben, sonst verweigert das Skript den Start („Der tägliche Lauf läuft noch“).
OEBB_AM_ENDE = True
if OEBB_AM_ENDE:
    _sperre.seek(0)
    msvcrt.locking(_sperre.fileno(), msvcrt.LK_UNLCK, 1)
    print("=== ÖBB im normalen Chrome ===", flush=True)
    with open(os.path.join("logs", f"{date.today().isoformat()}_oebb_von_hand.txt"), "a", encoding="utf-8") as f:
        subprocess.run([sys.executable, os.path.join("skripte", "oebb_von_hand.py")], stdout=f,
                       stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
