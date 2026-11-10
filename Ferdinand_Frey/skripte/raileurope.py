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
out, headless, datum, uhrzeit = read_args("raileurope.png")

# Strecke: Vorgabe hier, oder von alle_strecken.py gesetzt
START = os.environ.get(
    "RAIL_START", "Paris"
)  # Rail Europe accepts city or major station names
ZIEL = os.environ.get("RAIL_ZIEL", "London")

# Adresse der Ergebnisseite je Strecke cachen
URL_CACHE = DATEN / "raileurope_adressen.json"
OFFER = re.compile(r"^(.+?),\s*(\d+(?:,\d{1,2})?)\s*€", re.M)


def accept_cookies(driver, seconds=10):
    """Akzeptiert das Cookie-Banner von Rail Europe (oft OneTrust oder ähnlich)."""
    try:
        btn_xpath = (
            "//button[contains(@id, 'accept') or contains(text(), 'Accept') or contains(text(), 'Alle akzeptieren')]"
        )
        btn = WebDriverWait(driver, seconds).until(
            EC.element_to_be_clickable((By.XPATH, btn_xpath))
        )
        btn.click()
        print("cookies: akzeptiert")
    except Exception:
        print("cookies: kein Banner erschienen oder bereits akzeptiert")


def find_input(driver, selector, seconds=10):
    return WebDriverWait(driver, seconds).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )


def fill_station(driver, selector, text, station_keyword):
    inp = find_input(driver, selector)
    try:
        inp.click()
    except ElementClickInterceptedException:
        accept_cookies(driver)
        time.sleep(1)
        inp.click()
    time.sleep(0.5)

    # Text eingeben
    for ch in text:
        for attempt in range(3):
            try:
                inp.send_keys(ch)
                break
            except StaleElementReferenceException:
                if attempt == 2:
                    raise
                time.sleep(0.5)
                inp = find_input(driver, selector)
        time.sleep(0.08)

    time.sleep(1.5)
    # Auswahlelement aus der Dropdown-Liste anklicken
    option = (
        By.XPATH,
        f'//li[contains(@class, "suggestion") or contains(@role, "option")][contains(., "{station_keyword}")]',
    )
    for attempt in range(3):
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(option)
            ).click()
            break
        except (
            StaleElementReferenceException,
            ElementClickInterceptedException,
        ) as e:
            if attempt == 2:
                raise
            if isinstance(e, ElementClickInterceptedException):
                accept_cookies(driver, seconds=3)
            time.sleep(0.5)
    print(
        selector,
        "->",
        driver.find_element(By.CSS_SELECTOR, selector).get_attribute("value"),
    )


def cached_urls():
    try:
        with open(URL_CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def remember_url(driver):
    if "results" in driver.current_url and "access-error" not in driver.current_url:
        urls = cached_urls()
        urls[f"{START}|{ZIEL}"] = driver.current_url
        with open(URL_CACHE, "w", encoding="utf-8") as f:
            json.dump(urls, f, ensure_ascii=False, indent=1)


def blocked(driver):
    """Sperrseite oder DataDome-Captcha ("Nach rechts schieben"), das Rail Europe schon beim ersten
    Aufruf zeigt (Test 21.10.2026, auch mit undetected_chromedriver). Wird nicht umgangen."""
    return (
        "access-error" in driver.current_url
        or "Access Denied" in driver.title
        or "Robot" in driver.title
        or "captcha-delivery.com" in driver.page_source
    )


def search_direct(driver, url):
    """Ruft die gespeicherte Ergebnisseite auf."""
    driver.get(url)
    accept_cookies(driver, seconds=5)
    wait_for_results(driver)
    return not blocked(driver) and "€" in driver.find_element(By.TAG_NAME, "body").text


def search_with_form(driver):
    driver.get("https://www.raileurope.com")
    accept_cookies(driver)
    time.sleep(3)

    try:
        # Passen Sie die Selektoren ggf. an die aktuellen Input-Felder von Rail Europe an
        fill_station(
            driver, 'input[data-qa="origin-input"], input[name="origin"]', START, START
        )
        fill_station(
            driver,
            'input[data-qa="destination-input"], input[name="destination"]',
            ZIEL,
            ZIEL,
        )
    except Exception:
        print(
            "Suchfeld nicht gefunden. url:",
            driver.current_url,
            "title:",
            driver.title,
        )
        raise

    time.sleep(1)
    # Such-Button auslösen
    search_btn = driver.find_element(
        By.CSS_SELECTOR,
        'button[data-qa="search-submit"], button[type="submit"]',
    )
    search_btn.click()
    wait_for_results(driver)
    remember_url(driver)


def wait_for_results(driver):
    try:
        WebDriverWait(driver, 30).until(
            lambda d: blocked(d)
            or "€" in d.find_element(By.TAG_NAME, "body").text
        )
    except Exception:
        print("Nach 30 s noch keine Preise auf der Rail Europe Seite.")


# Browser konfigurieren
options = uc.ChromeOptions()
if headless:
    options.add_argument("--headless=new")
options.add_argument("--window-size=1280,800")
hide_window(options)
options.add_argument("--lang=de-DE")

# Starten
driver = start_uc(options, "raileurope")

try:
    known = cached_urls().get(f"{START}|{ZIEL}")
    if known and datum and search_direct(driver, known):
        print("Suche: direkt über die gemerkte Adresse")
    elif blocked(driver):
        print("Suche: gemerkte Adresse abgelehnt")
    else:
        try:
            search_with_form(driver)
        except Exception as e:
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
        print("BLOCKIERT: Rail Europe hat die Suche abgelehnt (Bot-Schutz).")
    else:
        body = driver.find_element(By.TAG_NAME, "body").text
        with open(SEITEN / "raileurope_ergebnisseite.txt", "w", encoding="utf-8") as f:
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
            append_rows(rows, reise_datum, START, ZIEL, quelle="raileurope.com")

    driver.save_screenshot(out)
    if VISIBLE and sys.stdin.isatty():
        input("Drücke Enter, um den Browser zu schließen...")
finally:
    driver.quit()