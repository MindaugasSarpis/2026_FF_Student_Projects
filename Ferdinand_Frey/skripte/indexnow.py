"""Meldet alle Seiten aus webseite/sitemap.xml per IndexNow (api.indexnow.org gibt sie an Bing, Yandex, Seznam,
Naver u. a. weiter; Google macht nicht mit). Aufruf nach dem Hochladen, z. B. am Ende von taeglich.py.
Der Schlüssel steht in INDEXNOW in webseite.py und liegt als <schlüssel>.txt auf der Seite."""
import json
import re
import sys
import urllib.error
import urllib.request

from pfade import WEBSEITE
from webseite import ADRESSE, INDEXNOW

if not INDEXNOW:
    print("IndexNow ist aus (INDEXNOW = \"\" in webseite.py).")
    sys.exit(0)

adressen = re.findall(r"<loc>([^<]+)</loc>", (WEBSEITE / "sitemap.xml").read_text(encoding="utf-8"))
daten = {"host": ADRESSE.split("://")[1], "key": INDEXNOW, "keyLocation": f"{ADRESSE}/{INDEXNOW}.txt",
         "urlList": adressen}
anfrage = urllib.request.Request("https://api.indexnow.org/indexnow", data=json.dumps(daten).encode("utf-8"),
                                 headers={"Content-Type": "application/json; charset=utf-8"})
try:
    with urllib.request.urlopen(anfrage, timeout=60) as antwort:
        # 200 = angenommen, 202 = angenommen, Schlüssel wird noch geprüft
        print(f"IndexNow: {len(adressen)} Seiten gemeldet (Antwort {antwort.status}).")
except urllib.error.HTTPError as e:
    # 403 = Schlüssel ungültig/nicht gefunden, 422 = Adressen passen nicht zur Domain, 429 = zu viele Meldungen
    print(f"IndexNow fehlgeschlagen: Antwort {e.code} {e.reason}")
    sys.exit(1)
except OSError as e:
    print(f"IndexNow fehlgeschlagen: {e}")
    sys.exit(1)
