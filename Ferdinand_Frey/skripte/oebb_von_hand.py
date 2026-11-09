"""ÖBB-Abfrage im normalen Chrome für die ÖBB-Strecken aus listen/strecken.csv. Erst nach dem täglichen Lauf starten:
Abgefragt werden die Züge, die andere Verkäufer heute für dieselbe Strecke und denselben Reisetag gezeigt haben.
Das Skript öffnet jeden Zug, kopiert die Seite (Strg+A, Strg+C), speichert den billigsten Preis in daten/preise.csv
(bemerkung = von Hand) und schließt den Tab. Chrome muss vorne bleiben; bei „Forbidden“ stoppt es.

    python skripte/oebb_von_hand.py            alle ÖBB-Strecken
    python skripte/oebb_von_hand.py 15 65      nur diese Streckennummern
    python skripte/oebb_von_hand.py probe      zeigt nur, was offen ist, öffnet nichts
    python skripte/oebb_von_hand.py vortag     nach Mitternacht: fragt die heutigen Reisetage ab, mit den Zügen vom
                                               letzten Lauf der Strecke bei gleichem Vorlauf (fahren sie nicht, wird übersprungen)

Ein Neustart am selben Tag fragt nur ab, was noch fehlt."""
import csv
import ctypes
import msvcrt
import os
import re
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import date, datetime, timedelta
from urllib.parse import quote

from pfade import ABFRAGEN_LOG, LISTEN, LOGS, STRECKEN
from takt import faellig, takt_lesen
from preise_csv import CSV_PATH, TARIF, append_rows, guess_date, trains_from_details

VORLAUF_TAGE = [1, 7, 21, 42]  # wie in taeglich.py
BAHNHOEFE = LISTEN / "oebb_bahnhoefe.csv"  # Name in strecken.csv -> Bahnhofsnummer für den Link
BEMERKUNG = "von Hand"
QUELLE = "oebb.at"
ERLEDIGT = {"gespeichert", "keine Verbindungen"}  # wie in alle_strecken.py
UHRZEIT = "08:00"    # Züge ab dieser Abfahrtszeit, wie in taeglich.py
MAX_ZUEGE = 5        # so viele Züge je Strecke und Reisetag; die alte ÖBB-Suche zeigte ebenfalls höchstens 5
MINDESTABSTAND = 60  # Sekunden zwischen zwei geöffneten Seiten, damit die ÖBB-Server wenig Last haben
LADEZEIT = 6         # Sekunden nach dem Öffnen, bevor zum ersten Mal kopiert wird
VERSUCHE = 15        # so oft wird kopiert, bis ein Ticketangebot dasteht (am 31.10. brauchte eine Seite 10 Versuche)
HINTEN_MAX = 40      # so viele Kopierrunden darf Chrome hinten bleiben (mit WARTEN gut 2 min), dann Stopp
WARTEN = 3           # Sekunden zwischen zwei Kopierversuchen
TAB_SCHLIESSEN = True  # nach jeder Seite Strg+W, damit sich keine Tabs stapeln
NICHT_AM_ENDE = {"2026-11-02"}  # an diesen Lauftagen nicht automatisch am Ende von taeglich.py (Wunsch des Nutzers)
VORTAG_MAX = 9      # vortag: so weit zurück nach dem letzten Lauf einer Strecke suchen (längster Takt: 8 Tage)
# Aussortieren (seit 08.11.2026), weil ÖBB diese Züge nicht anbietet und jede Seite gut eine Minute kostet:
NICHT_OEBB = re.compile(r"\bWB\b|WESTbahn|RegioJet", re.I)  # Züge, die ÖBB nicht verkauft
FEHL_TAGE = 2        # so oft an verschiedenen Tagen „kein Angebot“ bzw. nur die Verbindungsliste: Zug auslassen
FEHL_ZURUECK = 14    # nur die kein_angebot-Logs der letzten so vielen Tage zählen (Fahrpläne ändern sich)

VERBINDUNG = re.compile(r"Verbindung Abfahrt (\d{2}:\d{2}) , Ankunft (\d{2}:\d{2}) (Verbindungsdetails .*)")
ANGEBOT = re.compile(r"^Angebot \d+ von \d+$")
PREIS = re.compile(r"^€ (\d+,\d{2})$")
TARIF_REST = re.compile(r"^\* |€ \d+,\d{2}$")  # im Kopiertext steht der Tarif allein in einer Zeile, sonst mit Stern und Preis

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
# Griffe und Zeiger sind 64 Bit lang, ohne diese Angaben schneidet ctypes sie auf 32 Bit ab
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
CF_UNICODETEXT = 13
VK_CONTROL = 0x11
VK_F24 = 0x87  # Taste ohne Wirkung; Alt ginge nicht, das setzt in Chrome den Fokus aufs Menü
KEYEVENTF_KEYUP = 0x0002


def strg(taste):
    """Drückt Strg + taste im Fenster, das gerade im Vordergrund ist."""
    vk = ord(taste.upper())
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def eigenes_chrome(hwnd):
    """Sichtbares Chrome-Fenster auf dem Bildschirm; die Fenster der anderen Skripte liegen bei -2400 (hide_window)."""
    hwnd = ctypes.c_void_p(hwnd)
    buf = ctypes.create_unicode_buffer(300)
    user32.GetWindowTextW(hwnd, buf, 300)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return user32.IsWindowVisible(hwnd) and buf.value.endswith("Google Chrome") and rect.left > -1000


def chrome_vorne():
    return eigenes_chrome(user32.GetForegroundWindow())


def tagelauf_laeuft():
    """taeglich.py hält logs/taeglich.lock, solange es läuft. Hier nur prüfen, nicht halten, sonst startet es nicht."""
    with open(LOGS / "taeglich.lock", "a+") as f:
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return True
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    return False


def chrome_nach_vorne():
    """Holt das Chrome-Fenster nach vorne. Windows erlaubt das einem Hintergrundprozess nur nach einem Tastendruck."""
    fenster = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def pruefen(hwnd, _):
        if eigenes_chrome(hwnd):
            fenster.append(hwnd)
        return True

    user32.EnumWindows(pruefen, None)
    if fenster:
        user32.keybd_event(VK_F24, 0, 0, 0)
        user32.keybd_event(VK_F24, 0, KEYEVENTF_KEYUP, 0)
        user32.SetForegroundWindow(ctypes.c_void_p(fenster[0]))


def link(zug, datum):
    ankunft_tag = datum if zug["ankunft"] > zug["abfahrt"] else (date.fromisoformat(datum) + timedelta(days=1)).isoformat()
    return ("https://shop.oebbtickets.at/de/ticket?cref=scotty"
            f"&connectionDatetimeDeparture={datum}T{zug['abfahrt']}"
            f"&connectionDatetimeArrival={ankunft_tag}T{zug['ankunft']}"
            f"&connectionOrigEva={zug['start_eva']}&connectionDestEva={zug['ziel_eva']}"
            f"&stationOrigName={quote(zug['start'])}&stationDestName={quote(zug['ziel'])}")


def angebot_lesen(text):
    """Liest aus dem kopierten Ticketangebot Datum, Zeiten, Züge und den billigsten Preis der 2. Klasse."""
    zeilen = [z.strip() for z in text.splitlines() if z.strip()]
    if not any("für 2. Klasse" in z for z in zeilen):
        return None
    nr, treffer = next(((i, m) for i, m in enumerate(map(VERBINDUNG.search, zeilen)) if m), (0, None))
    if not treffer:
        return None
    angebote, preis = [], None
    for z in zeilen:
        if ANGEBOT.match(z):
            preis = None
        elif (m := PREIS.match(z)) and preis is None:
            preis = m.group(1)
            angebote.append({"preis": preis, "tarif": ""})
        elif angebote and not angebote[-1]["tarif"]:
            name = TARIF_REST.sub("", z).strip()
            if TARIF.match(name) and "Angebot" not in name:
                angebote[-1]["tarif"] = name
    if not angebote:
        return None
    billigst = min(angebote, key=lambda a: float(a["preis"].replace(",", ".")))
    abfahrt, ankunft = treffer.group(1), treffer.group(2)
    a, b = datetime.strptime(abfahrt, "%H:%M"), datetime.strptime(ankunft, "%H:%M")
    zuege = trains_from_details(treffer.group(3))
    # Der Reisetag steht direkt über der Verbindung; weiter oben stehen andere Daten („Stornierbar bis Mo, 24. Mai 2027“).
    # Bei morgen steht dort „Morgen“ statt des Datums
    tageszeile = zeilen[nr - 1] if nr else ""
    datum = guess_date(tageszeile) or ((date.today() + timedelta(days=1)).isoformat() if "Morgen" in tageszeile else "")
    row = {
        "datum": datum, "abfahrt": abfahrt, "ankunft": ankunft,
        "dauer_min": ((b - a).seconds // 60), "umstiege": len(zuege) - 1 if zuege else "",
        "zuege": " + ".join(zuege), "tarif": billigst["tarif"], "preis": billigst["preis"], "bemerkung": BEMERKUNG,
    }
    if any("Teilstrecke" in z for z in zeilen):  # Teilpreise zählen als kein Preis
        row.update(tarif="", preis="", bemerkung=f"nur Teilpreis ({billigst['preis']}); {BEMERKUNG}")
    return row


def zwischenablage_oeffnen():
    """Chrome kann die Zwischenablage kurz belegt halten, deshalb ein paar Versuche."""
    for _ in range(20):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.05)
    return False


def zwischenablage_leeren():
    if zwischenablage_oeffnen():
        user32.EmptyClipboard()
        user32.CloseClipboard()


def zwischenablage():
    """Liest den Text direkt von Windows; tkinter lieferte nach dem Leeren fast immer nichts (2.11.: 1 von 11 Seiten)."""
    if not zwischenablage_oeffnen():
        return ""
    try:
        griff = user32.GetClipboardData(CF_UNICODETEXT)
        zeiger = kernel32.GlobalLock(griff) if griff else None
        if not zeiger:
            return ""
        try:
            return ctypes.wstring_at(zeiger)
        finally:
            kernel32.GlobalUnlock(griff)
    finally:
        user32.CloseClipboard()


def seite_kopieren():
    """Strg+A, Strg+C in Chrome. None, wenn gerade ein anderes Fenster vorne ist."""
    if not chrome_vorne():
        return None
    zwischenablage_leeren()
    strg("a")
    time.sleep(0.2)
    strg("c")
    time.sleep(0.5)
    return zwischenablage()


def strecken_lesen(nummern):
    """Die ÖBB-Zeilen aus strecken.csv, ohne das, was die Regeln in alle_strecken.py heute auslassen."""
    with open(STRECKEN, encoding="utf-8-sig", newline="") as f:
        strecken = [r for r in csv.DictReader(f, delimiter=";")
                    if r["seite"] == "oebb" and (not nummern or r["nr"] in nummern)]
    woechentlich = set()
    if (LISTEN / "nur_woechentlich.csv").exists():
        with open(LISTEN / "nur_woechentlich.csv", encoding="utf-8-sig", newline="") as f:
            woechentlich = {r["nr"] for r in csv.DictReader(f, delimiter=";")}
    takt = takt_lesen()
    return [r for r in strecken if r["nr"] in nummern or (date.today().weekday() == 0 if r["nr"] in woechentlich
                                                          else faellig(r["nr"], takt))]


def heutige_preise():
    """(nr, Reisedatum) -> Züge anderer Verkäufer von heute; außerdem die heute schon von Hand gespeicherten Züge,
    die Zugnamen der anderen Verkäufer je Zug und welche Züge (nr, Abfahrt, Ankunft) ÖBB je mit Preis hatte."""
    heute = date.today().isoformat()
    fremd, erledigt, namen, oebb_je = {}, set(), {}, set()
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r["quelle"] == QUELLE and r["preis"]:
                oebb_je.add((r["strecke_nr"], r["abfahrt"], r["ankunft"]))
            if r["abfrage_datum"] != heute:
                continue
            if r["quelle"] != QUELLE:
                if r["preis"] and r["abfahrt"] >= UHRZEIT:
                    fremd.setdefault((r["strecke_nr"], r["reise_datum"]), set()).add((r["abfahrt"], r["ankunft"]))
                    namen.setdefault((r["strecke_nr"], r["reise_datum"], r["abfahrt"], r["ankunft"]), []).append(
                        f"{r['quelle']} {r['zuege']}")
            elif BEMERKUNG in r["bemerkung"]:
                erledigt.add((r["strecke_nr"], r["reise_datum"], r["abfahrt"], r["ankunft"]))
    return fremd, erledigt, namen, oebb_je


def fehlschlaege():
    """(nr, Abfahrt, Ankunft) -> an wie vielen Tagen die ÖBB-Seite „Kein Angebot verfügbar“ oder statt des Tickets nur
    die Verbindungsliste zeigte (dann gibt es den Zug bei ÖBB so nicht; die Liste gilt für jetzt, nicht den Reisetag)."""
    tage = {}
    for d in range(1, FEHL_ZURUECK + 1):
        tag = (date.today() - timedelta(days=d)).isoformat()
        pfad = LOGS / f"{tag}_oebb_kein_angebot.txt"
        if not pfad.exists():
            continue
        for block in pfad.read_text(encoding="utf-8").split("\n=== ")[0:]:
            kopf = re.match(r"(?:=== )?\d\d:\d\d \S+ (\d+) (\d\d:\d\d)-(\d\d:\d\d) ===", block)
            if kopf and ("Kein Angebot verfügbar" in block or re.search(r"(?m)^Verbindungen\s*$", block)):
                tage.setdefault(kopf.groups(), set()).add(tag)
    return {k: len(v) for k, v in tage.items()}


def vortags_zuege():
    """(nr, Reisedatum) -> Züge anderer Verkäufer vom letzten früheren Lauf dieser Strecke (höchstens VORTAG_MAX Tage
    zurück), Reisedatum um den Abstand verschoben (gleicher Vorlauf). Wegen des Takts (listen/takt.csv) lief eine
    Strecke, die heute dran ist, meist nicht gestern, sondern vor 2, 4 oder 8 Tagen."""
    heute = date.today()
    letzter = {}  # (nr, vorlauf) -> (Abfragetag, Züge)
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if not (r["quelle"] != QUELLE and r["preis"] and r["abfahrt"] >= UHRZEIT):
                continue
            tag = date.fromisoformat(r["abfrage_datum"])
            if not 0 < (heute - tag).days <= VORTAG_MAX:
                continue
            vorlauf = (date.fromisoformat(r["reise_datum"]) - tag).days
            k = (r["strecke_nr"], vorlauf)
            if k not in letzter or letzter[k][0] < tag:
                letzter[k] = (tag, set())
            if letzter[k][0] == tag:
                letzter[k][1].add((r["abfahrt"], r["ankunft"]))
    return {(nr, (heute + timedelta(days=vorlauf)).isoformat()): zuege for (nr, vorlauf), (_, zuege) in letzter.items()}


def heutiges_log():
    """Stand von heute in abfragen_log.csv: von oebb.py erledigte und schon von Hand eingetragene Abfragen."""
    heute = date.today().isoformat()
    oebb_py, von_hand = set(), set()
    with open(ABFRAGEN_LOG, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r["abfrage_datum"] == heute and r["seite"] == "oebb" and r["status"] in ERLEDIGT:
                (von_hand if r["hinweis"] == BEMERKUNG else oebb_py).add((r["nr"], r["reise_datum"]))
    return oebb_py, von_hand


def log_schreiben(zug, datum, uhrzeit):
    """auswertung.py wertet nur das Zeitfenster einer Abfrage laut Log, ohne Eintrag nur die ersten 10 Minuten."""
    with open(ABFRAGEN_LOG, "a", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter=";").writerow([date.today().isoformat(), uhrzeit, datum, zug["nr"], zug["strecke"], "oebb",
                                               zug["start"], zug["ziel"], "gespeichert", "", BEMERKUNG])


def aufgaben_bauen(nummern, vortag=False):
    """Offene Züge und die Strecken/Reisetage, für die heute noch kein anderer Verkäufer Preise hat."""
    with open(BAHNHOEFE, encoding="utf-8-sig", newline="") as f:
        eva = {r["name"]: r["eva"] for r in csv.DictReader(f, delimiter=";")}
    fremd, erledigt, namen, oebb_je = heutige_preise()
    if vortag:
        fremd = vortags_zuege()
    fehl = fehlschlaege()
    oebb_py, _ = heutiges_log()
    aufgaben, ohne_vergleich = [], []
    weg = {"WESTbahn/RegioJet": 0, f"bei ÖBB an {FEHL_TAGE}+ Tagen ohne Angebot": 0, "Abfahrt heute schon gespeichert": 0}
    erledigt_ab = {(nr, d, ab) for nr, d, ab, _ in erledigt}
    for t in VORLAUF_TAGE:
        datum = (date.today() + timedelta(days=t)).isoformat()
        for r in strecken_lesen(nummern):
            if (r["nr"], datum) in oebb_py:
                continue
            # Neue Strecke, deren Bahnhof noch nicht in oebb_bahnhoefe.csv steht (am 03.11. brach so der ganze Lauf ab)
            if r["start"] not in eva or r["ziel"] not in eva:
                print(f"Strecke {r['nr']}: Bahnhofsnummer fehlt in {BAHNHOEFE.name}, ausgelassen.")
                continue
            if (r["nr"], datum) not in fremd:
                ohne_vergleich.append((r["nr"], datum))
                continue
            zuege = []
            for abfahrt, ankunft in sorted(fremd[(r["nr"], datum)]):
                if any(NICHT_OEBB.search(n) for n in namen.get((r["nr"], datum, abfahrt, ankunft), [])):
                    weg["WESTbahn/RegioJet"] += 1
                elif (r["nr"], abfahrt, ankunft) not in oebb_je and fehl.get((r["nr"], abfahrt, ankunft), 0) >= FEHL_TAGE:
                    weg[f"bei ÖBB an {FEHL_TAGE}+ Tagen ohne Angebot"] += 1
                elif (r["nr"], datum, abfahrt) in erledigt_ab and (r["nr"], datum, abfahrt, ankunft) not in erledigt:
                    weg["Abfahrt heute schon gespeichert"] += 1
                else:
                    zuege.append((abfahrt, ankunft))
            # Gleiche Abfahrt, leicht andere Ankunft (z. B. MÁV 12:32, ÖBB 12:35): die Variante, die ÖBB schon mal hatte, zuerst
            zuege.sort(key=lambda z: (z[0], (r["nr"], *z) not in oebb_je, z[1]))
            for abfahrt, ankunft in zuege[:MAX_ZUEGE]:
                if (r["nr"], datum, abfahrt, ankunft) not in erledigt:
                    zug = {**r, "start_eva": eva[r["start"]], "ziel_eva": eva[r["ziel"]], "abfahrt": abfahrt, "ankunft": ankunft}
                    aufgaben.append((zug, datum))
    for grund, n in weg.items():
        if n:
            print(f"{n} Züge ausgelassen: {grund}.")
    return aufgaben, ohne_vergleich


def main():
    argumente = sys.argv[1:]
    probe = "probe" in argumente
    if not probe and tagelauf_laeuft():
        print("Der tägliche Lauf läuft noch: erst danach starten, dann sind auch alle Vergleichspreise da.")
        return
    # Von taeglich.py gestartet (setzt BAHN_LAUFTAG) an einem ausgesetzten Tag: nichts tun; von Hand geht es trotzdem
    if os.environ.get("BAHN_LAUFTAG") in NICHT_AM_ENDE:
        print(f"ÖBB am Ende des Tageslaufs ist am {os.environ['BAHN_LAUFTAG']} ausgesetzt (NICHT_AM_ENDE).")
        return
    aufgaben, ohne_vergleich = aufgaben_bauen({a for a in argumente if a not in ("probe", "vortag")}, "vortag" in argumente)
    dauer = len(aufgaben) * MINDESTABSTAND // 60
    print(f"{len(aufgaben)} Seiten offen, mindestens {dauer} min. {len(ohne_vergleich)} Abfragen ohne Preise anderer "
          "Verkäufer von heute ausgelassen.", flush=True)
    if probe:
        for zug, datum in aufgaben:
            print(f"{datum} {zug['nr']:>3} {zug['strecke']:24} {zug['abfahrt']}-{zug['ankunft']}")
        return
    print("Chrome vorne lassen und Tastatur nicht anfassen.", flush=True)
    # Laptop und Bildschirm wach halten, solange das Skript läuft: bei Sperrbildschirm wäre Chrome nicht mehr vorne
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)

    _, eingetragen = heutiges_log()
    gespeichert, zuletzt = 0, 0
    abfahrt_fertig = set()  # (nr, Reisetag, Abfahrt) mit gespeichertem Preis: weitere Varianten derselben Abfahrt auslassen
    for i, (zug, datum) in enumerate(aufgaben, 1):
        if (zug["nr"], datum, zug["abfahrt"]) in abfahrt_fertig:
            print(f"[{i}/{len(aufgaben)}] {datum} {zug['start']} -> {zug['ziel']} {zug['abfahrt']}: "
                  "Abfahrt schon gespeichert, ausgelassen.", flush=True)
            continue
        time.sleep(max(0, zuletzt + MINDESTABSTAND - time.monotonic()))
        zuletzt = time.monotonic()
        uhrzeit = datetime.now().strftime("%H:%M")
        print(f"[{i}/{len(aufgaben)}] {datum} {zug['start']} -> {zug['ziel']} {zug['abfahrt']}", flush=True)
        subprocess.run(["powershell", "-NoProfile", "-Command", f"Start-Process chrome '{link(zug, datum)}'"])
        time.sleep(LADEZEIT)

        row, versuche, hinten = None, 0, 0
        while versuche < VERSUCHE:  # Wartet, solange Chrome hinten ist; das zählt nicht als Versuch
            if not chrome_vorne():
                chrome_nach_vorne()
                time.sleep(0.5)
            text = seite_kopieren()
            if text is None:
                hinten += 1
                print("   Chrome ist nicht im Vordergrund, warte ...", flush=True)
                if hinten >= HINTEN_MAX:
                    print("Chrome bleibt im Hintergrund: Stopp, der Tab bleibt offen. Später neu starten.")
                    print(f"Heute von Hand gespeichert: {gespeichert}")
                    return
            else:
                versuche += 1
                if "Forbidden" in text.splitlines():
                    if TAB_SCHLIESSEN and chrome_vorne():
                        strg("w")
                    print("„Forbidden“ kopiert: Nichts gespeichert, Stopp. Später neu starten.")
                    print(f"Heute von Hand gespeichert: {gespeichert}")
                    return
                if row := angebot_lesen(text):
                    break
                if re.search(r"Angebote? für ", text):  # Nachtzug nur mit Liegewagen o. Ä.: kein Preis der 2. Klasse
                    break
            time.sleep(WARTEN)
        if TAB_SCHLIESSEN and chrome_vorne():
            strg("w")
        if not row:
            print("   Kein Ticketangebot gefunden, übersprungen.", flush=True)
            # Zuletzt kopierten Text aufheben, um später zu sehen, was die Seite gezeigt hat
            with open(LOGS / f"{date.today().isoformat()}_oebb_kein_angebot.txt", "a", encoding="utf-8") as f:
                f.write(f"=== {datetime.now():%H:%M} {datum} {zug['nr']} {zug['abfahrt']}-{zug['ankunft']} ===\n{text or ''}\n\n")
            continue

        if (row["datum"], row["abfahrt"], row["ankunft"]) != (datum, zug["abfahrt"], zug["ankunft"]):
            print(f"   NICHT GESPEICHERT: Seite zeigt {row['datum']} {row['abfahrt']}-{row['ankunft']}.", flush=True)
            continue
        if (zug["nr"], datum) not in eingetragen:
            log_schreiben(zug, datum, uhrzeit)
            eingetragen.add((zug["nr"], datum))
        append_rows([row], datum, zug["start"], zug["ziel"], quelle=QUELLE)
        print(f"   {row['zuege']}: {row['preis'] or row['bemerkung']} € {row['tarif']}", flush=True)
        gespeichert += 1
        if row["preis"]:
            abfahrt_fertig.add((zug["nr"], datum, zug["abfahrt"]))
    print(f"Fertig. Heute von Hand gespeichert: {gespeichert}")


if __name__ == "__main__":
    sys.exit(main())
