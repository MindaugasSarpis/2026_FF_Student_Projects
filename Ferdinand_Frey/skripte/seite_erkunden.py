"""Öffnet die Seite einer Bahn und speichert Suchmaske und Ergebnisliste, damit daraus ein
Suchskript gebaut werden kann. Gesucht wird von Hand im geöffneten Fenster.

    python skripte/seite_erkunden.py trenitalia https://www.trenitalia.com/de.html
"""
import sys
from pfade import SEITEN
from selenium_basis import save_page, start_driver

name, url = sys.argv[1], sys.argv[2]
driver = start_driver()

try:
    driver.get(url)
    input("Cookie-Banner wegklicken. Wenn die Suchmaske zu sehen ist: Enter drücken...")
    save_page(driver, f"{name}_suchseite")

    input("Jetzt Start und Ziel eintippen, aber noch NICHT auswählen (Vorschlagsliste offen lassen): Enter...")
    save_page(driver, f"{name}_vorschlaege")

    input("Jetzt die Suche abschicken. Wenn die Ergebnisliste mit Preisen zu sehen ist: Enter...")
    print("url:", driver.current_url)
    save_page(driver, f"{name}_ergebnisseite")
    driver.save_screenshot(str(SEITEN / f"{name}_ergebnisseite.png"))
finally:
    driver.quit()
