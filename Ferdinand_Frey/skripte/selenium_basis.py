"""Gemeinsame Helfer für die Selenium-Skripte der weiteren Bahnen."""
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from pfade import SEITEN
from preise_csv import VISIBLE, append_rows, hide_window, keep_text, read_args
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait

LADEZEIT = 60  # Sekunden, die driver.get höchstens auf das Laden einer Seite wartet

# Sammelt auch Text aus Shadow-DOM-Komponenten ein, den body.text nicht liefert (z. B. bei sbb.ch)
DEEP_TEXT = """
function deep(n) {
    let t = '';
    for (const c of n.childNodes) {
        if (c.nodeType === 3) {
            const s = c.textContent.trim();
            if (s) t += s + '\\n';
        } else if (c.nodeType === 1 && !['SCRIPT', 'STYLE', 'NOSCRIPT', 'svg'].includes(c.tagName)) {
            if (c.shadowRoot) t += deep(c.shadowRoot);
            t += deep(c);
        }
    }
    return t;
}
return deep(document.querySelector('main') || document.body);
"""


def route(start, ziel):
    """Strecke des Skripts; alle_strecken.py überschreibt sie über BAHN_START / BAHN_ZIEL."""
    return os.environ.get("BAHN_START", start), os.environ.get("BAHN_ZIEL", ziel)


def limit_page_load(driver, seconds=LADEZEIT):
    """driver.get wartet höchstens so lange. Selenium wartet sonst bis zu 300 s auf Seiten, die nie fertig laden
    (Werbung, Tracker) - genauso lange, wie alle_strecken.py einer Abfrage insgesamt gibt."""
    driver.set_page_load_timeout(seconds)
    get = driver.get

    def get_limited(url):
        try:
            get(url)
        except TimeoutException:
            print(f"Seite nach {seconds} s nicht fertig geladen, weiter mit dem bisher Geladenen.")
            try:
                driver.execute_script("window.stop()")
            except Exception:
                pass

    driver.get = get_limited
    return driver


def start_driver(headless=False):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,800")
    hide_window(options)
    options.add_argument("--lang=de-DE")
    return limit_page_load(webdriver.Chrome(options=options))


def chrome_major():
    """Hauptversion des installierten Chrome (z. B. 155) aus der Registry, 0 wenn unbekannt."""
    import winreg
    for root, key, value in ((winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon", "version"),
                             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion"
                                                         r"\Uninstall\Google Chrome", "DisplayVersion")):
        try:
            with winreg.OpenKey(root, key) as k:
                return int(winreg.QueryValueEx(k, value)[0].split(".")[0])
        except (OSError, ValueError):
            pass
    return 0


def uc_driver_path(name, major):
    """Eigene, schon gepatchte chromedriver-Datei pro Skript für undetected_chromedriver.
    Ohne das lädt uc bei jedem Start chromedriver neu herunter und ersetzt immer dieselbe Datei in
    %APPDATA%/undetected_chromedriver; laufen db.py und oebb.py gleichzeitig, stoßen sie dabei zusammen
    (FileExistsError WinError 183 / PermissionError WinError 32). So wird nur bei neuer Chrome-Version geladen."""
    from undetected_chromedriver.patcher import Patcher
    folder = Path(Patcher.data_path)
    exe = folder / f"chromedriver_{major}_{name}.exe"
    if Patcher(executable_path=str(exe)).is_binary_patched():
        return str(exe)
    print(f"Lade chromedriver {major} für {name} ...")
    p = Patcher(version_main=major)
    p.version_full = p.fetch_release_number()
    # eigener Entpack-Ordner und eigene Zwischendatei, damit sich gleichzeitige Läufe nicht stören
    p.zip_path = str(folder / f"entpacken_{name}_{os.getpid()}")
    p.executable_path = str(folder / f"chromedriver_{major}_{name}_{os.getpid()}.exe")
    p.unzip_package(p.fetch_package())
    p.patch()
    os.replace(p.executable_path, exe)
    return str(exe)


def start_uc(options, name):
    """Startet undetected_chromedriver (für db.py und oebb.py) mit eigener chromedriver-Datei."""
    import undetected_chromedriver as uc
    major = chrome_major()
    if not major:  # Version unbekannt: wie früher, uc lädt selbst
        return limit_page_load(uc.Chrome(options=options, use_subprocess=True))
    driver = uc.Chrome(options=options, driver_executable_path=uc_driver_path(name, major), version_main=major,
                       use_subprocess=True)
    return limit_page_load(driver)


def deep_text(driver):
    return driver.execute_script(DEEP_TEXT)


def save_page(driver, name):
    """Speichert HTML und Text der Seite als logs/seiten/<name>.html und .txt."""
    with open(SEITEN / f"{name}.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    text = deep_text(driver)
    with open(SEITEN / f"{name}.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print("Seite gespeichert:", SEITEN / f"{name}.html", "und .txt")
    return text


def click_text(driver, pattern, tags="button,a"):
    """Klickt das erste sichtbare Element, dessen Text zum Muster passt; gibt dessen Text zurück."""
    return driver.execute_script("""
        const re = new RegExp(arguments[0], 'i');
        const el = [...document.querySelectorAll(arguments[1])].find(
            e => e.getClientRects().length && re.test((e.innerText || e.value || '').trim()));
        if (el) { el.click(); return (el.innerText || el.value).trim().slice(0, 40); } return null;
    """, pattern, tags)


def type_slowly(element, text, delay=0.08):
    for ch in text:
        element.send_keys(ch)
        time.sleep(delay)


# Elemente auch in (verschachtelten) Shadow-Roots suchen (z. B. nsinternational.com, ouigo.com)
DEEP_FIND = """
const sel = arguments[0], all = [];
function walk(n) { for (const e of n.querySelectorAll('*')) { if (e.matches(sel)) all.push(e); if (e.shadowRoot) walk(e.shadowRoot); } }
walk(document); return all;"""
# Sichtbares innerstes Element mit passendem Text anklicken, auch im Shadow-DOM
DEEP_CLICK_TEXT = """
const re = new RegExp(arguments[0]); let hit = null;
function walk(n) { for (const e of n.querySelectorAll('*')) {
    if (!hit && e.getClientRects().length && re.test((e.innerText || '').trim())
        && ![...e.children].some(c => re.test((c.innerText || '').trim()))) hit = e;
    if (e.shadowRoot) walk(e.shadowRoot); } }
walk(document); if (hit) { (hit.closest('[role=option],li,button,a') || hit).click(); return (hit.innerText || '').trim(); }
return null;"""


def deep_find(driver, sel, visible=True):
    found = driver.execute_script(DEEP_FIND, sel)
    return [e for e in found if e.is_displayed()] if visible else found


def deep_click_text(driver, pattern):
    """Klickt das passende Element (auch im Shadow-DOM); gibt dessen Text zurück oder None."""
    return driver.execute_script(DEEP_CLICK_TEXT, pattern)


def insert_slowly(driver, text, delay=0.25):
    """Tippt über Chrome selbst (CDP) in das Feld mit dem Fokus. Manche Felder ersetzen bei send_keys
    jedes Mal den ganzen Text, sodass am Ende nur der letzte Buchstabe steht."""
    for ch in text:
        driver.execute_cdp_cmd("Input.insertText", {"text": ch})
        time.sleep(delay)


def wait_for_text(driver, needle, seconds=30):
    try:
        WebDriverWait(driver, seconds).until(lambda d: needle in deep_text(d))
        return True
    except Exception:
        print(f"Nach {seconds} s noch kein '{needle}' auf der Seite.")
        return False


def run(quelle, start, ziel, fetch, parse, waehrung="EUR", driver_factory=None):
    """Gemeinsamer Ablauf: Seite abrufen, Verbindungen lesen, Datum prüfen, in die CSV schreiben.
    fetch(driver, datum, uhrzeit) gibt (Seitentext, angezeigtes Reisedatum) zurück.
    driver_factory(headless) liefert bei Bedarf einen anderen Browser, z. B. undetected_chromedriver.
    Aufruf z. B.: python skripte/ltg.py 2026-10-27 08:00"""
    name = quelle.split(".")[0]
    out, headless, datum, uhrzeit = read_args(f"{name}.png")
    if not datum:
        datum, uhrzeit = datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M")

    driver = driver_factory(headless) if driver_factory else start_driver(headless)
    try:
        text, shown = fetch(driver, datum, uhrzeit)
        print("url:", driver.current_url)
        print("title:", driver.title)
        with open(SEITEN / f"{name}_ergebnisseite.txt", "w", encoding="utf-8") as f:
            f.write(text)
        keep_text(text)

        rows = parse(text)
        print("Verbindungen gefunden:", len(rows))
        for r in rows:
            print("  ", r["abfahrt"], "-", r["ankunft"], r["preis"] or r["bemerkung"], "|", r["zuege"])

        if shown != datum:
            print(f"NICHT GESPEICHERT: Seite zeigt {shown or 'kein Datum'} statt {datum}.")
        elif rows:
            append_rows(rows, datum, start, ziel, quelle=quelle, waehrung=waehrung)

        driver.save_screenshot(out)
        if VISIBLE and sys.stdin.isatty():
            input("Drücke Enter, um den Browser zu schließen...")
    finally:
        driver.quit()
