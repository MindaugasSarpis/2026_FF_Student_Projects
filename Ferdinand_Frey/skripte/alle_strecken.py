"""Führt alle Strecken aus listen/strecken.csv auf den jeweiligen Seiten aus.

    python skripte/alle_strecken.py 2026-10-20                   alle Zeilen
    python skripte/alle_strecken.py 2026-10-20 08:00 ltg         nur LTG Link, ab 08:00
    python skripte/alle_strecken.py 2026-10-20 1 6 17            nur die Strecken Nr. 1, 6 und 17
    python skripte/alle_strecken.py 2026-10-20 kandidaten.csv    eine andere Liste aus listen/
    python skripte/alle_strecken.py 2026-10-20 nachholen         nur, was heute für den Reisetag noch fehlt

Fehlgeschlagene Abfragen (fehler, blockiert, nicht gespeichert) werden am Ende einmal wiederholt.
Die Preise landen in daten/preise.csv; was pro Zeile passiert ist, steht in daten/abfragen_log.csv.
Die gesamte Konsolenausgabe eines Laufs steht in logs/<Abfragetag>_reise-<Reisetag>/konsole.txt.
"""
import csv
import json
import os
import random
import re
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

from pfade import ABFRAGEN_LOG, LISTEN, LOGS, SCREENSHOTS, SKRIPTE, STRECKEN, in_listen
from takt import faellig, takt_lesen

# Die Windows-Konsole kann nur cp1252: Zeichen wie "ł" (Kraków Główny) oder "Č" würden print abbrechen lassen
# und damit still die ganze Kette einer Seite beenden. Nicht darstellbare Zeichen werden deshalb ersetzt.
for _strom in (sys.stdout, sys.stderr):
    try:
        _strom.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

# Jede Seite hat ein Skript skripte/<kürzel>.py; das Kürzel steht in der Spalte "seite" der Streckenliste
# Diese Seiten laufen ganz ohne Fenster; db, oebb, sbb und eurostar öffnen eines außerhalb des Bildschirms
HEADLESS = {"ltg", "elron", "vivi", "koleo", "trenitalia", "pkp", "mav", "cd", "sncb", "ouigo"}
PARALLEL = 3  # so viele Seiten (Browser) gleichzeitig
# Pause zwischen zwei Abfragen derselben Seite in Sekunden (von, bis; zufällig dazwischen).
# bahn.de sperrt sonst nach etwa 10 Abfragen kurz hintereinander
# cd.cz sperrte ab 21.10.2026 abends die Adresse des WLANs (vorher 5 s Pause), seitdem wie bahn.de
# oebb.at sperrte ab 27.10.2026 die Adresse (vorher 5 s Pause), seit 30.10. deshalb ebenso
PAUSE = {"db": (20, 40), "cd": (20, 40), "oebb": (20, 40)}
PAUSE_SONST = (5, 5)
# Nach einer Sperre ("blockiert") diese Seite so lange in Ruhe lassen, statt sie gleich wieder abzufragen.
# 5 min reichten bei bahn.de nicht (20.10.: nach der Pause oft gleich die nächste Sperre, nach Stunden Ruhe keine)
# oebb: gilt für gewöhnliche Sperren (Sicherheitsprüfung); bei Sperre der Adresse greift SPERRE_AUSSETZEN
ABKUEHLEN = {"db": 20 * 60, "oebb": 20 * 60}
# Nach so vielen Sperren hintereinander kommen die restlichen Abfragen dieser Seite ans Ende des Laufs,
# damit sie nicht mit langen Pausen einen der PARALLEL Plätze belegt, während andere Seiten warten
NACH_HINTEN_AB = 2
# Seiten, deren Sperre die ganze Adresse betrifft (cd.cz antwortet dann gar nicht mehr): nach einer Sperre so viele
# Sekunden gar nicht mehr abfragen, auch nicht in den folgenden Reisetagen (eigene Prozesse). Der Zeitpunkt der
# Sperre steht deshalb in logs/sperren.json. Ausgelassene Abfragen werden mit Status "ausgelassen" protokolliert.
# Gilt nur, wenn das Skript „SPERRE DER ADRESSE“ meldet (cd.cz: keine Antwort mehr; oebb.at seit 27.10.2026 abends:
# Fenster „Forbidden“ bei jeder Suche). Gewöhnliche Sperren (z. B. ÖBB-Sicherheitsprüfung) lösen das nicht aus.
SPERRE_AUSSETZEN = {"cd": 6 * 3600, "oebb": 6 * 3600}
ADRESSE_GESPERRT = "Adresse gesperrt"
HINWEISE = {}  # (nr, seite) -> Hinweis der letzten Abfrage in diesem Lauf
SPERREN = LOGS / "sperren.json"
NACH_HINTEN_RUNDEN = 3  # so oft darf eine Seite höchstens ans Ende geschoben werden
NACHGESTELLT = []  # Abfragen, die ans Ende geschoben wurden
LETZTE_SPERRE = {}  # seite -> Zeitpunkt (time.time()) der letzten Sperre
LOCK = threading.Lock()
LOG = ABFRAGEN_LOG
LOG_HEADER = ["abfrage_datum", "abfrage_uhrzeit", "reise_datum", "nr", "strecke", "seite", "start", "ziel",
              "status", "verbindungen", "hinweis"]
# Diese Ergebnisse gelten als erledigt; alles andere wird am Ende einmal wiederholt bzw. beim Nachholen neu versucht
ERLEDIGT = {"gespeichert", "keine Verbindungen"}
# Baltische Strecken (Vilnius/Riga - Tartu/Tallinn): Züge sind erst kurz vorher buchbar, für weiter entfernte
# Reisetage zeigen LTG und Elron nie Verbindungen. Deshalb nur bis zu so vielen Tagen Vorlauf abfragen.
NUR_KURZFRISTIG, MAX_VORLAUF_KURZ = {"2", "3", "4", "5"}, 14
# Ohne Internet (nachts fiel das WLAN mehrmals aus, z. B. 24. und 27.10.) liefen alle Abfragen sofort als „fehler“
# durch und der Reisetag war verloren. Jetzt wird vor jeder Abfrage geprüft, ob das Internet da ist, und sonst
# gewartet: alle INTERNET_PRUEFEN Sekunden, höchstens INTERNET_WARTEN_MAX Sekunden, danach geht es trotzdem weiter.
# Eine Abfrage, die mit „fehler“ endet, während das Internet weg ist, wird danach einmal neu gestartet.
INTERNET_PRUEFEN, INTERNET_WARTEN_MAX = 60, 4 * 3600
INTERNET_ZIELE = [("1.1.1.1", 443), ("8.8.8.8", 53), ("www.bahn.de", 443)]
INTERNET_LOCK = threading.Lock()

datum, uhrzeit, filters, liste, nachholen = "", "06:00", set(), STRECKEN, False
for arg in sys.argv[1:]:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", arg):
        datum = arg
    elif re.fullmatch(r"\d{1,2}:\d{2}", arg):
        uhrzeit = arg
    elif arg.endswith(".csv"):
        liste = in_listen(arg)  # andere Streckenliste, z. B. kandidaten.csv
    elif arg == "nachholen":
        nachholen = True
    else:
        filters.add(arg)
if not datum:
    sys.exit("Bitte ein Reisedatum angeben, z. B.: python skripte/alle_strecken.py 2026-10-20")

with open(liste, encoding="utf-8-sig", newline="") as f:
    routes = [r for r in csv.DictReader(f, delimiter=";") if not filters or r["nr"] in filters or r["seite"] in filters]

vorlauf = (date.fromisoformat(datum) - date.today()).days
kurz_weg = [r for r in routes if r["nr"] in NUR_KURZFRISTIG and vorlauf > MAX_VORLAUF_KURZ]
routes = [r for r in routes if r not in kurz_weg]

# Gleichpreis-Regel (skripte/gleichpreis_pruefen.py): Strecken, auf denen alle Verkäufer immer gleich viel verlangen,
# nur montags abfragen - außer man hat sie ausdrücklich per Nummer verlangt
woechentlich = set()
if os.path.exists(LISTEN / "nur_woechentlich.csv"):
    with open(LISTEN / "nur_woechentlich.csv", encoding="utf-8-sig", newline="") as f:
        woechentlich = {r["nr"] for r in csv.DictReader(f, delimiter=";")}
woche_weg = [r for r in routes if r["nr"] in woechentlich and r["nr"] not in filters and date.today().weekday() != 0]
routes = [r for r in routes if r not in woche_weg]

# Gewichtung (skripte/strecken_gewichten.py): wenig angesehene Strecken seltener abfragen - außer man hat sie per
# Nummer verlangt. Gilt für strecken.csv und die Restlisten von fortsetzen.py, nicht für Testlisten wie kandidaten.csv.
# Die Gleichpreis-Regel oben geht vor (ihre Strecken laufen montags).
takt_plan = takt_lesen() if liste == STRECKEN or "_rest-" in liste.name else {}
takt_weg = [r for r in routes if r["nr"] not in filters and r["nr"] not in woechentlich
            and not faellig(r["nr"], takt_plan)]
routes = [r for r in routes if r not in takt_weg]

# Nachholen: was heute für diesen Reisetag schon erledigt wurde, nicht noch einmal abfragen (z. B. nach einem Abbruch)
schon_erledigt = []
if nachholen and os.path.exists(ABFRAGEN_LOG):
    letzter = {}
    with open(ABFRAGEN_LOG, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r["abfrage_datum"] == date.today().isoformat() and r["reise_datum"] == datum:
                letzter[(r["nr"], r["seite"])] = r["status"]
    schon_erledigt = [r for r in routes if letzter.get((r["nr"], r["seite"])) in ERLEDIGT]
    routes = [r for r in routes if r not in schon_erledigt]

# Jeder Lauf bekommt einen eigenen Ordner: konsole.txt enthält die Ausgabe aller Abfragen,
# daneben liegt pro Abfrage eine Datei mit der vollständigen Ausgabe des Skripts samt Fehlermeldungen
RUN_DIR = LOGS / f"{datetime.now():%Y-%m-%d}_reise-{datum}"
suffix = 2
while os.path.exists(RUN_DIR):
    RUN_DIR = LOGS / f"{datetime.now():%Y-%m-%d}_reise-{datum}_{suffix}"
    suffix += 1
os.makedirs(RUN_DIR)
CONSOLE = open(f"{RUN_DIR}/konsole.txt", "w", encoding="utf-8")


def say(text=""):
    """Schreibt auf die Konsole und in konsole.txt."""
    try:
        print(text, flush=True)
    except Exception:  # Konsole kaputt oder Zeichen nicht darstellbar: wenigstens konsole.txt schreiben
        pass
    CONSOLE.write(text + "\n")
    CONSOLE.flush()


say(f"{len(routes)} Abfragen für {datum} ab {uhrzeit} - Ausgabe in {RUN_DIR / 'konsole.txt'}")
if kurz_weg:
    say(f"  {len(kurz_weg)} baltische Abfragen ausgelassen (nur bis {MAX_VORLAUF_KURZ} Tage Vorlauf buchbar)")
if woche_weg:
    say(f"  {len(woche_weg)} Abfragen ausgelassen: Strecken mit immer gleichen Preisen laufen nur montags")
if takt_weg:
    say(f"  {len(takt_weg)} Abfragen ausgelassen: wenig angesehene Strecken sind heute nicht dran (listen/takt.csv)")
if schon_erledigt:
    say(f"  {len(schon_erledigt)} Abfragen heute schon erledigt, werden nicht wiederholt")
say()
RESULTS = {}  # (nr, seite) -> letzter Status in diesem Lauf


def run_one(r):
    """Startet das Skript der Seite mit der Strecke der Zeile; gibt (status, verbindungen, hinweis, ausgabe) zurück."""
    cmd = [sys.executable, str(SKRIPTE / f"{r['seite']}.py"), str(SCREENSHOTS / f"{r['nr']}_{r['seite']}.png"),
           datum, uhrzeit]
    if r["seite"] in HEADLESS:
        cmd.append("headless")
    env = dict(os.environ, BAHN_START=r["start"], BAHN_ZIEL=r["ziel"], BAHN_LISTE=str(liste), PYTHONIOENCODING="utf-8",
               # Seitentext pro Abfrage aufheben, damit sich Preise später nachprüfen lassen
               BAHN_SEITE=f"{RUN_DIR}/{r['nr']}_{r['seite']}_seite.txt")
    p = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", errors="replace")
    try:
        p.stdout, p.stderr = p.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        # Mit dem ganzen Prozessbaum beenden: ein übrig gebliebener Chrome hält sonst die Ausgabe offen
        # und die Abfragen dieser Seite bleiben für immer hängen
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
        try:
            out, err = p.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        # Bisherige Ausgabe aufheben; preise_csv.py schreibt kurz vor dem Abbruch, wo das Skript gerade hängt
        with open(f"{RUN_DIR}/{r['nr']}_{r['seite']}.txt", "w", encoding="utf-8") as f:
            f.write((out or "") + "\n--- Fehlerausgabe ---\n" + (err or ""))
        return "fehler", "", "nach 5 min abgebrochen", out or ""
    with open(f"{RUN_DIR}/{r['nr']}_{r['seite']}.txt", "w", encoding="utf-8") as f:
        f.write(p.stdout + "\n--- Fehlerausgabe ---\n" + p.stderr)
    found = re.search(r"Verbindungen gefunden: (\d+)", p.stdout)
    count = found.group(1) if found else ""
    if "Zeile(n) in" in p.stdout:
        return "gespeichert", count, "", p.stdout
    if m := re.search(r"NICHT GESPEICHERT: (.*)", p.stdout):
        return "nicht gespeichert", count, m.group(1), p.stdout
    if "SPERRE DER ADRESSE" in p.stdout:
        return "blockiert", count, ADRESSE_GESPERRT, p.stdout
    if "BLOCKIERT" in p.stdout:
        return "blockiert", count, "Suche von der Seite abgelehnt", p.stdout
    if count == "0":
        return "keine Verbindungen", count, "", p.stdout
    # "WinError 6" meldet undetected_chromedriver bei jedem Beenden; das ist nicht die Ursache
    errors = [l for l in p.stderr.splitlines()
              if re.match(r"^[\w.]+(Error|Exception)\b", l) and "WinError 6" not in l]
    hint = errors[-1] if errors else p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
    return "fehler", count, hint[:200], p.stdout


def sperren_lesen():
    try:
        return json.loads(SPERREN.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def gesperrt_bis(seite):
    """Zeitpunkt (time.time()), bis zu dem die Seite nach einer Sperre ausgelassen wird; 0 = nicht gesperrt."""
    if seite not in SPERRE_AUSSETZEN:
        return 0
    bis = sperren_lesen().get(seite, 0) + SPERRE_AUSSETZEN[seite]
    return bis if bis > time.time() else 0


def sperre_merken(seite):
    with LOCK:
        sperren = sperren_lesen()
        sperren[seite] = time.time()
        SPERREN.write_text(json.dumps(sperren), encoding="utf-8")


def online():
    """True, wenn mindestens eins der INTERNET_ZIELE erreichbar ist (nur Verbindungsaufbau, nichts gesendet)."""
    for ziel in INTERNET_ZIELE:
        try:
            socket.create_connection(ziel, timeout=5).close()
            return True
        except OSError:
            pass
    return False


def warte_auf_internet():
    """Wartet, bis das Internet wieder da ist (alle Seiten-Threads warten gemeinsam, gemeldet wird einmal).
    Gibt True zurück, wenn gewartet wurde."""
    if online():
        return False
    with INTERNET_LOCK:  # der erste Thread wartet, die anderen warten hinter ihm am Lock
        if online():
            return True
        seit = time.time()
        say(f"   Kein Internet seit {datetime.now():%H:%M}, warte (Prüfung alle {INTERNET_PRUEFEN} s) ...")
        while not online():
            if time.time() - seit > INTERNET_WARTEN_MAX:
                say(f"   Nach {INTERNET_WARTEN_MAX // 3600} h immer noch kein Internet, es geht trotzdem weiter")
                return True
            time.sleep(INTERNET_PRUEFEN)
        say(f"   Internet wieder da um {datetime.now():%H:%M} (nach {(time.time() - seit) / 60:.0f} min)")
        return True


def run_site(site_routes, log, f, label=""):
    """Arbeitet die Abfragen einer Seite nacheinander ab; ein Fehler bei einer Abfrage beendet die Kette nicht.
    Nach einer Sperre lange Pause; nach NACH_HINTEN_AB Sperren hintereinander kommt der Rest ans Ende des Laufs."""
    gesperrt = 0
    for i, r in enumerate(site_routes):
        seite = r["seite"]
        if bis := gesperrt_bis(seite):
            ausgelassen(r, log, f, label, f"{seite} nach Sperre ausgesetzt bis {datetime.fromtimestamp(bis):%d.%m. %H:%M}")
            continue
        for versuch in range(2):
            warte_auf_internet()
            try:
                status = run_site_one(r, log, f, label + ("(nach Internet-Ausfall) " if versuch else ""))
            except Exception as e:  # z. B. beim Schreiben der Ausgabe; ThreadPoolExecutor würde das sonst verschlucken
                with LOCK:
                    say(f"{r['nr']:>2} {r['strecke']:22} {seite:11} Ausnahme im Ablauf: {type(e).__name__}: {e}"[:300])
                status = "fehler"
            # Fehler während das Internet weg ist: liegt nicht an der Seite, deshalb nach dem Warten noch einmal.
            # Auch „Adresse gesperrt“ (cd.cz: keine Antwort) sieht ohne Internet genauso aus: dann keine 6-h-Sperre
            netz_typisch = status == "fehler" or HINWEISE.get((r["nr"], seite)) == ADRESSE_GESPERRT
            if not netz_typisch or online():
                break
            HINWEISE[(r["nr"], seite)] = "kein Internet"
        rest = site_routes[i + 1:]
        if (status == "blockiert" and seite in SPERRE_AUSSETZEN
                and HINWEISE.get((r["nr"], seite)) == ADRESSE_GESPERRT):
            # keine Pause nötig: die übrigen Abfragen der Seite werden ab jetzt ausgelassen
            sperre_merken(seite)
            continue
        # Dieselbe Seite nicht im Sekundentakt abfragen; nach einer Sperre länger warten
        if status == "blockiert" and seite in ABKUEHLEN:
            gesperrt += 1
            LETZTE_SPERRE[seite] = time.time()
            if gesperrt >= NACH_HINTEN_AB and rest:
                with LOCK:
                    NACHGESTELLT.extend(rest)
                    say(f"   {seite}: {gesperrt} Sperren hintereinander, {len(rest)} Abfragen kommen ans Ende des Laufs")
                return
            if rest:
                with LOCK:
                    say(f"   {seite}: gesperrt, {ABKUEHLEN[seite] // 60} min Pause")
                time.sleep(ABKUEHLEN[seite])
        else:
            if status != "blockiert":
                gesperrt = 0
            if rest:
                time.sleep(random.uniform(*PAUSE.get(seite, PAUSE_SONST)))


def ausgelassen(r, log, f, label, hint):
    """Protokolliert eine Abfrage, die wegen einer Sperre gar nicht erst gestartet wurde."""
    now = datetime.now()
    RESULTS[(r["nr"], r["seite"])] = "ausgelassen"
    with LOCK:
        log.writerow([now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), datum, r["nr"], r["strecke"], r["seite"],
                      r["start"], r["ziel"], "ausgelassen", "", hint])
        f.flush()
        say(f"{r['nr']:>2} {r['strecke']:22} {r['seite']:11} {'ausgelassen':18}     {label}{hint}")


def run_site_one(r, log, f, label=""):
    """Eine Abfrage samt Log-Zeile und Ausgabe; gibt den Status zurück."""
    now = datetime.now()
    try:
        status, count, hint, output = run_one(r)
    except Exception as e:
        status, count, hint, output = "fehler", "", f"{type(e).__name__}: {e}"[:200], ""
    RESULTS[(r["nr"], r["seite"])] = status
    HINWEISE[(r["nr"], r["seite"])] = hint
    with LOCK:
        # Log-Zeile zuerst, damit sie auch dann geschrieben wird, wenn die Ausgabe scheitert
        log.writerow([now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), datum, r["nr"], r["strecke"], r["seite"],
                      r["start"], r["ziel"], status, count, hint])
        f.flush()
        say(f"{r['nr']:>2} {r['strecke']:22} {r['seite']:11} {status:18} {count:>3} {label}{hint}")
        say("".join(f"      {line}\n" for line in output.splitlines()))
    return status


new_log = not os.path.exists(LOG)
with open(LOG, "a", newline="", encoding="utf-8") as f:
    log = csv.writer(f, delimiter=";")
    if new_log:
        log.writerow(LOG_HEADER)
    def run_pool(todo, label=""):
        by_site = {}
        for r in todo:
            by_site.setdefault(r["seite"], []).append(r)
        # Verschiedene Seiten laufen gleichzeitig, jede einzelne Seite wird weiter der Reihe nach abgefragt
        with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
            jobs = {pool.submit(run_site, site_routes, log, f, label): seite for seite, site_routes in by_site.items()}
        # Ausnahmen der Threads sichtbar machen, statt sie still zu verschlucken
        for job, seite in jobs.items():
            if job.exception():
                say(f"   {seite}: Kette abgebrochen: {type(job.exception()).__name__}: {job.exception()}"[:300])

    def run_all(todo, label=""):
        run_pool(todo, label)
        # Ans Ende geschobene Abfragen: erst weiter, wenn die Sperre der Seite lange genug her ist
        for runde in range(NACH_HINTEN_RUNDEN):
            if not NACHGESTELLT:
                return
            spaeter = NACHGESTELLT[:]
            NACHGESTELLT.clear()
            seiten = {r["seite"] for r in spaeter}
            warten = max(0, max(LETZTE_SPERRE.get(s, 0) + ABKUEHLEN.get(s, 0) for s in seiten) - time.time())
            say(f"\n--- {len(spaeter)} ans Ende geschobene Abfragen ({', '.join(sorted(seiten))}), "
                f"weiter in {warten / 60:.0f} min ---\n")
            time.sleep(warten)
            run_pool(spaeter, label + "(nachgestellt) ")
        if NACHGESTELLT:  # auch nach der letzten Runde noch gesperrt: laufen in der Wiederholung mit
            say(f"   {len(NACHGESTELLT)} Abfragen auch nach {NACH_HINTEN_RUNDEN} Runden noch gesperrt")
            NACHGESTELLT.clear()

    run_all(routes)
    # Fehlgeschlagene Abfragen einmal wiederholen: oft war die Seite nur kurz langsam oder hat sich neu aufgebaut
    # (wegen einer Sperre ausgelassene Abfragen nicht: die Sperre gilt noch)
    retry = [r for r in routes if RESULTS.get((r["nr"], r["seite"])) not in ERLEDIGT | {"ausgelassen"}]
    if retry:
        say(f"\n--- Wiederholung von {len(retry)} fehlgeschlagenen Abfragen ---\n")
        run_all(retry, "(Wiederholung) ")
        still = [r for r in retry if RESULTS.get((r["nr"], r["seite"])) not in ERLEDIGT]
        say(f"Nach der Wiederholung erledigt: {len(retry) - len(still)} von {len(retry)}")

say(f"Fertig um {datetime.now():%H:%M}. Preise in daten/preise.csv, Übersicht in daten/abfragen_log.csv.")
