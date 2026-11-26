import json
import os
import re
import sys
import time
from datetime import date
import undetected_chromedriver as uc
from pfade import DATEN, SEITEN
from preise_csv import VISIBLE, append_rows, guess_date, hide_window, keep_text, parse, read_args
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_basis import start_uc

# Argumente einlesen
# z. B.: python skripte/db.py 2026-10-27 08:00
out, headless, datum, uhrzeit = read_args("db.png")
# Strecke: Vorgabe hier, oder von alle_strecken.py über BAHN_START / BAHN_ZIEL gesetzt
START = os.environ.get("BAHN_START", "München Hbf")
ZIEL = os.environ.get("BAHN_ZIEL", "Wien Hbf")
# Mit 'mit-tarife' wird zu jeder Verbindung die Angebotsseite geöffnet und der Name des billigsten
# Tarifs gelesen. Das dauert pro Abfrage etwa eine Minute länger und ist deshalb abgeschaltet.
TARIFE = "mit-tarife" in sys.argv
# Adresse der Ergebnisseite je Strecke: beim nächsten Mal wird sie direkt aufgerufen, ohne Suchmaske
URL_CACHE = DATEN / "bahn_de_adressen.json"
ALTER = "30"  # bei Auslandsstrecken fragt bahn.de vor der Angebotsseite nach dem Alter
OFFER = re.compile(r"^(.+?), 2\. Klasse, (\d+(?:,\d{1,2})?)\s*€", re.M)

# Cookie-Banner im Shadow DOM suchen
FIND_COOKIE_BUTTON = """
for (const el of document.querySelectorAll('*')) {
    const btn = el.shadowRoot && el.shadowRoot.querySelector('button.js-accept-all-cookies');
    if (btn) return btn;
}
return null;
"""

def accept_cookies(driver, seconds=10):
    try:
        btn = WebDriverWait(driver, seconds).until(lambda d: d.execute_script(FIND_COOKIE_BUTTON))
        btn.click()
        print("cookies: akzeptiert")
    except Exception:
        print("cookies: kein Banner erschienen")

def find_input(driver, name, seconds=10):
    """Eingabefeld suchen; nach einem Neuaufbau der Suchmaske bis zu `seconds` warten, bis es wieder da ist."""
    return WebDriverWait(driver, seconds).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, f'input[name="{name}"]'))
    )


def fill_station(driver, name, text, station):
    inp = find_input(driver, name)
    try:
        inp.click()
    except ElementClickInterceptedException:
        # Das Cookie-Banner ist erst jetzt erschienen und liegt über dem Feld
        accept_cookies(driver)
        time.sleep(1)
        inp.click()
    time.sleep(0.5)

    # Menschlicheres Tippen. bahn.de baut das Eingabefeld beim Tippen manchmal neu auf; dann ist das alte
    # Element "stale" und wird neu gesucht (der schon getippte Text steht im neuen Feld)
    for ch in text:
        for attempt in range(3):
            try:
                inp.send_keys(ch)
                break
            except StaleElementReferenceException:
                if attempt == 2:
                    raise
                time.sleep(0.5)
                inp = find_input(driver, name)
        time.sleep(0.08)

    time.sleep(1)
    option = (By.XPATH, f'//li[contains(@class, "db-web-select-list-item")][contains(., "{station}")]')
    for attempt in range(3):
        try:
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(option)).click()
            break
        except (StaleElementReferenceException, ElementClickInterceptedException) as e:
            # Die Vorschlagsliste wurde gerade neu aufgebaut oder das Cookie-Banner liegt darüber:
            # noch einmal suchen und klicken
            if attempt == 2:
                raise
            if isinstance(e, ElementClickInterceptedException):
                accept_cookies(driver, seconds=3)
            time.sleep(0.5)
    print(name, "->", driver.find_element(By.CSS_SELECTOR, f'input[name="{name}"]').get_attribute("value"))

def cached_urls():
    try:
        with open(URL_CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def remember_url(driver):
    """Merkt sich die Adresse der Ergebnisseite dieser Strecke (enthält die Bahnhofs-IDs)."""
    if "hd=" in driver.current_url and "access-error" not in driver.current_url:
        urls = cached_urls()
        urls[f"{START}|{ZIEL}"] = driver.current_url
        with open(URL_CACHE, "w", encoding="utf-8") as f:
            json.dump(urls, f, ensure_ascii=False, indent=1)


def blocked(driver):
    """Sperrseite von bahn.de: Adresse mit access-error oder Titel 'Fehler beim Zugriff'."""
    return "access-error" in driver.current_url or "Fehler beim Zugriff" in driver.title


def search_direct(driver, url):
    """Ruft die gemerkte Ergebnisseite mit neuem Datum auf. Gibt False zurück, wenn keine Preise kommen."""
    driver.get(re.sub(r"hd=[^&]*", f"hd={datum}T{uhrzeit}:00", url))
    accept_cookies(driver, seconds=5)
    wait_for_results(driver)
    return not blocked(driver) and "€" in driver.find_element(By.TAG_NAME, "body").text


def search_with_form(driver):
    driver.get("https://www.bahn.de")
    accept_cookies(driver)
    time.sleep(3)
    # Statt der Startseite kommt manchmal die Sperrseite; dann gibt es kein Suchfeld
    try:
        WebDriverWait(driver, 15).until(
            lambda d: blocked(d) or d.find_elements(By.CSS_SELECTOR, 'input[name="quickFinderBasic-von"]'))
    except Exception:
        print("Suchfeld nach 15 s nicht da. url:", driver.current_url, "title:", driver.title)
        raise
    if blocked(driver):
        return

    fill_station(driver, "quickFinderBasic-von", START, START)
    fill_station(driver, "quickFinderBasic-nach", ZIEL, ZIEL)

    time.sleep(1)
    driver.find_element(By.CSS_SELECTOR, "button.quick-finder-basic__search-btn--desktop").click()
    wait_for_results(driver)
    remember_url(driver)
    if datum and not blocked(driver):
        set_date(driver, datum, uhrzeit)


def wait_for_results(driver):
    # Warten, bis Preise geladen sind (oder die Suche abgelehnt wurde)
    try:
        WebDriverWait(driver, 30).until(
            lambda d: blocked(d) or "€" in d.find_element(By.TAG_NAME, "body").text
        )
    except Exception:
        print("Nach 30 s noch keine Preise auf der Seite.")


def set_date(driver, datum, uhrzeit):
    """Reisedatum und Uhrzeit stehen bei bahn.de als hd=... in der Adresse der Ergebnisseite."""
    url = driver.current_url
    if "hd=" not in url:
        raise RuntimeError("kein hd= in der Adresse: " + url)
    driver.get(re.sub(r"hd=[^&]*", f"hd={datum}T{uhrzeit}:00", url))
    driver.refresh()
    time.sleep(3)
    wait_for_results(driver)


def next_buttons(driver):
    xpath = "//button[normalize-space()='Weiter']"
    return [b for b in driver.find_elements(By.XPATH, xpath) if b.is_displayed()]


def age_field(driver):
    fields = [f for f in driver.find_elements(By.CSS_SELECTOR, 'input[name="reisender01"]') if f.is_displayed()]
    return fields[0] if fields else None


def read_offers(driver):
    """Öffnet zu jeder Verbindung mit Preis die Angebotsseite und liest die Tarife der 2. Klasse.
    Ergebnis: {(abfahrt, ankunft): [(tarif, preis), ...]}"""
    offers = {}
    for i in range(len(next_buttons(driver))):
        buttons = next_buttons(driver)
        if i >= len(buttons):
            break
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", buttons[i])
        time.sleep(0.5)
        buttons[i].click()
        WebDriverWait(driver, 20).until(lambda d: "angebotsauswahl" in d.current_url or age_field(d))
        if "angebotsauswahl" not in driver.current_url:
            field = age_field(driver)
            field.click()
            field.send_keys(ALTER)
            driver.find_element(By.XPATH, "//button[normalize-space()='Übernehmen']").click()
            WebDriverWait(driver, 20).until(lambda d: "angebotsauswahl" in d.current_url)
        try:
            WebDriverWait(driver, 15).until(lambda d: "2. Klasse" in d.find_element(By.TAG_NAME, "body").text)
        except Exception:
            pass
        text = driver.find_element(By.TAG_NAME, "body").text
        times = re.search(r"(\d{1,2}:\d{2}) – (\d{1,2}:\d{2})", text)
        if times:
            offers[(times.group(1).zfill(5), times.group(2).zfill(5))] = OFFER.findall(text)
        driver.back()
        WebDriverWait(driver, 20).until(lambda d: "angebotsauswahl" not in d.current_url and next_buttons(d))
        time.sleep(1)
    return offers


def with_offers(rows, offers):
    """Trägt bei jeder Verbindung den billigsten Tarif der Angebotsseite mit Namen und Preis ein."""
    result = []
    for r in rows:
        found = offers.get((r["abfahrt"], r["ankunft"]))
        if not found:
            result.append(r)
            continue
        tarif, preis = min(found, key=lambda offer: float(offer[1].replace(",", ".")))
        preis = f"{float(preis.replace(',', '.')):.2f}".replace(".", ",")
        result.append({**r, "tarif": tarif.strip(), "preis": preis, "bemerkung": ""})
    return result


# Browser konfigurieren
options = uc.ChromeOptions()
if headless:
    options.add_argument("--headless=new")
options.add_argument("--window-size=1280,800")
hide_window(options)
options.add_argument("--lang=de-DE")

# Starten
driver = start_uc(options, "db")

try:
    known = cached_urls().get(f"{START}|{ZIEL}")
    if known and datum and search_direct(driver, known):
        print("Suche: direkt über die gemerkte Adresse")
    elif blocked(driver):
        # Schon die gemerkte Adresse wurde abgelehnt: nicht noch die Startseite aufrufen
        print("Suche: gemerkte Adresse abgelehnt")
    else:
        try:
            search_with_form(driver)
        except Exception as e:
            # Festhalten, was die Seite gerade zeigt; landet sie auf der Sperrseite, ist es eine Ablehnung
            print("Suchmaske fehlgeschlagen:", type(e).__name__)
            print("url:", driver.current_url)
            print("title:", driver.title)
            driver.save_screenshot(out.replace(".png", "_fehler.png"))
            if not blocked(driver):
                raise
        print("Suche: über die Suchmaske")

    print("url:", driver.current_url)
    print("title:", driver.title)

    if blocked(driver):
        print("BLOCKIERT: bahn.de hat die Suche abgelehnt.")
    else:
        body = driver.find_element(By.TAG_NAME, "body").text
        with open(SEITEN / "db_ergebnisseite.txt", "w", encoding="utf-8") as f:
            f.write(body)
        keep_text(body)
        rows = parse(body)
        print("Verbindungen gefunden:", len(rows))
        for r in rows:
            print("  ", r["abfahrt"], "-", r["ankunft"], r["preis"] or r["bemerkung"])
        reise_datum = guess_date(body) or date.today().isoformat()
        if datum and reise_datum != datum:
            print(f"NICHT GESPEICHERT: Seite zeigt {reise_datum} statt {datum}.")
        elif rows:
            if TARIFE:
                try:
                    offers = read_offers(driver)
                    rows = with_offers(rows, offers)
                    print("Tarife gelesen für", len(offers), "Verbindung(en):")
                    for r in rows:
                        print("  ", r["abfahrt"], "-", r["ankunft"], r["tarif"] or "-", r["preis"] or r["bemerkung"])
                except Exception as e:
                    print("Tarife lesen fehlgeschlagen:", type(e).__name__, "- gespeichert wird der 'ab'-Preis.")
            append_rows(rows, reise_datum, START, ZIEL, quelle="bahn.de")

    driver.save_screenshot(out)
    if VISIBLE and sys.stdin.isatty():
        input("Drücke Enter, um den Browser zu schließen...")
finally:
    driver.quit()