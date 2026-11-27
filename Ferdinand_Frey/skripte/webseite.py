"""Erzeugt aus daten/vergleich.csv eine statische Website im Ordner webseite/, auf Deutsch (de/) und Englisch (en/):
Startseite, eine Seite je Strecke, Methodik, Impressum, Feedback-Formular, dazu robots.txt und sitemap.xml.
Vorher skripte/auswertung.py laufen lassen, damit vergleich.csv aktuell ist.

Aufruf: python skripte/webseite.py [vergleich.csv] [--adresse https://meine-domain.eu] [--goatcounter code] [--affiliate bahn.de=https://...]"""
import collections
import csv
import hashlib
import html
import ast
import json
import math
import re
import shutil
import statistics
import sys
import unicodedata
from datetime import date, timedelta
from urllib.parse import quote
from pathlib import Path

from pfade import BILLIGSTE_FAHRT, DATEN, LOGS, SKRIPTE, STRECKEN, VERGLEICH, WEBSEITE

ADRESSE = "https://sametrain.eu"  # Domain (bei INWX, DNS über Cloudflare); für Sitemap und Sprachverknüpfung
SPRACHEN = ("de", "en")
# Anbieter für das Impressum: Name, Straße, Ort, E-Mail
ANBIETER = ("Ferdinand Frey", "", "", "")  # address and e-mail removed here, see the imprint on sametrain.eu
GOATCOUNTER_ANBIETER = {  # Betreiber laut goatcounter.com/help/privacy (Stand 8.6.2025), für die Datenschutzerklärung
    "de": "Martin Tournoij, Irland (GoatCounter.com); die Daten liegen auf Servern der Hetzner Online GmbH in Finnland "
          "und Deutschland",
    "en": "Martin Tournoij, Ireland (GoatCounter.com); the data is stored on servers of Hetzner Online GmbH in Finland "
          "and Germany",
}
GOATCOUNTER = "sametrain"  # Besucherzählung: Code bei goatcounter.com (Statistik: sametrain.goatcounter.com); "" = aus
# IndexNow (Bing, Yandex u. a. über neue Seiten informieren): öffentlicher Schlüssel, liegt als <schlüssel>.txt
# auf der Seite; gemeldet wird von skripte/indexnow.py nach dem Hochladen. "" = aus
INDEXNOW = "7ce26c705125de8ebb986f3147cc5b40"
# Provisionslinks (Affiliate): Verkäufer -> Link, z. B. Awin-Deeplink für bahn.de; leer = normale Links.
# Auch per Aufruf: --affiliate bahn.de=https://www.awin1.com/cread.php?... Gekennzeichnet mit *, rel="sponsored"
AFFILIATE = {}
# Datensatz bei Zenodo (Concept-DOI, gilt für alle Versionen) und GitHub, siehe veroeffentlichung/anleitung.md
DATENSATZ_DOI = "10.5281/zenodo.23669337"
DATENSATZ_GITHUB = "https://github.com/UrzasMine/same-train-different-price"
SPERRFRIST_TAGE = 7  # die Rohdaten-CSV enthält nur Abfragen, die mindestens so alt sind; aktuelle Preise nur auf der Seite
# Neue Gestaltung vom 21.10.2026: jede Änderung einzeln abschaltbar. False = wieder wie vorher.
# (Komplette alte Version: alte_dateien/webseite_2026-10-21_*_vor_ui_umbau.py)
UI = {
    "frisch": True,            # Browser laden HTML und CSS immer neu, sobald sich etwas geändert hat (_headers, stil.css?v=)
    "kopf_oben": True,         # Startseite: Überschrift = Erkenntnis, drei Kennzahlen, kurzer Projektsatz
    "suche_oben": True,        # großes Suchfeld oben; findet beide Richtungen, deutsche/englische Namen, ohne Akzente
    "zeilen_satz": True,       # je Strecke ein Satz, was dort passiert (z. B. „ÖBB bei 83 % der Züge billiger als DB“)
    "spart": True,             # „spart bis X €“ unter dem Ab-Preis
    "wenig_daten": True,       # Strecken mit weniger als 10 Zügen eingeklappt unter „Weitere Strecken“
    "filter": True,            # Filter-Knöpfe über der Liste
    "kopf_fest": True,         # Kopfzeile bleibt beim Scrollen oben, Sprachwahl als Umschalter
    "zuege_einklappen": True,  # Streckenseite: je Abfragetag nur die 5 Züge mit dem größten Unterschied, Rest aufklappbar
    "verkaeufer_balken": True,  # Streckenseite: ein geteilter Balken je Verkäufer statt drei Spalten allein/gleich/teurer
    "verkaeufer_wenig": True,   # Streckenseite: Verkäufer mit weniger als WENIG_VERKAEUFER_ZUEGE Zügen nur unter der Tabelle
    "gestrichen_kurz": True,    # Streckenseite: gestrichene Verkäufer mit kleinem Schild, Erklärung einmal unter der Tabelle
    "suche_von_nach": True,     # Startseite: Suche mit zwei Feldern „Von“/„Nach“ und Tausch-Knopf (wie in der DB-App)
}
WENIG_VERKAEUFER_ZUEGE = 5
# Offizielle SNCF-Preisspanne (Open Data, skripte/sncf_tarife_holen.py) auf Strecken, auf denen SNCF Connect fehlt.
# Der Datensatz hat nur Inlandsverbindungen; Bahnhöfe so geschrieben wie dort
SNCF_TARIFE, SNCF_TARIFE_STAND = DATEN / "sncf_tarife.csv", DATEN / "sncf_tarife_stand.txt"
SNCF_STRECKEN = {"Paris – Lyon": ("PARIS GARE DE LYON", "LYON PART DIEU"),
                 "Lyon – Paris": ("LYON PART DIEU", "PARIS GARE DE LYON")}
SNCF_ZUGARTEN = {"TGV INOUI": "TGV inOui", "OUIGO": "OUIGO"}
WENIG_ZUEGE = 10  # ab so vielen verglichenen Zügen steht eine Strecke in der Hauptliste

# Such- und Nutzer-Abrufe von KI-Diensten und Suchmaschinen ausdrücklich erlaubt (robots.txt)
CRAWLER_ERLAUBT = ("OAI-SearchBot", "ChatGPT-User", "Claude-SearchBot", "Claude-User", "PerplexityBot",
                   "Perplexity-User", "Googlebot", "Bingbot")

# Anzeigename und Buchungsseite je Verkäufer
VERKAEUFER = {
    "bahn.de": ("bahn.de (DB)", "https://www.bahn.de"),
    "oebb.at": ("ÖBB", "https://www.oebb.at"),
    "sbb.ch": ("SBB", "https://www.sbb.ch"),
    "cd.cz": ("České dráhy (ČD)", "https://www.cd.cz/en/"),
    "intercity.pl": ("PKP Intercity", "https://www.intercity.pl"),
    "mav.hu": ("MÁV", "https://jegy.mav.hu"),
    "ltglink.lt": ("LTG Link", "https://ltglink.lt"),
    "elron.ee": ("Elron", "https://elron.ee"),
    "trenitalia.com": ("Trenitalia", "https://www.lefrecce.it"),
    "eurostar.com": ("Eurostar", "https://www.eurostar.com"),
    "b-europe.com": ("SNCB International", "https://www.b-europe.com"),
    "ouigo.com": ("OUIGO", "https://www.ouigo.com"),
    "nsinternational.com": ("NS International", "https://www.nsinternational.com/en"),
    "regiojet.com": ("RegioJet", "https://regiojet.com"),
    "cfrcalatori.ro": ("CFR Călători", "https://bileteinternationale.cfrcalatori.ro/en"),
    "omio.com": ("Omio", "https://www.omio.com"),
}

# Städtenamen in der Streckenliste sind deutsch; englische Namen, wo sie abweichen
STADT_EN = {"Brüssel": "Brussels", "Bukarest": "Bucharest", "Danzig": "Gdansk", "Hannover": "Hanover", "Köln": "Cologne", "Krakau": "Krakow", "Mailand": "Milan",
            "München": "Munich", "Nürnberg": "Nuremberg", "Prag": "Prague", "Rom": "Rome", "Venedig": "Venice",
            "Warschau": "Warsaw", "Wien": "Vienna", "Zürich": "Zurich"}

MONATE_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Alle Texte der Seite je Sprache; neue Texte immer in beiden Sprachen anlegen
T = {
    "de": {
        "titel": "Zugpreis-Vergleich",
        "ordner": "strecken",
        "nav_alle": "Alle Strecken", "nav_methodik": "So wird gemessen", "nav_ergebnisse": "Ergebnisse",
        "h1_befund": "Meist ist die Bahn des eigenen Landes am billigsten. Aber nicht immer.",
        "kz_zuege": "Züge verglichen", "kz_verk": "Verkäufer", "kz_strecken": "Strecken", "kz_bis": "bis {e}", "kz_spanne": "Preisunterschied für denselben Zug", "kz_fremd": "der Züge: ausländische Bahn billiger",
        "kz_vermittler": "{v} im Median teurer", "satz_kurz": "Ein Studentenprojekt, entstanden aus Neugier: Seit "
        "Oktober 2026 frage ich jeden Tag die Preise derselben Züge bei vielen Bahn-Verkäufern ab.",
        "suche_gross": "Strecke suchen, z. B. München Wien",
        "vn_von": "Von", "vn_nach": "Nach", "vn_von_ph": "z. B. München", "vn_nach_ph": "z. B. Wien",
        "vn_tauschen": "Start und Ziel tauschen", "vn_suche": "Strecke suchen",
        "vn_gegen": "In dieser Richtung nicht gemessen, aber in der Gegenrichtung:",
        "vn_umstieg": "Keine direkte Strecke gemessen, aber mit Umstieg aus gemessenen Strecken:",
        "vn_ueber": "über {s}", "vn_zusammen": "zusammen ab {p}",
        "vn_umst_hinweis": "Getrennte Fahrten: Jeder Preis gilt nur für seine Teilstrecke, oft an verschiedenen Tagen "
                           "oder Zügen gemessen. Einen Anschluss garantiert das nicht.",
        "f_alle": "Alle", "f_fremd": "Ausländische Bahn billiger", "f_gross": "Großer Unterschied",
        "f_gleich": "Alle gleich teuer", "weitere": "Weitere Strecken mit noch wenigen Daten ({n})",
        "zs_fremd": "{v} bei {p} % der Züge billiger als {h}", "zs_gleich": "alle Verkäufer gleich teuer",
        "zs_faktor": "bei {v} im Median {f}-mal so teuer", "zs_prozent": "bei {v} im Median {p} teurer",
        "zs_kaum": "kaum Preisunterschiede", "zs_nur": "andere Verkäufer waren nie billiger, nur noch {v} wird abgefragt", "zs_zuege": "{n} Züge", "spart": "spart bis {e}",
        "alle_zeigen": "Alle {n} Züge anzeigen", "weniger_zeigen": "Weniger anzeigen",
        "datei_ergebnisse": "ergebnisse",
        "titel_ergebnisse": "Ergebnisse: Wo ist dasselbe Zugticket am billigsten?",
        "beschr_ergebnisse": "Die wichtigsten Zahlen aus {n} täglich verglichenen Zügen auf {r} Strecken in Europa: "
                             "welcher Verkäufer am billigsten ist, wann eine ausländische Bahn günstiger ist und wo "
                             "derselbe Zug ein Vielfaches kostet.",
        "stand_ergebnisse": "{n} verglichene Züge auf {r} Strecken · {v} Verkäufer · Abfragen vom {von} bis {bis}",
        "h2_kurz": "Das Wichtigste in Kürze",
        "befund_strecken": "Auf {k} von {r} Strecken war am häufigsten eine Bahn des Start- oder Ziellandes am billigsten.",
        "befund_gleich": "Auf {k} von {r} Strecken verlangten alle verglichenen Verkäufer für denselben Zug immer "
                         "denselben Preis.",
        "befund_max": "Der größte Unterschied: Auf {s} kostete derselbe Zug bei {teuer} {f}-mal so viel wie bei {billig} "
                      "({pt} statt {pb}).",
        "h2_verkaeufer_alle": "Alle Verkäufer im Vergleich",
        "sp_strecken": "Strecken", "sp_anteil": "Anteil",
        "erkl_verkaeufer_alle": "Über alle Strecken: „am billigsten“ = niedrigster Preis für denselben Zug (auch gleich "
                                "billig wie ein anderer Verkäufer). „Wenn teurer“: um wie viel der Verkäufer im Median "
                                "über dem billigsten Preis lag, bei den Zügen, bei denen er nicht am billigsten war. "
                                "Wenige Züge = noch unsichere Zahlen.",
        "sp_wenn_teurer": "wenn teurer: im Median",
        "h2_max": "Die größten Preisunterschiede für denselben Zug",
        "sp_billig_bei": "am billigsten", "sp_teuer_bei": "am teuersten", "sp_faktor": "Faktor",
        "erkl_max": "Je Strecke der Zug mit dem größten Unterschied zwischen billigstem und teuerstem Verkäufer.",
        "h2_fremd": "Wo eine ausländische Bahn billiger war",
        "fremd_satz": "Gezählt sind Züge, bei denen eine Bahn ohne eigenen Start- oder Zielbahnhof billiger war als alle "
                      "Bahnen des Start- und Ziellandes.",
        "fremd_keine": "Bisher auf keiner Strecke.", "sp_billiger_bei": "billiger bei", "sp_zuege_n": "Züge",
        "h2_zitieren": "Zitieren und Daten",
        "zitieren": "Quelle: „Zugpreis-Vergleich (sametrain.eu), Stand {d}“. Die Zahlen dürfen frei verwendet werden "
                    "(CC BY 4.0), mit Link auf diese Seite. Die Rohdaten gibt es als <a href=\"../daten/vergleich.csv\">"
                    "CSV-Datei</a> (Abfragen ab 7 Tage alt), zitierfähig mit DOI bei <a href=\"https://doi.org/10.5281/zenodo.23669337\">"
                    "Zenodo</a>; wie gemessen wird, steht unter "
                    "<a href=\"methodik.html\">So wird gemessen</a>.",
        "vorsicht": "Die Datenbasis wächst jeden Tag. Bei Strecken mit wenigen Zügen sind die Zahlen noch unsicher.",
        "zu_ergebnissen": "Alle Ergebnisse auf einen Blick",
        "fuss": "Eigene Messungen: Preise für 1 Erwachsenen, 2. Klasse, ohne Ermäßigung, abgefragt direkt auf den "
                "Seiten der Verkäufer. Angaben ohne Gewähr.",
        "methodik": "Methodik", "rohdaten": "Rohdaten (CSV, ab 7 Tage alt, CC BY 4.0)", "impressum": "Impressum", "datenschutz": "Datenschutz",
        "beschr_datenschutz": "Datenschutzerklärung des Zugpreis-Vergleichs.",
        "aktuell": "Täglich aktualisiert · Stand: {d}",
        "rolle": {"Start/Ziel": "Bahn eines Start- oder Ziellandes", "Durchgang": "Bahn eines Durchfahrtslandes",
                  "kein Bezug": "Bahn ohne Bezug zur Strecke",
                  "Vermittler": "Vermittler (verkauft Tickets vieler Bahnen)"},
        "satz_gleich": "Für {s} verlangten alle verglichenen Verkäufer für denselben Zug denselben Preis (typisch {p}).",
        "satz": "Für {s} war {v} bei {b} von {n} verglichenen Zügen der billigste Verkäufer für denselben Zug "
                "(typischer Preis {p}).",
        # Billigste Fahrt über alle Züge, auch solche, die nur ein Verkäufer anbietet (daten/billigste_fahrt.csv)
        "gesamt": "Billigste Fahrt insgesamt (alle Züge): {v} an {k} von {n} Reisetagen, ab {p}.",
        "gesamt_titel": "Billigste Fahrt insgesamt",
        "gesamt_info": "{v} an {k} von {n} Reisetagen · alle Züge und Verkäufer, je Reisetag die billigste Fahrt",
        "gesamt_eigene": "{v} fährt eigene Züge, die die anderen Verkäufer nicht anbieten. Im Vergleich derselben "
                         "Züge weiter unten kommt {v} deshalb nicht vor.",
        "satz_teuer": " Derselbe Zug kostete bei {v} typischerweise {f}-mal so viel.",
        "satz_teuer_p": " Bei {v} kostete derselbe Zug im Median {p} mehr ({n} gemeinsame Züge).",
        "satz_fehlt": " Mit {v} gab es bisher keinen Vergleich am selben Zug.",
        "fehlt_kurz": "noch ohne Vergleich mit {v}",
        "sp_gegen": "gegenüber {v}", "kein_gemeinsam": "kein gemeinsamer Zug", "gegen_wert": "{p} · {n} Züge",
        "h2_vorlauf": "Wann buchen? Preise nach Vorlauf",
        "vorlauf_stufen": ("kurzfristig (0–3 Tage)", "1–2 Wochen vorher", "2–4 Wochen vorher", "mehr als 4 Wochen vorher"),
        "sp_vorlauf": "Abgefragt", "sp_anzahl": "Züge", "sp_billigster_preis": "billigster Preis (Median)",
        "vorlauf_satz": "Billigstes Ticket für {s} im Median: {liste}.",
        "vorlauf_zu_wenig": "Für einen Vergleich nach Vorlauf gibt es auf dieser Strecke noch zu wenige Daten. Jeder "
                            "Reisetag wird 1, 7, 21 und 42 Tage vorher abgefragt.",
        "erkl_vorlauf": "Je Zug zählt der niedrigste Preis aller Verkäufer. Die Stufen enthalten verschiedene Reisetage "
                        "und Züge; das zeigt eine Tendenz, keine Garantie.",
        "buchen_bester": "meist am billigsten",
        "suche": "Stadt suchen, z. B. Wien", "suche_leer": "Keine Strecke gefunden.",
        "h2_faq": "Häufige Fragen",
        "faq_heim_f": "Ist die Bahn des eigenen Landes immer am billigsten?",
        "faq_heim_a": "Meistens. Bei {p} % der verglichenen Züge ({k} von {n}) war eine Bahn des Start- oder Ziellandes "
                      "am billigsten oder gleich billig wie der billigste andere Verkäufer.",
        "faq_fremd_f": "Lohnt es sich, das Ticket bei einer ausländischen Bahn zu kaufen?",
        "faq_fremd_ja": "Manchmal. Bei {k} von {n} Zügen ({p} %) war eine andere Bahn billiger als die Bahnen des Start- "
                        "und Ziellandes, am häufigsten auf den Strecken {s}.",
        "faq_fremd_nein": "Bisher nicht: Bei keinem der {n} verglichenen Züge war eine andere Bahn billiger als die "
                          "Bahnen des Start- und Ziellandes.",
        "faq_fremd_teuer": " Bahnen ohne Bezug zur Strecke verlangten im Median das {f}-Fache des billigsten Preises.",
        "faq_vermittler_f": "Sind Vermittler wie {v} teurer?",
        "faq_vermittler_a": "{start} {v} war bei {b} von {n} verglichenen Zügen am billigsten und kostete im Median {p} "
                            "mehr als der billigste Verkäufer. Eingerechnet ist eine geschätzte Servicegebühr von etwa "
                            "6,5 %, mindestens 2 €.",
        "meist_ja": "Meist ja, Vermittler sind teurer.", "nicht_unbedingt": "Nicht unbedingt, Vermittler sind nicht immer teurer.",
        "faq_wann_f": "Wann sollte man das Zugticket kaufen?",
        "faq_wann_a": "{start} Auf {r} Strecken mit Daten zu beiden Zeitpunkten war das billigste Ticket 1–2 Wochen "
                      "vor der Fahrt im Median {p} als mehr als 4 Wochen vorher.",
        "frueh": "Möglichst früh.", "egal": "Bisher macht der Zeitpunkt wenig Unterschied.",
        "teurer": "{p} % teurer", "billiger": "{p} % billiger",
        "faq_wann_leer": "Dazu sammle ich noch Daten: Jeder Reisetag wird 1, 7, 21 und 42 Tage vorher abgefragt.",
        "faq_aktuell_f": "Wie aktuell sind die Preise?",
        "faq_aktuell_a": "Die Preise werden täglich neu abgefragt, letzter Stand: {d}. Sie ändern sich laufend; vor dem "
                         "Buchen bitte beim Verkäufer prüfen.",
        "h1_strecke": "{s} mit dem Zug: wo ist das Ticket am billigsten?",
        "titel_strecke": "{s} mit dem Zug: billigster Verkäufer",
        "stand_strecke": "{n} verglichene Züge · Abfragen vom {von} bis {bis}",
        "h2_verkaeufer": "Verkäufer im Vergleich",
        "sp_verkaeufer": "Verkäufer", "sp_billigst": "am billigsten", "sp_typisch": "typischer Preis",
        "sp_aufschlag": "Aufschlag zum Billigsten", "von": "{b} von {n}",
        "sp_allein": "allein am billigsten", "sp_gleich": "gleich billig", "sp_teurer": "teurer",
        "sp_wie_oft_billig": "Wie oft am billigsten", "stapel_text": "{a} von {n}", "stapel_gleich": " · {g} gleich billig",
        "erkl_verkaeufer2": "Gezählt wird je Zug, den der Verkäufer im Angebot hatte: „allein am billigsten“ = niemand "
                            "war billiger oder gleich billig; „gleich billig“ = derselbe niedrigste Preis wie mindestens "
                            "ein anderer Verkäufer; „teurer“ = ein anderer Verkäufer war billiger. „Gegenüber {v}“: "
                            "mittlerer Preisunterschied (Median) bei den Zügen, die beide im Angebot hatten. Fremdwährungen "
                            "sind zum EZB-Kurs des Abfragetags umgerechnet.",
        "satz_gleichauf": "Für {s} verlangten {v} für dieselben Züge fast immer denselben Preis ({g} von {n} gemeinsamen "
                          "Zügen gleich teuer, typisch {p}).",
        "satz_allein": "Für {s} war {v} bei {a} von {n} Zügen allein der billigste Verkäufer für denselben Zug und bei "
                       "{g} gleich billig wie ein anderer Verkäufer (typischer Preis {p}).",
        "und": " und ",
        "erkl_verkaeufer": "„Am billigsten“: wie oft der Verkäufer für denselben Zug den niedrigsten Preis hatte. "
                           "„Gegenüber {v}“: mittlerer Preisunterschied (Median) bei den Zügen, die beide im Angebot "
                           "hatten. „Aufschlag zum Billigsten“: Median über alle Züge des Verkäufers. Fremdwährungen sind "
                           "zum EZB-Kurs des Abfragetags umgerechnet.",
        "h2_sncf": "SNCF-Preise zum Vergleich",
        "sncf_text": "SNCF Connect lässt sich nicht automatisch abfragen, deshalb fehlen oben die Tagespreise von "
                     "TGV inOui. SNCF veröffentlicht aber, in welcher Spanne der volle Tarif für diese Verbindung "
                     "liegt (2. Klasse, ohne Ermäßigung):",
        "sncf_median": "Zum Vergleich: Der billigste hier gemessene Preis je Zug lag im Median bei {m}.",
        "sncf_buchen": "TGV inOui und OUIGO kann man z. B. bei {l} buchen, einem kleinen französischen Verkäufer "
                       "ohne Zusatzangebote. Dessen Preise werden hier nicht gemessen; kein Provisionslink.",
        "sncf_quelle": "Quelle: SNCF Voyageurs, „Tarifs TGV INOUI et OUIGO“ (SNCF Open Data, Lizenz ODbL), Stand {d}. "
                       "Die Spanne gilt für alle Züge und Reisetage; welcher Preis gilt, hängt von Nachfrage und "
                       "Buchungszeitpunkt ab. Für die Frecciarossa-Züge von Trenitalia gilt sie nicht.",
        "h2_zuege": "Alle gemessenen Züge", "sp_reisetag": "Vorlauf", "sp_zug": "Zug", "tage_vorher": "{n} Tage vorher", "tag_vorher": "1 Tag vorher", "am_reisetag": "am Reisetag",
        "reise_abfrage": "Fahrt {r} · abgefragt {a}",
        "h3_abfrage": "Abgefragt am {d}",
        "luecke_kurz": "zuletzt Preise am {d}",
        "luecke_erkl": "Seit diesem Tag kamen keine Preise mehr, obwohl der Verkäufer weiter abgefragt wird, z. B. weil "
                       "seine Website die automatischen Abfragen sperrt. Seine Werte beruhen nur auf den Tagen davor.",
        "gestrichen_kurz": "seit {d} nicht mehr abgefragt",
        "gestrichen_erkl": "Nicht mehr abgefragt: an mindestens 6 Reisetagen nie billiger als die billigste Bahn eines "
                           "Start- oder Ziellandes (höchstens gleich teuer). Gezählt nur bei Zügen, die auch eine solche "
                           "Bahn mit Preis anbot; „allein am billigsten“ war er nur, wenn diese Bahn für den Zug keinen "
                           "Preis zeigte.",
        "wenig_verk": "Außerdem kurz abgefragt, aber mit zu wenigen Zügen für einen Vergleich: {v}.",
        "gestrichen": "seit {d} nicht mehr abgefragt: an {n} Reisetagen nie billiger als die billigste Bahn eines Start- oder "
                      "Ziellandes (höchstens gleich teuer) – gezählt nur bei Zügen, die auch eine solche Bahn mit Preis "
                      "anbot; „allein am billigsten“ war er nur, wenn diese Bahn für den Zug keinen Preis zeigte",
        "erkl_zuege": "Markiert: billigster Verkäufer für diesen Zug. Je Abfragetag stehen nur die Verkäufer in der "
                      "Tabelle, die an diesem Tag einen Preis hatten. Preise, die nur für einen Teil der Strecke gelten, "
                      "sind nicht enthalten.",
        "h2_buchen": "Direkt buchen",
        "erkl_buchen": "Die Preise ändern sich laufend; vor dem Buchen auf der Seite des Verkäufers prüfen.",
        "erkl_suchlink": " Direkt zur Suche für den {d}: {v}.",
        "provision": "* Provisionslink: Wenn du darüber buchst, bekomme ich eine kleine Provision. Dein Preis ändert sich "
                     "nicht, und auf den Vergleich und die Reihenfolge hat das keinen Einfluss.",
        "h1_start": "Welcher Verkäufer hat das billigste Zugticket?",
        "titel_start": "Zugpreis-Vergleich: Welcher Verkäufer ist am billigsten? | sametrain.eu",
        "stand_start": "{n} verglichene Züge auf {r} Strecken",
        "satz_start": "Ein Studentenprojekt, entstanden aus Neugier: Seit Oktober 2026 frage ich jeden Tag die Preise "
                      "derselben Züge bei {v} Bahn-Verkäufern ab, auf {r} Strecken in Europa. Die Frage dahinter: Wo "
                      "bekommt man dasselbe Ticket am günstigsten?",
        "satz_start2": " Bisher ist es meistens die Bahn des Start- oder Ziellandes, aber nicht immer, und manche Verkäufer "
                       "verlangen für denselben Zug ein Vielfaches.",
        "h2_alle": "Alle Strecken", "sp_strecke": "Strecke", "sp_meist": "meist am billigsten", "sp_wie_oft": "wie oft",
        "sp_unterschied": "größter Unterschied", "alle_gleich": "alle gleich teuer", "bis": "bis {f}×",
        "sp_verglichen": "verglichene Züge", "sp_ab": "ab", "sp_ab_zug": "Derselbe Zug · ab",
        "gleis_titel": "Beispiel: derselbe Zug bei {n} Verkäufern",
        "gleis_info": "Ein Zug aus der neuesten Abfrage: {z} · Fahrt am {d} · abgefragt {a}. "
                      "Alle Züge stehen unten unter „Alle gemessenen Züge“.",
        "zeile_info": "meist am billigsten: {v} ({b} von {n})", "zeile_zahlen": "{z} Züge verglichen", "gleich_kurz": "gleich", "skala_billig": "1×",
        "zeile_gleich": "alle Verkäufer gleich teuer", "tipp_zeile": "Strecke antippen für alle Züge, Preise und Buchungslinks.", "erkl_sortierung": "Sortiert nach Zahl der Züge und Verkäufer, Preisunterschied und wie oft eine ausländische Bahn billiger war.", "f_anzahl": "{n} Strecken", "sp_gewinner": "Gewinner", "sp_ab_preis": "Preis ab",
        "erkl_gleis": "„Gewinner“: der Verkäufer, der bei den meisten verglichenen Zügen am billigsten war. Das kleine Gleis zeigt einen Beispielzug aus der letzten Abfrage: links der billigste Verkäufer, jeder weitere Punkt ein anderer Verkäufer. Je länger die durchgezogene Schiene, desto größer der Preisunterschied für denselben Zug.",
        "ab_info": "bei {v} · Reisetag {d}, {z} · abgefragt {a}",
        "erkl_ab": "„Ab“: niedrigster Preis der letzten Abfrage dieser Strecke, für einen der abgefragten Reisetage.",
        "erkl_unterschied": "„Größter Unterschied“: teuerster geteilt durch billigsten Preis für denselben Zug.",
        "titel_methodik": "So wird gemessen", "beschr_methodik": "Wie die Zugpreise gemessen und verglichen werden.",
        "methodik_text": """<h1>So wird gemessen</h1>
<p>Ein Programm ruft jeden Tag die Websites der Bahn-Verkäufer auf und sucht dieselben Verbindungen, wie es auch ein
Mensch tun würde. Gespeichert wird der niedrigste angezeigte Preis je Zug für 1 Erwachsenen in der 2. Klasse ohne
Ermäßigung oder Rabattkarte.</p>
<h2>Was als „derselbe Zug“ gilt</h2>
<p>Zwei Angebote gelten als derselbe Zug, wenn Abfahrt und Ankunft gleich sind oder sie eine Zugnummer teilen und die
Zeiten höchstens 15 bzw. 20 Minuten abweichen. Verglichen werden nur Preise, die am selben Tag abgefragt wurden.</p>
<h2>Was nicht zählt</h2>
<ul><li>Preise, die nur für einen Teil der Strecke gelten (z. B. „Ticket nur für Teilstrecke“).</li>
<li>Verbindungen ohne angezeigten Preis.</li></ul>
<h2>Umrechnung</h2>
<p>Preise in CHF, CZK und PLN werden mit dem Referenzkurs der Europäischen Zentralbank vom Abfragetag umgerechnet.
Beim Bezahlen mit einer Euro-Karte ist der Kurs meist 1–3 % schlechter.</p>
<h2>Grenzen</h2>
<ul><li>Verglichen wird der niedrigste angezeigte Preis. Bei einem Verkäufer kann das ein Sparpreis sein, beim anderen
ein Normalpreis mit mehr Flexibilität.</li>
<li>Preise ändern sich laufend; eine Messung ist eine Momentaufnahme.</li>
<li>Servicegebühren beim Bezahlen sind bei den Bahnen nicht berücksichtigt. Beim Vermittler Omio ist eine geschätzte Servicegebühr eingerechnet (etwa 6,5 % des Ticketpreises, mindestens 2 €), weil sie dort bei jeder Buchung anfällt.</li>
<li>Ermäßigungen wie BahnCard, Railcards, Interrail oder Jugendrabatte sind nicht berücksichtigt. Mit Rabattkarte
kann ein anderer Verkäufer am billigsten sein.</li>
<li>Abgefragt werden Züge ab 8 Uhr morgens. Für Abend- und Nachtzüge können die Ergebnisse anders aussehen.</li></ul>
<h2>Welche Verkäufer fehlen</h2>
<p>Einige Verkäufer sperren automatische Abfragen mit Captchas oder Zugriffssperren. Diese Sperren werden bewusst
nicht umgangen, deshalb fehlen sie im Vergleich:</p>
<ul><li><strong>SNCF Connect</strong> (französische Staatsbahn): Captcha schon nach wenigen Aufrufen. Auf rein
französischen Strecken wie Lyon – Paris fehlt deshalb das normale TGV-inOui-Angebot; OUIGO ist dabei. Dort steht
stattdessen die offizielle Preisspanne aus SNCF Open Data (voller Tarif, min–max), als Einordnung.</li>
<li><strong>Trainline</strong> und <strong>Rail Europe</strong>: Zugriffssperre bzw. Captcha bei der Suche.</li>
<li>Außerdem u. a. NS International, SŽ (Slowenien) und ZSSK (Slowakei).</li></ul>
<h2>Daten</h2>
<p>Die Vergleichsdaten gibt es offen als <a href="../daten/vergleich.csv">CSV-Datei</a>, mit 7 Tagen Verzögerung:
Sie enthält alle Abfragen, die mindestens 7 Tage alt sind. Die aktuellen Preise stehen auf den Streckenseiten.</p>
<p>Zum Zitieren gibt es den Datensatz mit DOI bei Zenodo:
<a href="https://doi.org/10.5281/zenodo.23669337">doi.org/10.5281/zenodo.23669337</a>
(<a href="https://github.com/UrzasMine/same-train-different-price">auch auf GitHub</a>, Englisch).</p>
<p>Lizenz: <a href="https://creativecommons.org/licenses/by/4.0/deed.de" rel="license">CC BY 4.0</a>. Die Daten dürfen
frei genutzt werden, auch kommerziell, mit Quellenangabe „Zugpreis-Vergleich“ und Link auf diese Seite.</p>
""",
        "impressum_text": """<h1>Impressum</h1>
<h2>Angaben gemäß § 5 DDG</h2>
<p>{anbieter}</p>
<h2>Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV</h2>
<p>{name}, Anschrift wie oben</p>
<h2>Haftung für Links</h2>
<p>Diese Seite verlinkt auf die Websites der Bahn-Verkäufer. Für deren Inhalte sind ausschließlich die jeweiligen
Anbieter verantwortlich.</p>
<h2>Datenschutz</h2>
<p>Siehe <a href="datenschutz.html">Datenschutzerklärung</a>.</p>
""",
        "feedback": "Feedback", "beschr_feedback": "Rückmeldung, Fehler oder Wünsche zum Zugpreis-Vergleich.",
        "fb_text": "Fehler entdeckt, eine Strecke vermisst oder einfach eine Meinung? Schreib mir kurz.",
        "fb_art": "Worum geht es?", "fb_arten": {"wunsch": "Strecke oder Verkäufer vorschlagen", "fehler": "Fehler melden",
                                                   "lob": "Lob", "sonstiges": "Sonstiges"},
        "fb_nachricht": "Nachricht", "fb_email": "E-Mail (freiwillig, nur für Rückfragen)",
        "fb_senden": "Absenden", "fb_sendet": "Wird gesendet …",
        "fb_danke": "Danke! Deine Nachricht ist angekommen.",
        "fb_fehler": "Das hat leider nicht geklappt. Bitte später noch einmal versuchen oder eine E-Mail schreiben:",
        "fb_hinweis": "Gespeichert werden nur Nachricht, Thema, Sprache, die Seite, von der du kommst, und – falls "
                      "angegeben – die E-Mail-Adresse; keine IP-Adresse. Mehr in der <a href=\"datenschutz.html\">"
                      "Datenschutzerklärung</a>.",
        "datenschutz_zaehlung": """<h2>Besucherzählung</h2>
<p>Diese Seite zählt Besuche mit <a href="https://www.goatcounter.com">GoatCounter</a>. Dabei werden keine Cookies
gesetzt und keine IP-Adressen gespeichert. Erfasst werden nur aufgerufene Seite, Herkunftsseite (Referrer),
Browser, Bildschirmgröße und Land.</p>
""",
    },
    "en": {
        "titel": "Train Price Comparison",
        "ordner": "routes",
        "nav_alle": "All routes", "nav_methodik": "How it is measured", "nav_ergebnisse": "Results",
        "h1_befund": "The railway of your own country is usually cheapest. But not always.",
        "kz_zuege": "trains compared", "kz_verk": "sellers", "kz_strecken": "routes", "kz_bis": "up to {e}", "kz_spanne": "price difference for the same train", "kz_fremd": "of trains: a foreign railway was cheaper",
        "kz_vermittler": "more at {v} (median)", "satz_kurz": "A student project, started out of curiosity: since "
        "October 2026 I have been checking the fares of the same trains at many railway sellers every day.",
        "suche_gross": "Search a route, e.g. Munich Vienna",
        "vn_von": "From", "vn_nach": "To", "vn_von_ph": "e.g. Munich", "vn_nach_ph": "e.g. Vienna",
        "vn_tauschen": "Swap departure and destination", "vn_suche": "Search a route",
        "vn_gegen": "Not measured in this direction, but in the opposite one:",
        "vn_umstieg": "No direct route measured, but with a change between measured routes:",
        "vn_ueber": "via {s}", "vn_zusammen": "together from {p}",
        "vn_umst_hinweis": "Separate journeys: each price only covers its own leg, often measured on different days "
                           "or trains. A connection is not guaranteed.",
        "f_alle": "All", "f_fremd": "Foreign railway cheaper", "f_gross": "Big difference",
        "f_gleich": "All the same price", "weitere": "More routes with little data so far ({n})",
        "zs_fremd": "{v} cheaper than {h} for {p}% of trains", "zs_gleich": "all sellers charge the same",
        "zs_faktor": "{f} times as expensive at {v} (median)", "zs_prozent": "{p} more at {v} (median)",
        "zs_kaum": "hardly any price differences", "zs_nur": "other sellers were never cheaper, only {v} is still checked", "zs_zuege": "{n} trains", "spart": "save up to {e}",
        "alle_zeigen": "Show all {n} trains", "weniger_zeigen": "Show fewer",
        "datei_ergebnisse": "results",
        "titel_ergebnisse": "Results: where is the same train ticket cheapest?",
        "beschr_ergebnisse": "Key figures from {n} trains compared daily on {r} routes across Europe: which seller is "
                             "cheapest, when a foreign railway is cheaper, and where the same train costs several times "
                             "as much.",
        "stand_ergebnisse": "{n} trains compared on {r} routes · {v} sellers · checked {von} to {bis}",
        "h2_kurz": "Key findings",
        "befund_strecken": "On {k} of {r} routes, a railway of the origin or destination country was most often the "
                           "cheapest seller.",
        "befund_gleich": "On {k} of {r} routes, all compared sellers always charged the same price for the same train.",
        "befund_max": "The largest difference: on {s}, the same train cost {f} times as much at {teuer} as at {billig} "
                      "({pt} instead of {pb}).",
        "h2_verkaeufer_alle": "All sellers compared",
        "sp_strecken": "Routes", "sp_anteil": "Share",
        "erkl_verkaeufer_alle": "Across all routes: “cheapest” = lowest fare for the same train (including ties with "
                                "another seller). “If more expensive”: the seller's median markup over the cheapest fare "
                                "for the trains where it was not cheapest. Few trains = figures still uncertain.",
        "sp_wenn_teurer": "if more expensive: median",
        "h2_max": "The largest price differences for the same train",
        "sp_billig_bei": "cheapest", "sp_teuer_bei": "most expensive", "sp_faktor": "Factor",
        "erkl_max": "For each route the train with the largest gap between the cheapest and the most expensive seller.",
        "h2_fremd": "Where a foreign railway was cheaper",
        "fremd_satz": "Counted are trains for which a railway without its own origin or destination station was cheaper "
                      "than all railways of the origin and destination countries.",
        "fremd_keine": "Not on any route so far.", "sp_billiger_bei": "cheaper at", "sp_zuege_n": "Trains",
        "h2_zitieren": "Citing and data",
        "zitieren": "Source: “Train Price Comparison (sametrain.eu), data as of {d}”. You may use the figures freely "
                    "(CC BY 4.0) with a link to this page. The raw data is available as a "
                    "<a href=\"../daten/vergleich.csv\">CSV file</a> (checks at least 7 days old), citable with a DOI on "
                    "<a href=\"https://doi.org/10.5281/zenodo.23669337\">Zenodo</a>; the method is "
                    "described under <a href=\"methodik.html\">How it is measured</a>.",
        "vorsicht": "The data grows every day. For routes with only a few trains the figures are still uncertain.",
        "zu_ergebnissen": "All results at a glance",
        "fuss": "Our own measurements: fares for 1 adult, 2nd class, no discount card, checked directly on each "
                "seller's website. No guarantee of accuracy.",
        "methodik": "Method", "rohdaten": "Raw data (CSV, 7+ days old, CC BY 4.0)", "impressum": "Legal notice", "datenschutz": "Privacy",
        "beschr_datenschutz": "Privacy policy of the train price comparison.",
        "aktuell": "Updated daily · latest data: {d}",
        "rolle": {"Start/Ziel": "Railway of the origin or destination country",
                  "Durchgang": "Railway of a transit country", "kein Bezug": "Railway not involved in the route",
                  "Vermittler": "Reseller (sells tickets of many railways)"},
        "satz_gleich": "For {s}, all compared sellers charged the same price for the same train (typically {p}).",
        "satz": "For {s}, {v} was the cheapest seller of the same train for {b} of {n} compared trains "
                "(typical fare {p}).",
        "gesamt": "Cheapest trip overall (any train): {v} on {k} of {n} travel dates, from {p}.",
        "gesamt_titel": "Cheapest trip overall",
        "gesamt_info": "{v} on {k} of {n} travel dates · all trains and sellers, cheapest trip per travel date",
        "gesamt_eigene": "{v} runs its own trains that the other sellers do not offer, so {v} does not appear in the "
                         "same-train comparison below.",
        "satz_teuer": " The same train typically cost {f} times as much at {v}.",
        "satz_teuer_p": " At {v}, the same train cost a median of {p} more ({n} trains in common).",
        "satz_fehlt": " There is no same-train comparison with {v} yet.",
        "fehlt_kurz": "not yet compared with {v}",
        "sp_gegen": "vs. {v}", "kein_gemeinsam": "no train in common", "gegen_wert": "{p} · {n} trains",
        "h2_vorlauf": "When to book? Fares by booking time",
        "vorlauf_stufen": ("last minute (0–3 days)", "1–2 weeks ahead", "2–4 weeks ahead", "more than 4 weeks ahead"),
        "sp_vorlauf": "Checked", "sp_anzahl": "Trains", "sp_billigster_preis": "cheapest fare (median)",
        "vorlauf_satz": "Cheapest ticket for {s} (median): {liste}.",
        "vorlauf_zu_wenig": "There is not enough data yet to compare booking times on this route. Every travel date is "
                            "checked 1, 7, 21 and 42 days ahead.",
        "erkl_vorlauf": "For each train the lowest fare of all sellers counts. The groups contain different travel dates "
                        "and trains; this shows a tendency, not a guarantee.",
        "buchen_bester": "usually cheapest",
        "suche": "Search a city, e.g. Vienna", "suche_leer": "No route found.",
        "h2_faq": "Frequently asked questions",
        "faq_heim_f": "Is the railway of your own country always cheapest?",
        "faq_heim_a": "Mostly. For {p}% of the compared trains ({k} of {n}) a railway of the origin or destination "
                      "country was cheapest or as cheap as the cheapest other seller.",
        "faq_fremd_f": "Is it worth buying the ticket from a foreign railway?",
        "faq_fremd_ja": "Sometimes. For {k} of {n} trains ({p}%) another railway was cheaper than the railways of the "
                        "origin and destination countries, most often on the routes {s}.",
        "faq_fremd_nein": "Not so far: for none of the {n} compared trains was another railway cheaper than the railways "
                          "of the origin and destination countries.",
        "faq_fremd_teuer": " Railways not involved in the route charged a median of {f} times the cheapest fare.",
        "faq_vermittler_f": "Are resellers like {v} more expensive?",
        "faq_vermittler_a": "{start} {v} was cheapest for {b} of {n} compared trains and cost a median of {p} more than "
                            "the cheapest seller. An estimated service fee of about 6.5% (at least €2) is included.",
        "meist_ja": "Mostly yes, resellers cost more.", "nicht_unbedingt": "Not necessarily, resellers are not always more expensive.",
        "faq_wann_f": "When should you buy the train ticket?",
        "faq_wann_a": "{start} On {r} routes with data for both times, the cheapest ticket 1–2 weeks before travel "
                      "was a median of {p} than more than 4 weeks ahead.",
        "frueh": "As early as possible.", "egal": "So far the timing makes little difference.",
        "teurer": "{p}% more expensive", "billiger": "{p}% cheaper",
        "faq_wann_leer": "I am still collecting data: every travel date is checked 1, 7, 21 and 42 days ahead.",
        "faq_aktuell_f": "How up to date are the fares?",
        "faq_aktuell_a": "Fares are checked again every day, latest data: {d}. They change all the time; please check "
                         "with the seller before booking.",
        "h1_strecke": "{s} by train: where is the ticket cheapest?",
        "titel_strecke": "{s} by train: cheapest seller",
        "stand_strecke": "{n} trains compared · checked {von} to {bis}",
        "h2_verkaeufer": "Sellers compared",
        "sp_verkaeufer": "Seller", "sp_billigst": "cheapest", "sp_typisch": "typical fare",
        "sp_aufschlag": "markup vs. cheapest", "von": "{b} of {n}",
        "sp_allein": "cheapest alone", "sp_gleich": "tied cheapest", "sp_teurer": "more expensive",
        "sp_wie_oft_billig": "How often cheapest", "stapel_text": "{a} of {n}", "stapel_gleich": " · {g} tied",
        "erkl_verkaeufer2": "Counted per train the seller offered: “cheapest alone” = nobody was cheaper or equally "
                            "cheap; “tied cheapest” = the same lowest fare as at least one other seller; “more "
                            "expensive” = another seller was cheaper. “Vs. {v}”: median price difference for the trains "
                            "both sellers offered. Other currencies are converted at the ECB reference rate of the day "
                            "the fare was checked.",
        "satz_gleichauf": "For {s}, {v} almost always charged the same price for the same train ({g} of {n} shared "
                          "trains equally priced, typically {p}).",
        "satz_allein": "For {s}, {v} was the only cheapest seller of the same train for {a} of {n} trains and tied "
                       "cheapest for {g} (typical fare {p}).",
        "und": " and ",
        "erkl_verkaeufer": "“Cheapest”: how often the seller had the lowest fare for the same train. “Vs. {v}”: median "
                           "price difference for the trains both sellers offered. “Markup vs. cheapest”: median over "
                           "all of the seller's trains. Other currencies are converted at the ECB reference rate of the "
                           "day the fare was checked.",
        "h2_sncf": "SNCF fares for comparison",
        "sncf_text": "SNCF Connect cannot be checked automatically, so the daily TGV inOui fares are missing above. "
                     "SNCF does, however, publish the range of the full fare for this connection (2nd class, no "
                     "discount):",
        "sncf_median": "For comparison: the cheapest fare measured here per train had a median of {m}.",
        "sncf_buchen": "You can book TGV inOui and OUIGO e.g. at {l}, a small French seller without add-ons. Its "
                       "fares are not measured here; not an affiliate link.",
        "sncf_quelle": "Source: SNCF Voyageurs, “Tarifs TGV INOUI et OUIGO” (SNCF Open Data, ODbL licence), as of {d}. "
                       "The range applies to all trains and travel dates; the actual fare depends on demand and when "
                       "you book. It does not apply to Trenitalia's Frecciarossa trains.",
        "h2_zuege": "All measured trains", "sp_reisetag": "Booked ahead", "sp_zug": "Train", "tage_vorher": "{n} days ahead", "tag_vorher": "1 day ahead", "am_reisetag": "same day",
        "reise_abfrage": "travel {r} · checked {a}",
        "h3_abfrage": "Checked on {d}",
        "luecke_kurz": "last prices on {d}",
        "luecke_erkl": "No prices since that day although the seller is still being checked, e.g. because its website "
                       "blocks the automated searches. Its figures are based only on the days before.",
        "gestrichen_kurz": "not checked since {d}",
        "gestrichen_erkl": "No longer checked: on at least 6 travel dates never cheaper than the cheapest railway of the "
                           "origin or destination country (at most equally cheap). Counted only for trains that railway "
                           "also priced; it was “cheapest alone” only where that railway showed no fare for the train.",
        "wenig_verk": "Also checked briefly, but with too few trains for a comparison: {v}.",
        "gestrichen": "not checked since {d}: never cheaper than the cheapest railway of the origin or destination country "
                      "on {n} travel dates (at most equally cheap) – counted only for trains that railway also priced; "
                      "it was “cheapest alone” only where that railway showed no fare for the train",
        "erkl_zuege": "Highlighted: cheapest seller for that train. For each day, the table only shows sellers that had "
                      "a fare on that day. Fares valid only for part of the route are excluded.",
        "h2_buchen": "Book directly",
        "erkl_buchen": "Fares change all the time; check the seller's website before booking.",
        "erkl_suchlink": " Opens the search for {d} directly: {v}.",
        "provision": "* Commission link: if you book through it, I receive a small commission. Your price does not "
                     "change, and it has no influence on the comparison or the order.",
        "h1_start": "Which seller has the cheapest train ticket?",
        "titel_start": "Train price comparison: which seller is cheapest? | sametrain.eu",
        "stand_start": "{n} trains compared on {r} routes",
        "satz_start": "A student project, started out of curiosity: since October 2026 I have been checking the fares of "
                      "the same trains at {v} railway sellers every day, on {r} routes across Europe. The question "
                      "behind it: where do you get the same ticket cheapest?",
        "satz_start2": " So far it is usually the railway of the origin or destination country, but not always, and some "
                       "sellers charge several times as much for the same train.",
        "h2_alle": "All routes", "sp_strecke": "Route", "sp_meist": "usually cheapest", "sp_wie_oft": "how often",
        "sp_unterschied": "largest difference", "alle_gleich": "all the same price", "bis": "up to {f}×",
        "sp_verglichen": "trains compared", "sp_ab": "from", "sp_ab_zug": "Same train · from",
        "gleis_titel": "Example: the same train at {n} sellers",
        "gleis_info": "One train from the latest check: {z} · travel {d} · checked {a}. "
                      "All trains are listed below under “All measured trains”.",
        "zeile_info": "usually cheapest: {v} ({b} of {n})", "zeile_zahlen": "{z} trains compared", "gleich_kurz": "same", "skala_billig": "1×",
        "zeile_gleich": "all sellers charge the same", "tipp_zeile": "Tap a route to see all trains, fares and booking links.", "erkl_sortierung": "Sorted by number of trains and sellers, price difference and how often a foreign railway was cheaper.", "f_anzahl": "{n} routes", "sp_gewinner": "Winner", "sp_ab_preis": "Price from",
        "erkl_gleis": "“Winner”: the seller that was cheapest for most of the compared trains. The small track shows one example train from the latest check: cheapest seller on the left, each further dot another seller. The longer the solid track, the bigger the price difference for the same train.",
        "ab_info": "at {v} · travel date {d}, {z} · checked {a}",
        "erkl_ab": "“From”: lowest fare in the latest check of this route, for one of the travel dates checked.",
        "erkl_unterschied": "“Largest difference”: highest divided by lowest fare for the same train.",
        "titel_methodik": "How it is measured", "beschr_methodik": "How the train fares are measured and compared.",
        "methodik_text": """<h1>How it is measured</h1>
<p>Every day a program opens the railway sellers' websites and searches for the same connections, just as a person
would. It stores the lowest fare shown for each train for 1 adult in 2nd class without any discount or railcard.</p>
<h2>What counts as “the same train”</h2>
<p>Two offers count as the same train if departure and arrival times match, or if they share a train number and the
times differ by no more than 15 or 20 minutes. Only fares checked on the same day are compared.</p>
<h2>What is excluded</h2>
<ul><li>Fares that are only valid for part of the route (e.g. “ticket only for part of the journey”).</li>
<li>Connections without a fare shown.</li></ul>
<h2>Currency conversion</h2>
<p>Fares in CHF, CZK and PLN are converted at the European Central Bank reference rate of the day they were checked.
Paying with a euro card usually gives a rate 1–3 % worse.</p>
<h2>Limitations</h2>
<ul><li>I compare the lowest fare shown. At one seller this may be a saver fare, at another a flexible standard fare.</li>
<li>Fares change constantly; each measurement is a snapshot.</li>
<li>Booking fees charged at payment are not included for railways. For the reseller Omio an estimated service fee is added (about 6.5 % of the fare, at least €2), as it applies to every booking there.</li>
<li>Discounts such as BahnCard, railcards, Interrail or youth fares are not taken into account. With a discount card,
a different seller may be cheapest.</li>
<li>Only trains from 8 a.m. onwards are checked. Results for evening and night trains may differ.</li></ul>
<h2>Which sellers are missing</h2>
<p>Some sellers block automated searches with captchas or access blocks. These blocks are deliberately not
bypassed, so these sellers are missing from the comparison:</p>
<ul><li><strong>SNCF Connect</strong> (French national railway): captcha after only a few searches. On purely French
routes such as Lyon – Paris, the regular TGV inOui offer is therefore missing; OUIGO is included. Those pages show the
official fare range from SNCF Open Data instead (full fare, min–max), for context.</li>
<li><strong>Trainline</strong> and <strong>Rail Europe</strong>: access block or captcha when searching.</li>
<li>Also, among others, NS International, SŽ (Slovenia) and ZSSK (Slovakia).</li></ul>
<h2>Data</h2>
<p>The comparison data is openly available as a <a href="../daten/vergleich.csv">CSV file</a>, with a 7-day delay: it
contains all checks that are at least 7 days old. Current fares are shown on the route pages.</p>
<p>For citing, the dataset is available with a DOI on Zenodo:
<a href="https://doi.org/10.5281/zenodo.23669337">doi.org/10.5281/zenodo.23669337</a>
(<a href="https://github.com/UrzasMine/same-train-different-price">also on GitHub</a>).</p>
<p>License: <a href="https://creativecommons.org/licenses/by/4.0/" rel="license">CC BY 4.0</a>. You may use the data
freely, including commercially, if you credit “Train Price Comparison” with a link to this site.</p>
""",
        "impressum_text": """<h1>Legal notice</h1>
<h2>Information according to § 5 DDG (German law)</h2>
<p>{anbieter}</p>
<h2>Responsible for the content according to § 18 (2) MStV</h2>
<p>{name}, address as above</p>
<h2>Links to other websites</h2>
<p>This site links to the websites of railway sellers. Their respective operators are solely responsible for their
content.</p>
<h2>Privacy</h2>
<p>See <a href="datenschutz.html">privacy policy</a>.</p>
""",
        "feedback": "Feedback", "beschr_feedback": "Feedback, errors or wishes for the train price comparison.",
        "fb_text": "Found an error, missing a route, or just have an opinion? Drop me a line.",
        "fb_art": "What is it about?", "fb_arten": {"wunsch": "Suggest a route or seller", "fehler": "Report an error",
                                                   "lob": "Praise", "sonstiges": "Something else"},
        "fb_nachricht": "Message", "fb_email": "E-mail (optional, only for follow-up questions)",
        "fb_senden": "Send", "fb_sendet": "Sending …",
        "fb_danke": "Thank you! Your message has arrived.",
        "fb_fehler": "Sorry, that did not work. Please try again later or send an e-mail:",
        "fb_hinweis": "Only the message, topic, language, the page you came from and – if given – your e-mail address "
                      "are stored; no IP address. More in the <a href=\"datenschutz.html\">privacy policy</a>.",
        "datenschutz_zaehlung": """<h2>Visitor statistics</h2>
<p>This site counts visits with <a href="https://www.goatcounter.com">GoatCounter</a>. No cookies are set and no IP
addresses are stored. Only the page visited, the referring page, browser, screen size and country are recorded.</p>
""",
    },
}


def name(v):
    return VERKAEUFER.get(v, (v, ""))[0]


def strecke_in(strecke, lang):
    """'Prag – Budapest' -> 'Prague – Budapest' auf Englisch."""
    if lang == "en":
        return " – ".join(STADT_EN.get(s, s) for s in strecke.split(" – "))
    return strecke


def zahl(x, lang, stellen=1):
    text = f"{x:,.{stellen}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".") if lang == "de" else text


def euro(x, lang, stellen=2):
    return f"{zahl(x, lang, stellen)} €" if lang == "de" else f"€{zahl(x, lang, stellen)}"


def datum(d, lang):
    return f"{d.day}.{d.month}.{d.year}" if lang == "de" else f"{d.day} {MONATE_EN[d.month - 1]} {d.year}"


def datum_kurz(d, lang):
    return f"{d.day}.{d.month}." if lang == "de" else f"{d.day} {MONATE_EN[d.month - 1]}"


def slug(text):
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("Ä", "ae"), ("Ö", "oe"), ("Ü", "ue")):
        text = text.replace(a, b)
    return "-".join("".join(c if c.isalnum() else " " for c in text.lower()).split())


def strecken_pfad(strecke, lang):
    return f"{lang}/{T[lang]['ordner']}/{slug(strecke_in(strecke, lang))}.html"


def esc(text):
    return html.escape(str(text))


def lesen(path):
    """Verbindungen je Strecke und Abfragetag: {strecke: [ {reise_datum, abfahrt, ankunft, zuege, vorlauf, abfrage,
    preise: {verkäufer: (eur, original, rolle, tarif)}} ]}"""
    groups = collections.OrderedDict()
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if not r["preis_eur"]:
                continue
            strecke = r["strecke"].replace(" - ", " – ")
            vorlauf = int(r["vorlauf_tage"])
            # Nur Preise vom selben Abfragetag vergleichen: Vorlauf gehört zum Schlüssel
            key = (strecke, r["reise_datum"], vorlauf, r["abfahrt"], r["ankunft"])
            g = groups.setdefault(key, {"strecke": strecke, "nr": r["nr"], "reise_datum": r["reise_datum"],
                                        "abfahrt": r["abfahrt"], "ankunft": r["ankunft"], "zuege": r["zuege"],
                                        "preise": {}, "vorlauf": vorlauf,
                                        "abfrage": date.fromisoformat(r["reise_datum"]) - timedelta(days=vorlauf)})
            eur = float(r["preis_eur"].replace(",", "."))
            original = (r["preis"], r["waehrung"]) if r["waehrung"] != "EUR" else None
            if r["verkaeufer"] not in g["preise"] or eur < g["preise"][r["verkaeufer"]][0]:
                g["preise"][r["verkaeufer"]] = (eur, original, r["rolle"], r["tarif"])
            if not g["zuege"] and r["zuege"]:
                g["zuege"] = r["zuege"]
    routes = collections.defaultdict(list)
    for g in groups.values():
        if len(g["preise"]) >= 2:
            routes[g["strecke"]].append(g)
    return routes


# Kürzel der Seite in logs/gestrichen.csv -> Verkäufer in vergleich.csv
SEITE_VERKAEUFER = {
    "db": "bahn.de", "oebb": "oebb.at", "sbb": "sbb.ch", "ltg": "ltglink.lt", "elron": "elron.ee", "vivi": "vivi.lv",
    "koleo": "koleo.pl", "pkp": "intercity.pl", "trenitalia": "trenitalia.com", "mav": "mav.hu", "cd": "cd.cz",
    "sncb": "b-europe.com", "ouigo": "ouigo.com", "eurostar": "eurostar.com", "omio": "omio.com",
    "ns": "nsinternational.com", "regiojet": "regiojet.com", "cfr": "cfrcalatori.ro",
}


def gestrichen():
    """Von der 6er-Regel gestrichene Verkäufer (skripte/unbeteiligte_streichen.py):
    {(strecke, verkäufer): (datum, zahl der abfragen)}"""
    out = {}
    try:
        with open(LOGS / "gestrichen.csv", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                verk = SEITE_VERKAEUFER.get(r["seite"])
                if verk:
                    out[(r["strecke"].replace(" - ", " – "), verk)] = (date.fromisoformat(r["datum"]), r["abfragen"])
    except FileNotFoundError:
        pass
    return out


GESTRICHEN = gestrichen()


def in_liste():
    """(strecke, verkäufer), die laut listen/strecken.csv noch abgefragt werden."""
    out = set()
    with open(STRECKEN, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            verk = SEITE_VERKAEUFER.get(r["seite"])
            if verk:
                out.add((r["strecke"].replace(" - ", " – "), verk))
    return out


IN_LISTE = in_liste()
LUECKE_TAGE = 2  # so viele spätere Abfragetage der Strecke ohne Preis dieses Verkäufers -> Schild „zuletzt Preise am …“


def letzte_preise():
    """Aus daten/preise.csv: ({(strecke, quelle): letzter Abfragetag mit Preis}, {strecke: alle Abfragetage}).
    Bewusst aus den Rohdaten statt aus vergleich.csv: dort fehlen Preise, die keinen Partner vom selben Tag haben
    (z. B. ÖBB von Hand an Tagen, an denen die Strecke sonst nicht abgefragt wurde); das ist keine Sperre."""
    letzte, tage = {}, collections.defaultdict(set)
    with open(DATEN / "preise.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            s, a = r["strecke"].replace(" - ", " – "), date.fromisoformat(r["abfrage_datum"])
            tage[s].add(a)
            if r["preis"] and a > letzte.get((s, r["quelle"]), date.min):
                letzte[(s, r["quelle"])] = a
    return letzte, tage


LETZTE_PREISE, ABFRAGETAGE = letzte_preise()


def billigste_fahrt():
    """{Strecke: Zeilen aus daten/billigste_fahrt.csv}; nur Reisetage, an denen mindestens zwei Verkäufer abgefragt wurden."""
    fahrten = collections.defaultdict(list)
    if BILLIGSTE_FAHRT.exists():
        with open(BILLIGSTE_FAHRT, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                if int(r["verkaeufer_abgefragt"]) >= 2:
                    r["preis"] = float(r["preis_eur"].replace(",", "."))
                    fahrten[r["strecke"].replace(" - ", " – ")].append(r)
    return fahrten


BILLIGSTE = billigste_fahrt()


def gesamt(strecke):
    """Wer bot an den meisten Reisetagen die billigste Fahrt über alle Züge? (Verkäufer, Tage, alle Tage, ab-Preis)
    ab-Preis: billigste Fahrt dieses Verkäufers aus seiner neuesten Abfrage. None bei zu wenig Reisetagen."""
    fahrten = BILLIGSTE.get(strecke, [])
    if len(fahrten) < 3:
        return None
    zahl_tage = collections.Counter(r["verkaeufer"] for r in fahrten)
    verk, k = zahl_tage.most_common(1)[0]
    eigene = [r for r in fahrten if r["verkaeufer"] == verk]
    letzte = max(r["abfrage_datum"] for r in eigene)
    ab = min(r["preis"] for r in eigene if r["abfrage_datum"] == letzte)
    return verk, k, len(fahrten), ab


def gestrichen_hier(verbindungen):
    """Verkäufer, die auf der Strecke dieser Verbindungen gestrichen sind."""
    strecke = verbindungen[0]["strecke"] if verbindungen else ""
    return {verk for (s, verk) in GESTRICHEN if s == strecke}


def statistik(verbindungen):
    """Je Verkäufer: Zahl der Vergleiche, wie oft billigster, Median-Preis, Median-Faktor zum Billigsten."""
    s = collections.defaultdict(lambda: {"n": 0, "billigster": 0, "allein": 0, "gleich": 0, "teurer": 0,
                                         "preise": [], "faktoren": [], "rolle": ""})
    for v in verbindungen:
        low = min(p[0] for p in v["preise"].values())
        n_low = sum(p[0] <= low + 0.005 for p in v["preise"].values())
        for verk, (eur, _, rolle, _) in v["preise"].items():
            e = s[verk]
            e["n"] += 1
            e["preise"].append(eur)
            e["faktoren"].append(eur / low if low else 1)
            e["rolle"] = rolle
            if eur <= low + 0.005:
                e["billigster"] += 1
                e["allein" if n_low == 1 else "gleich"] += 1
            else:
                e["teurer"] += 1
    # Reihenfolge nach dem Anteil der Züge, bei denen der Verkäufer am billigsten war. Damit „2 von 2“ nicht gegen
    # „30 von 40“ gewinnt, zählen zuerst nur Verkäufer mit mindestens halb so vielen Zügen wie der mit den meisten.
    # (Nach der Anzahl allein stand z. B. ÖBB bei Berlin–Dresden mit 37 von 38 vor bahn.de mit 36 von 36, obwohl ÖBB nie
    # billiger war.) Bei Gleichstand zuerst die Bahn des Start-/Ziellandes; gestrichene Verkäufer ganz nach hinten.
    rang = {"Start/Ziel": 0, "Durchgang": 1, "Vermittler": 2, "kein Bezug": 3}
    genug = max(e["n"] for e in s.values()) / 2
    # Wer nie am billigsten war, kommt nie nach vorn (sonst stand z. B. bei Warschau–Prag Omio mit 0 von 25 vorn,
    # weil die Bahnen weniger als halb so viele Züge hatten)
    return sorted(s.items(), key=lambda kv: (kv[0] in gestrichen_hier(verbindungen), kv[1]["billigster"] == 0,
                                             kv[1]["n"] < genug,
                                             -kv[1]["billigster"] / kv[1]["n"], rang.get(kv[1]["rolle"], 4),
                                             statistics.median(kv[1]["faktoren"])))


def groesster_faktor(verbindungen):
    # nur die Preise vergleichen: bei Gleichstand würde max() sonst die übrigen Felder vergleichen (None gegen Tupel)
    return max(max(p[0] for p in v["preise"].values()) / min(p[0] for p in v["preise"].values())
               for v in verbindungen)


def gegenueber(verbindungen, a, b):
    """Züge, die a und b beide im Angebot hatten: (Anzahl, Median von Preis b / Preis a)."""
    q = [v["preise"][b][0] / v["preise"][a][0] for v in verbindungen
         if a in v["preise"] and b in v["preise"] and v["preise"][a][0]]
    return len(q), (statistics.median(q) if q else None)


def gleichauf(verbindungen, a, b):
    """Züge, die a und b beide im Angebot hatten: (davon genau gleich teuer, Anzahl gemeinsam)."""
    gem = [v for v in verbindungen if a in v["preise"] and b in v["preise"]]
    return sum(abs(v["preise"][a][0] - v["preise"][b][0]) < 0.005 for v in gem), len(gem)


def ohne_vergleich(verbindungen, stat):
    """Bahnen des Start-/Ziellandes, die nie am selben Zug mit dem meist billigsten Verkäufer verglichen wurden."""
    best = stat[0][0]
    return [verk for verk, e in stat[1:] if e["rolle"] == "Start/Ziel" and not gegenueber(verbindungen, best, verk)[0]]


def prozent(faktor, lang):
    p = (faktor - 1) * 100
    if abs(p) < 0.5:
        return "±0 %"
    return ("+" if p > 0 else "−") + zahl(abs(p), lang, 0) + " %"  # geschütztes Leerzeichen: kein Umbruch zwischen Zahl und %


VORLAUF_STUFEN = ((0, 3), (4, 13), (14, 27), (28, 9999))  # Tage vor der Fahrt; tägliche Abfragen bei 1, 7, 21, 42


def nach_vorlauf(verbindungen):
    """{Stufe: {'preise': billigster Preis je Zug, 'billigster': Counter Verkäufer}}, nur Stufen mit mind. 3 Zügen."""
    stufen = collections.defaultdict(lambda: {"preise": [], "billigster": collections.Counter()})
    for v in verbindungen:
        low = min(p[0] for p in v["preise"].values())
        s = stufen[next(i for i, (a, b) in enumerate(VORLAUF_STUFEN) if a <= v["vorlauf"] <= b)]
        s["preise"].append(low)
        for verk, p in v["preise"].items():
            if p[0] <= low + 0.005:
                s["billigster"][verk] += 1
    return {i: s for i, s in sorted(stufen.items()) if len(s["preise"]) >= 3}


def ab_preis(verbindungen):
    """Billigstes Angebot der letzten Abfrage einer Strecke: (Preis in €, Verbindung, Verkäufer)."""
    letzte = max(v["abfrage"] for v in verbindungen)
    return min(((p[0], v, verk) for v in verbindungen if v["abfrage"] == letzte for verk, p in v["preise"].items()),
               key=lambda x: (x[0], x[1]["reise_datum"], x[1]["abfahrt"]))


def pfeil(strecke):
    """Anzeige mit Richtungspfeil: 'München – Wien' -> 'München → Wien' (abgefragt wird je Strecke eine Richtung)."""
    return strecke.replace(" – ", " → ")


def kurzname(verk):
    """'bahn.de (DB)' -> 'DB', 'České dráhy (ČD)' -> 'ČD', sonst der Anzeigename."""
    n = name(verk)
    return n[n.index("(") + 1:n.index(")")] if "(" in n else n


def beispielzug(verbindungen):
    """Zug der letzten Abfrage mit den meisten Verkäufern (bei Gleichstand größter Preisunterschied):
    daran zeigt das Preis-Gleis „derselbe Zug, verschiedene Preise“."""
    letzte = max(v["abfrage"] for v in verbindungen)
    kandidaten = [v for v in verbindungen if v["abfrage"] == letzte] or verbindungen
    return max(kandidaten, key=lambda v: (len(v["preise"]),
                                          max(p[0] for p in v["preise"].values()) / min(p[0] for p in v["preise"].values()),
                                          -v["vorlauf"]))


MINI = {"breite": 200, "von": 8, "bis": 146, "faktor": 4}  # kleines Gleis: Schiene von x=8 (billigster) bis x=146 (4-Fach)


def mini_x(faktor):
    """x-Position im kleinen Gleis für ein Vielfaches des billigsten Preises (1 = billigster, ab 4 ganz rechts)."""
    return MINI["von"] + min((faktor - 1) / (MINI["faktor"] - 1), 1) * (MINI["bis"] - MINI["von"])


def gleis_klein(preise, lang):
    """Kleines Gleis für die Startseite (Variante A): durchgezogen vom billigsten bis zum teuersten Verkäufer,
    der Rest bis zum 4-Fachen gestrichelt; dahinter das Vielfache. Feine Striche bei 2× und 3× passen zur Skala
    über der Liste."""
    lo, hi = preise[0][0], preise[-1][0]
    f = hi / lo if lo else 1
    y = 12
    teile = [f'<line class="rest" x1="{MINI["von"]}" y1="{y}" x2="{MINI["bis"]}" y2="{y}"/>']
    teile += [f'<line class="strich" x1="{mini_x(k):.1f}" y1="{y - 5}" x2="{mini_x(k):.1f}" y2="{y + 5}"/>' for k in (2, 3)]
    if f >= 1.005:
        teile.append(f'<line class="schiene" x1="{MINI["von"]}" y1="{y}" x2="{mini_x(f):.1f}" y2="{y}"/>')
    for preis, _ in reversed(preise):
        billig = preis <= lo + 0.005
        teile.append(f'<circle class="halt{" billig" if billig else ""}" cx="{mini_x(preis / lo):.1f}" cy="{y}" '
                     f'r="{5 if billig else 3.5}"/>')
    text = (f"{zahl(f, lang, 1)}×" if f >= 1.05 else T[lang]["gleich_kurz"])
    teile.append(f'<text class="faktor" x="{MINI["bis"] + 10}" y="{y + 4}">{text}</text>')
    return f'<svg class="gleis klein" viewBox="0 0 {MINI["breite"]} 24" aria-hidden="true">' + "".join(teile) + "</svg>"


def mini_skala(lang):
    """Skala einmal über der Streckenliste, passend zu den kleinen Gleisen."""
    t = T[lang]
    marken = [(1, t["skala_billig"]), (2, "2×"), (3, "3×"), (4, "4×+")]
    texte = "".join(f'<text x="{mini_x(k):.1f}" y="11" text-anchor="{"start" if k == 1 else "middle"}">{esc(b)}</text>'
                    for k, b in marken)
    # Kopfzeile: je Spalte eine kurze Beschriftung, über dem Gleis die gemeinsame Skala
    return (f'<li class="skala" aria-hidden="true"><span class="z-text">{t["sp_strecke"]}</span>'
            f'<span class="z-sieger">{t["sp_gewinner"]}</span>'
            f'<svg class="gleis klein" viewBox="0 0 {MINI["breite"]} 14">{texte}</svg>'
            f'<span class="z-preis">{t["sp_ab_preis"]}</span><span class="z-pfeil"></span></li>')


def gleis(v, lang, klein=False, breite=600, cls=""):
    """Preis-Gleis als SVG: eine Schiene, jeder Verkäufer eine Haltestelle; je teurer, desto weiter rechts.
    Der billigste Halt ist hervorgehoben. klein=True: nur Punkte, ohne Beschriftung, auf einem für alle Strecken
    gleichen Maßstab bis zum 4-Fachen (für die Startseite)."""
    preise = sorted((p[0], verk) for verk, p in v["preise"].items())
    lo, hi = preise[0][0], preise[-1][0]
    if klein:
        return gleis_klein(preise, lang)
    breite, rand = breite, 34
    if True:
        x_von = lambda p: rand + (p - lo) / (hi - lo) * (breite - 2 * rand) if hi - lo > 0.005 else rand
    y = 10 if klein else 46
    teile = [f'<line class="schiene" x1="{rand}" y1="{y}" x2="{breite - rand}" y2="{y}"/>']
    # Verkäufer mit genau gleichem Preis teilen sich einen Halt: ein Preis oben, die Namen untereinander
    halte = []
    for preis, verk in preise:
        if halte and preis <= halte[-1][0] + 0.005:
            halte[-1][1].append(verk)
        else:
            halte.append((preis, [verk]))
    # Nicht ganz maßstabsgetreu: nahe Halte rücken auf einen Mindestabstand auseinander, damit Preis und Name
    # nebeneinander passen (die Preise stehen ja dran). Reihenfolge und rechter Rand bleiben erhalten.
    abstand = min(72, (breite - 2 * rand) / max(len(halte) - 1, 1))
    xs = [x_von(p) for p, _ in halte]
    for i in range(1, len(xs)):
        xs[i] = max(xs[i], xs[i - 1] + abstand)
    xs[-1] = min(xs[-1], breite - rand)
    for i in range(len(xs) - 2, -1, -1):
        xs[i] = min(xs[i], xs[i + 1] - abstand)
    lage = {p: x for (p, _), x in zip(halte, xs)}
    belegt = []  # (x, Zeile, Anzahl Namen) der Beschriftungen, damit sich nahe Halte nicht überlappen
    for preis, verks in reversed(halte):  # billigster zuletzt, damit sein Punkt oben liegt
        x = lage[preis]
        billig = preis <= lo + 0.005
        teile.append(f'<circle class="halt{" billig" if billig else ""}" cx="{x:.1f}" cy="{y}" r="{9 if billig else 6}"/>')
        # Zeile so wählen, dass weder der Preis noch die Namen (Zeilen zeile..zeile+n-1) einen nahen Halt treffen
        zeile = 0
        while any(abs(x - bx) < 62 and zeile < bz + bn and bz < zeile + len(verks) for bx, bz, bn in belegt):
            zeile += 1
        belegt.append((x, zeile, len(verks)))
        dy = 16 * zeile
        wert_cls = "wert billig" if billig else "wert"
        teile.append(f'<text class="{wert_cls}" x="{x:.1f}" y="{y - 16 - dy}">{euro(preis, lang, 0 if preis >= 100 else 2)}</text>')
        teile += [f'<text class="name" x="{x:.1f}" y="{y + 30 + dy + 16 * i}">{esc(kurzname(verk))}</text>'
                  for i, verk in enumerate(verks)]
    hoehe = 46 + 34 + 16 * max([z + n - 1 for _, z, n in belegt] or [0])
    if True:
        oben = 16 * max([z for _, z, _ in belegt] or [0]) + 4  # Platz für versetzte Preise über der Schiene
        return (f'<svg class="gleis {cls}" viewBox="0 {-oben} {breite} {hoehe + oben}" role="img" '
                f'aria-label="{esc(", ".join(f"{name(vk)} {euro(p, lang)}" for p, vk in preise))}">'
                + "".join(teile) + "</svg>")


def balken(anteil):
    """Kleiner Balken hinter einer Zahl (0–1), nur zur Orientierung; die Zahl steht immer daneben."""
    return f"<span class='balken' style='--a:{round(100 * anteil)}%' aria-hidden='true'></span>"


def stapel(e, lang):
    """Ein Balken für alle Züge eines Verkäufers: allein am billigsten | gleich billig | teurer, daneben „63 von 66“."""
    t = T[lang]
    teile = "".join(f"<i class='{c}' style='width:{100 * e[k] / e['n']:.1f}%'></i>"
                    for c, k in (("s-allein", "allein"), ("s-gleich", "gleich"), ("s-teurer", "teurer")) if e[k])
    text = t["stapel_text"].format(a=e["allein"], n=e["n"]) + (t["stapel_gleich"].format(g=e["gleich"]) if e["gleich"] else "")
    titel = f"{t['sp_allein']} {e['allein']} · {t['sp_gleich']} {e['gleich']} · {t['sp_teurer']} {e['teurer']}"
    return (f"<div class='stapel' title='{esc(titel)}'><span class='stapel-balken' aria-hidden='true'>{teile}</span>"
            f"<span class='stapel-text'>{text}</span></div>")


def vorlauf_abschnitt(strecke, verbindungen, lang):
    t = T[lang]
    stufen = nach_vorlauf(verbindungen)
    if len(stufen) < 2:
        return f"<h2>{t['h2_vorlauf']}</h2>\n<p class='klein'>{t['vorlauf_zu_wenig']}</p>\n"
    zeilen, liste = [], []
    hoechster = max(statistics.median(s["preise"]) for s in stufen.values())
    for i, s in stufen.items():
        m = statistics.median(s["preise"])
        median = euro(m, lang, 0)
        b = s["billigster"].most_common(1)[0][1]
        # Bei Gleichstand alle gleich oft billigsten Verkäufer nennen, nicht zufällig einen davon
        verk = " = ".join(name(v) for v, c in s["billigster"].most_common() if c == b)
        n = len(s["preise"])
        liste.append(f"{t['vorlauf_stufen'][i]} {median}")
        zeilen.append(f"<tr><td>{t['vorlauf_stufen'][i]}</td><td class='zahl'>{n}</td>"
                      f"<td class='zahl'>{median}{balken(m / hoechster)}</td>"
                      f"<td>{esc(verk)} <span class='klein'>({t['von'].format(b=b, n=n)})</span></td></tr>")
    satz = t["vorlauf_satz"].format(s=strecke_in(strecke, lang), liste=", ".join(liste))
    return f"""<h2>{t['h2_vorlauf']}</h2>
<p>{esc(satz)}</p>
<div class="tabelle"><table><thead><tr><th>{t['sp_vorlauf']}</th><th class="zahl">{t['sp_anzahl']}</th>
<th class="zahl">{t['sp_billigster_preis']}</th><th>{t['sp_meist']}</th></tr></thead><tbody>{''.join(zeilen)}</tbody></table></div>
<p class="klein">{t['erkl_vorlauf']}</p>
"""


def kurzaussage(strecke, verbindungen, stat, lang):
    """Ein Satz, den Suchmaschinen und KI-Antworten übernehmen können."""
    t, s = T[lang], strecke_in(strecke, lang)
    best, b = stat[0]
    typisch = euro(statistics.median(b["preise"]), lang, 0)
    # Fährt ein anderer Verkäufer insgesamt am billigsten (z. B. OUIGO mit eigenen Zügen), steht das zuerst:
    # sonst lesen Suchmaschinen und KI-Antworten „X am billigsten“ als Antwort auf „wo fahre ich am billigsten“
    g = gesamt(strecke)
    vorweg = (t["gesamt"].format(v=name(g[0]), k=g[1], n=g[2], p=euro(g[3], lang, 0 if g[3] >= 100 else 2)) + " "
              if g and g[0] != best else "")
    if groesster_faktor(verbindungen) < 1.005:
        return vorweg + t["satz_gleich"].format(s=s, p=typisch)
    # Verkäufer, die bei mindestens 80 % der gemeinsamen Züge genau so viel verlangten wie der meist billigste:
    # dann ist „X war am billigsten“ irreführend, ehrlicher ist „X und Y verlangten dasselbe“
    partner = []
    for verk, _ in stat[1:]:
        g, n = gleichauf(verbindungen, best, verk)
        if n >= 3 and g / n >= 0.8:
            partner.append((verk, g, n))
    if partner:
        namen = t["und"].join([name(best)] + [name(v) for v, _, _ in partner])
        text = t["satz_gleichauf"].format(s=s, v=namen, g=partner[0][1], n=partner[0][2], p=typisch)
    elif b["gleich"]:
        text = t["satz_allein"].format(s=s, v=name(best), a=b["allein"], g=b["gleich"], n=b["n"], p=typisch)
    else:
        text = t["satz"].format(s=s, v=name(best), b=b["billigster"], n=b["n"], p=typisch)
    gleich_teuer = {v for v, _, _ in partner}
    # Teuerster Verkäufer gegenüber dem meist billigsten, am selben Zug (wie Spalte „gegenüber …“ der Tabelle):
    # unter dem Doppelten in Prozent („13 % mehr“), ab dem Doppelten als Faktor („3,1-mal so viel“)
    teuer = []
    for verk, _ in stat:
        if verk != best and verk not in gleich_teuer:
            n, q = gegenueber(verbindungen, best, verk)
            if q and n >= max(1, b["n"] // 3):
                teuer.append((q, n, verk))
    if teuer:
        q, n, verk = max(teuer)
        if q >= 2:
            text += t["satz_teuer"].format(v=name(verk), f=zahl(q, lang))
        elif q >= 1.03:
            text += t["satz_teuer_p"].format(v=name(verk), p=prozent(q, lang).lstrip("+"), n=n)
    fehlt = ohne_vergleich(verbindungen, stat)
    if fehlt:
        text += t["satz_fehlt"].format(v=", ".join(name(x) for x in fehlt))
    return vorweg + text


CSS = """
/* „Preis-Gleis“: ruhiges warmes Grau, schwarz-weiß: der Akzent ist die Textfarbe selbst (invertierte Schilder, gefüllter Punkt) für den billigsten Preis.
   Erkennungszeichen ist das Gleis: eine Schiene, jeder Verkäufer eine Haltestelle, je teurer, desto weiter rechts. */
:root { --bg:#f4f2ee; --flaeche:#fbfaf7; --fg:#22211f; --muted:#77736b; --line:#e2ded6; --rule:#22211f;
  --akzent:#22211f; --akzent-hell:#e2ded6; --auf-akzent:#fbfaf7; --bar:#22211f; --barbg:#e2ded6;
  --schrift: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
@media (prefers-color-scheme: dark) { :root { --bg:#16171a; --flaeche:#1d1f23; --fg:#ece8df; --muted:#9a968d;
  --line:#2e3036; --rule:#ece8df; --akzent:#ece8df; --akzent-hell:#2e3036; --auf-akzent:#16171a; --bar:#ece8df; --barbg:#2e3036; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.55 var(--schrift); }
header, main, footer { max-width: 920px; margin: 0 auto; padding: 0 16px; }
header { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px 24px;
  padding-top: 22px; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
header > div { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 28px; }
header .marke { font-weight: 750; font-size: 1.15rem; letter-spacing: -.02em; color: var(--fg); text-decoration: none; }
header .marke .punkt { color: var(--akzent); }
header .marke .untertitel { font-weight: 400; font-size: .85rem; letter-spacing: 0; color: var(--muted); margin-left: 8px; }
nav, .sprache { font-size: .9rem; }
nav a, .sprache a { color: var(--muted); text-decoration: none; }
nav a:hover, .sprache a:hover { color: var(--fg); }
.sprache strong { color: var(--fg); }
a { color: var(--fg); text-decoration-color: var(--akzent); text-underline-offset: 3px; }
a:hover { color: var(--akzent); }
.aktuell { margin: 40px 0 0; font-size: .85rem; color: var(--muted); }
.aktuell::before { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: var(--akzent); margin-right: 8px; vertical-align: 1px; }
h1 { font-size: clamp(1.8rem, 4.6vw, 2.7rem); line-height: 1.1; font-weight: 700; letter-spacing: -.025em;
  margin: 8px 0 10px; max-width: 24ch; }
main > h1:first-child { margin-top: 40px; }
h2 { font-size: 1.2rem; font-weight: 700; letter-spacing: -.01em; margin: 56px 0 14px; }
h3 { font-size: 1rem; font-weight: 650; margin: 26px 0 8px; }
h4 { font-size: .95rem; font-weight: 650; margin: 18px 0 4px; }
.stand { color: var(--muted); font-size: .9rem; margin: 0; }
.kurz { font-size: clamp(1.05rem, 2.5vw, 1.15rem); line-height: 1.55; margin: 22px 0 0; max-width: 64ch; }
.klein { color: var(--muted); font-size: .82rem; }
main > p.klein { margin: 8px 0 0; max-width: 72ch; }

/* Das Preis-Gleis */
.gleis-block { margin: 28px 0 0; padding: 18px 20px 14px; background: var(--flaeche); border: 1px solid var(--line);
  border-radius: 14px; }
.gleis-block figcaption { font-weight: 650; font-size: .95rem; }
.gleis-block .klein { margin: 4px 0 0; }
.gleis { display: block; width: 100%; height: auto; overflow: visible; }
.gleis-block .gleis { margin: 10px 0 0; max-width: 680px; }
.gleis.schmal { display: none; }
@media (max-width: 560px) { .gleis-block { padding: 14px 14px 12px; } .gleis.breit { display: none; }
  .gleis.schmal { display: block; } }
.gleis .schiene { stroke: var(--fg); stroke-width: 3; stroke-linecap: round; }
.gleis .halt { fill: var(--flaeche); stroke: var(--fg); stroke-width: 2.5; }
.gleis .halt.billig { fill: var(--akzent); stroke: var(--akzent); }
.gleis text { font: 13px var(--schrift); fill: var(--fg); text-anchor: middle; }
.gleis text.wert { font-weight: 600; font-variant-numeric: tabular-nums; }
.gleis text.wert.billig { fill: var(--akzent); font-weight: 750; }
.gleis text.name { fill: var(--muted); font-size: 12px; }
.gleis.klein { width: 200px; flex: none; }
.gleis.klein .schiene { stroke-width: 2.5; }
.gleis.klein .rest { stroke: var(--muted); stroke-width: 1.5; stroke-dasharray: 2 4; opacity: .6; }
.gleis.klein .strich { stroke: var(--line); stroke-width: 1; }
.gleis.klein .halt { stroke-width: 1.5; }
.gleis.klein text { font-size: 12px; text-anchor: start; fill: var(--muted); }
.gleis.klein text.faktor { font-weight: 650; fill: var(--fg); font-variant-numeric: tabular-nums; }
.strecken li.skala { display: flex; align-items: center; gap: 20px; padding: 10px 0 8px;
  border-bottom: 1px solid var(--line); }
.strecken li.skala > span { font-size: .7rem; font-weight: 600; letter-spacing: .07em; text-transform: uppercase;
  color: var(--muted); white-space: nowrap; }
.strecken li.skala text { font-size: 11px; fill: var(--muted); }

/* „ab“-Preis */
.ab { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 16px; margin: 20px 0 0; }
.ab p { margin: 0; }
.ab-preis { font-size: clamp(1.9rem, 5.5vw, 2.5rem); font-weight: 750; letter-spacing: -.02em; line-height: 1;
  font-variant-numeric: tabular-nums; }
.ab-preis span { font-size: .42em; font-weight: 400; color: var(--muted); letter-spacing: 0; margin-right: 2px; }
.ab-info { color: var(--muted); font-size: .92rem; }
/* Billigste Fahrt über alle Züge: gleich aufgebaut wie der ab-Preis, etwas kleiner */
.ab.gesamt { margin-top: 12px; }
.ab.gesamt .ab-preis { font-size: clamp(1.4rem, 4vw, 1.8rem); }
.ab.gesamt .klein { flex-basis: 100%; margin: 2px 0 0; }

/* Startseite: Strecken als Liste mit kleinem Gleis */
.strecken { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--line); }
.strecken li { border-bottom: 1px solid var(--line); }
.zeile { display: flex; align-items: center; gap: 20px; padding: 14px 10px; margin: 0 -10px; color: var(--fg);
  text-decoration: none; border-radius: 10px; }
.zeile:hover { background: var(--flaeche); color: var(--fg); }
.zeile:hover .z-name { text-decoration: underline; text-underline-offset: 3px; }
.z-pfeil { flex: none; width: 1rem; margin-left: -8px; font-size: 1.5rem; line-height: 1; color: var(--muted);
  transition: transform .15s, color .15s; }
.zeile:hover .z-pfeil { transform: translateX(3px); color: var(--fg); }
.z-text { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.z-name { font-weight: 650; font-size: 1.05rem; }
.z-info { color: var(--muted); font-size: .84rem; }
.z-preis { flex: none; min-width: 9rem; text-align: right; font-weight: 750; font-size: 1.2rem;
  font-variant-numeric: tabular-nums; }
.z-preis small { font-size: .62em; font-weight: 400; color: var(--muted); }
.z-sieger { flex: none; width: 7rem; display: flex; flex-direction: column; align-items: flex-start; gap: 3px; }
.z-sieger small { font-size: .78rem; color: var(--muted); font-variant-numeric: tabular-nums; }
.schild { display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  padding: 3px 10px; border-radius: 999px; background: var(--akzent); color: var(--auf-akzent); font-weight: 750; font-size: .9rem; }
.schild.gleich { background: var(--barbg); color: var(--muted); font-weight: 600; font-size: .78rem; }
.strecken li.skala .z-preis { text-align: right; }
@media (max-width: 560px) { .zeile { flex-wrap: wrap; gap: 6px 14px; } .z-text { flex-basis: 100%; }
  .gleis.klein { width: 170px; } .z-preis { margin-left: auto; min-width: 0; }
  .strecken li.skala { display: none; }
  .z-sieger { width: auto; flex-direction: row; align-items: center; gap: 8px; } }

/* Tabellen */
.tabelle { overflow-x: auto; background: var(--flaeche); border: 1px solid var(--line); border-radius: 14px; }
table { border-collapse: collapse; width: 100%; font-size: .92rem; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 10px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }
tr:last-child td { border-bottom: 0; }
thead th { font-size: .78rem; font-weight: 600; color: var(--muted); white-space: nowrap; }
td.zahl, th.zahl { text-align: right; white-space: nowrap; }
.billig { color: var(--akzent); font-weight: 750; }
.zeit { white-space: nowrap; }
td.vorlauf { font-weight: 650; white-space: nowrap; }
td.vorlauf .klein { font-weight: 400; }
.balken { display: inline-block; width: 48px; height: 5px; margin-left: 10px; vertical-align: middle; border-radius: 3px;
  background: linear-gradient(to right, var(--bar) var(--a), var(--barbg) var(--a)); }
/* Geteilter Balken in „Verkäufer im Vergleich“: dunkel = allein am billigsten, mittel = gleich billig, hell = teurer */
.stapel { display: flex; align-items: center; gap: 12px; white-space: nowrap; }
.stapel-balken { display: flex; width: 160px; flex: none; height: 10px; border-radius: 5px; overflow: hidden;
  background: var(--barbg); gap: 2px; }
.stapel-balken i, .stapel-legende i { display: block; height: 100%; }
.s-allein { background: var(--bar); }
.s-gleich { background: color-mix(in srgb, var(--bar) 45%, var(--barbg)); }
.s-teurer { background: var(--barbg); }
.stapel-text { font-variant-numeric: tabular-nums; }
.stapel-legende { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 0 0 10px; color: var(--muted); font-size: .85rem; }
.stapel-legende span { display: inline-flex; align-items: center; gap: 6px; }
.stapel-legende i { width: 12px; height: 12px; border-radius: 3px; border: 1px solid var(--line); }
.schild-leise { display: inline-block; margin-top: 4px; padding: 1px 8px; border: 1px solid var(--line);
  border-radius: 999px; color: var(--muted); font-size: .75rem; white-space: nowrap; }
/* Handy: jede Zeile eine Karte – Name über die ganze Breite, darunter Balken und „gegenüber …“ nebeneinander */
@media (max-width: 560px) {
  table.verk thead { display: none; }
  table.verk, table.verk tbody, table.verk td { display: block; width: auto; }
  table.verk tr { display: grid; grid-template-columns: 1fr auto; gap: 8px 12px; padding: 12px 14px;
    border-bottom: 1px solid var(--line); }
  table.verk tr:last-child { border-bottom: 0; }
  table.verk td { padding: 0; border: 0; }
  table.verk td:first-child { grid-column: 1 / -1; }
  table.verk td.gegen { align-self: end; text-align: right; }
  table.verk td.gegen::before { content: attr(data-label); display: block; color: var(--muted); font-size: .75rem; }
  .stapel { flex-direction: column; align-items: flex-start; gap: 4px; }
  .stapel-balken { width: 120px; }
}

/* Buchen */
.buchen { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 8px; }
.buchen a { display: inline-block; padding: 8px 14px; border: 1px solid var(--line); background: var(--flaeche);
  border-radius: 999px; color: var(--fg); text-decoration: none; font-weight: 600; font-size: .92rem; }
.buchen a::after { content: " \\2192"; color: var(--muted); }
.buchen a:hover { border-color: var(--fg); }
.buchen a.bester { background: var(--akzent); border-color: var(--akzent); color: var(--auf-akzent); }
.buchen a.bester::after, .buchen a.bester .klein { color: var(--auf-akzent); }
.buchen a.bester .klein { font-weight: 400; }

/* Suche, FAQ, Sprachwahl, Fuß */
.suche { width: 100%; max-width: 360px; padding: 10px 14px; margin: 0 0 14px; font: inherit; color: var(--fg);
  background: var(--flaeche); border: 1px solid var(--line); border-radius: 999px; outline: none; }
.suche:focus { border-color: var(--fg); }
.suche::placeholder { color: var(--muted); }
.weiter { margin: 14px 0 0; font-weight: 600; }
.befunde { margin: 0; padding-left: 1.2em; max-width: 72ch; }
.befunde li { margin: 0 0 10px; }
.faq h3 { margin: 24px 0 4px; }
.faq p { margin: 0; max-width: 70ch; }
.wahl { display: flex; gap: 10px; flex-wrap: wrap; margin: 28px 0; }
.wahl a { padding: 12px 24px; border: 1px solid var(--line); background: var(--flaeche); border-radius: 999px;
  color: var(--fg); text-decoration: none; font-weight: 650; font-size: 1.1rem; }
.wahl a.vorschlag { background: var(--akzent); border-color: var(--akzent); color: var(--auf-akzent); }
footer { color: var(--muted); font-size: .82rem; border-top: 1px solid var(--line); margin-top: 72px;
  padding-top: 16px; padding-bottom: 40px; }
footer a { color: var(--muted); }
code { font-size: .9em; }

/* Neue Gestaltung (Schalter UI in webseite.py); ohne die Klassen wirkungslos */
header.fest { position: sticky; top: 0; z-index: 10; background: var(--bg); padding-top: 12px; padding-bottom: 10px; }
@media (max-width: 560px) { header.fest { position: static; } }
header.fest { align-items: center; }
.sprache.tg { display: inline-flex; gap: 2px; padding: 3px; border: 1px solid var(--line); border-radius: 999px;
  background: var(--flaeche); }
.sprache.tg a, .sprache.tg strong { min-width: 2.6em; padding: 3px 10px; border-radius: 999px; text-align: center;
  font-size: .78rem; font-weight: 650; line-height: 1.4; letter-spacing: .03em; }
.sprache.tg a { color: var(--muted); }
.sprache.tg a:hover { color: var(--fg); background: var(--line); }
.sprache.tg strong { background: var(--fg); color: var(--bg); }
.unterzeile { margin: 14px 0 0; max-width: 62ch; color: var(--muted); font-size: 1.02rem; line-height: 1.55; }
.zahlenzeile { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 26px; margin: 22px 0 0; padding: 14px 0;
  border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); color: var(--muted); font-size: .9rem; }
.zahlenzeile b { color: var(--fg); font-size: 1.1rem; font-weight: 750; font-variant-numeric: tabular-nums; }
/* Handy: 2 × 2, Zahl über der Beschriftung, statt ungleichmäßig umzubrechen */
@media (max-width: 560px) {
  .zahlenzeile { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 18px; font-size: .82rem; line-height: 1.3; }
  .zahlenzeile span { display: flex; flex-direction: column; gap: 2px; }
  .zahlenzeile b { font-size: 1.25rem; } }
.suche.gross { max-width: none; padding: 14px 20px; font-size: 1.05rem; margin: 22px 0 0; }
main > p.tipp { margin: -6px 0 16px; }
.suche.gross + h2 { margin-top: 40px; }
/* Von/Nach-Suche wie in der DB-App: Kasten mit zwei Zeilen, links Punkte mit Linie, rechts Tausch-Knopf */
.vn { position: relative; display: flex; align-items: center; margin: 22px 0 0; background: var(--flaeche);
  border: 1px solid var(--line); border-radius: 16px; }
.vn:focus-within { border-color: var(--fg); }
.vn + h2 { margin-top: 40px; }
.vn-felder { flex: 1; min-width: 0; }
.vn-zeile { position: relative; display: flex; align-items: center; gap: 12px; padding: 0 8px 0 18px; cursor: text; }
.vn-zeile + .vn-zeile { border-top: 1px solid var(--line); margin-left: 44px; padding-left: 0; }
.vn-zeile + .vn-zeile .vn-punkt { position: absolute; left: -26px; }
.vn-punkt { flex: none; width: 10px; height: 10px; border: 2px solid var(--fg); border-radius: 50%; background: var(--flaeche); }
.vn-punkt.ziel { background: var(--fg); }
/* gestrichelte Linie zwischen den Punkten */
.vn-felder::before { content: ""; position: absolute; left: 24px; top: 50%; height: 36px; margin-top: -18px;
  border-left: 2px dotted var(--muted); }
.vn-l { flex: none; width: 3.2em; color: var(--muted); font-size: .85rem; font-weight: 600; }
.vn input { flex: 1; min-width: 0; padding: 15px 0; font: inherit; font-size: 1.05rem; color: var(--fg);
  background: transparent; border: 0; outline: none; }
.vn input::placeholder { color: var(--muted); }
.vn input::-webkit-search-cancel-button { cursor: pointer; }
.vn-tausch { flex: none; width: 42px; height: 42px; margin: 0 12px 0 4px; border-radius: 50%; border: 1px solid var(--line);
  background: var(--bg); color: var(--fg); font-size: 1.25rem; line-height: 1; cursor: pointer; }
.vn-tausch:hover, .vn-tausch:focus-visible { border-color: var(--fg); }
#gegen { margin: 0 0 8px; }
#umstieg { margin: 0 0 16px; }
.umst { margin: 0 0 14px; border: 1px solid var(--line); border-radius: 12px; padding: 8px 10px 2px; }
.umst-kopf { display: flex; justify-content: space-between; gap: 8px; font-size: .85rem; color: var(--muted); margin: 0 0 4px; }
.umst-kopf b { color: var(--fg); }
.umst .strecken { margin: 0; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 14px; }
.chip .anz { color: var(--muted); font-variant-numeric: tabular-nums; margin-left: 2px; }
.chip[aria-pressed="true"] .anz { color: inherit; opacity: .7; }
#anzahl { margin: 0 0 8px; }
.chip { font: inherit; font-size: .85rem; padding: 6px 13px; border-radius: 999px; border: 1px solid var(--line);
  background: var(--flaeche); color: var(--fg); cursor: pointer; }
.chip[aria-pressed="true"] { background: var(--fg); color: var(--bg); border-color: var(--fg); }
.weitere { margin: 26px 0 22px; text-align: center; }
.weitere[open] { text-align: left; }
.weitere[open] summary { display: flex; width: max-content; margin: 0 auto 14px; }
.weitere summary { list-style: none; display: inline-flex; align-items: center; gap: 10px; cursor: pointer;
  padding: 11px 20px; border: 1px solid var(--line); border-radius: 999px; background: var(--flaeche);
  color: var(--fg); font-weight: 650; font-size: .95rem; }
.weitere summary::-webkit-details-marker { display: none; }
.weitere summary::after { content: "›"; display: inline-block; font-size: 1.25rem; line-height: 1; margin-top: -3px;
  color: var(--muted); transition: transform .15s; }
.weitere[open] summary::after { transform: rotate(90deg); }
.weitere summary:hover { border-color: var(--fg); }
.z-spart { display: block; font-size: .72rem; font-weight: 600; color: var(--muted); letter-spacing: 0; }
.eingeklappt tr.zu { display: none; }
.mehr-knopf { font: inherit; font-size: .88rem; margin: 10px 0 0; padding: 7px 15px; border-radius: 999px;
  border: 1px solid var(--line); background: var(--flaeche); color: var(--fg); cursor: pointer; }
.mehr-knopf:hover { border-color: var(--fg); }
.feedback { display: grid; gap: 18px; max-width: 560px; margin: 28px 0 0; }
.feedback fieldset { border: 0; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px; }
.feedback legend, .feedback label { font-weight: 600; font-size: .92rem; }
.feedback legend { margin-bottom: 8px; }
.feedback label { display: grid; gap: 6px; }
.feedback fieldset label { display: inline-flex; align-items: center; gap: 6px; font-weight: 400;
  padding: 6px 13px; border: 1px solid var(--line); border-radius: 999px; background: var(--flaeche); cursor: pointer; }
.feedback fieldset label:has(input:checked) { border-color: var(--fg); }
.feedback textarea, .feedback input[type=email] { font: inherit; font-weight: 400; color: var(--fg); background: var(--flaeche);
  border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; width: 100%; box-sizing: border-box; }
.feedback textarea { min-height: 9em; resize: vertical; }
.feedback textarea:focus, .feedback input[type=email]:focus { outline: none; border-color: var(--fg); }
.feedback button { justify-self: start; font: inherit; font-weight: 600; padding: 10px 22px; border-radius: 999px;
  border: 1px solid var(--akzent); background: var(--akzent); color: var(--auf-akzent); cursor: pointer; }
.feedback button:disabled { opacity: .6; cursor: default; }
.feedback .topf { position: absolute; left: -9999px; width: 1px; height: 1px; overflow: hidden; }
.danke, .fb-fehler { margin: 0; padding: 14px 18px; border: 1px solid var(--line); border-radius: 14px; background: var(--flaeche); }
.danke { display: none; margin-top: 28px; }
.danke:target, .danke.da { display: block; }
.danke:target + form, .danke.da + form { display: none; }
"""


def aktuell(stand, lang):
    """Hinweis ganz oben: täglich neu, mit Datum der letzten Abfrage."""
    d = f'<time datetime="{stand.isoformat()}">{datum(stand, lang)}</time>'
    return f'<p class="aktuell">{T[lang]["aktuell"].format(d=d)}</p>'


def anbieter_html():
    name, strasse, ort, mail = (esc(x) for x in ANBIETER)
    return f"{name}<br>{strasse}<br>{ort}<br>E-Mail: <a href=\"mailto:{mail}\">{mail}</a>"


def datenschutz(lang):
    """Datenschutzerklärung aus skripte/datenschutz_<lang>.html; GoatCounter-Abschnitte nur, wenn die Zählung an ist."""
    text = (Path(__file__).with_name(f"datenschutz_{lang}.html")).read_text(encoding="utf-8")
    if GOATCOUNTER:
        if not GOATCOUNTER_ANBIETER:
            sys.exit("GOATCOUNTER_ANBIETER in webseite.py eintragen (Betreiber von GoatCounter für die Datenschutzerklärung)")
        text = text.replace("{goatcounter_anbieter}", esc(GOATCOUNTER_ANBIETER[lang]))
    else:
        text = re.sub(r"<!--goatcounter-->.*?<!--/goatcounter-->", "", text, flags=re.S)
    if not AFFILIATE:
        text = re.sub(r"<!--affiliate-->.*?<!--/affiliate-->", "", text, flags=re.S)
    return text.replace("{anbieter}", anbieter_html())


def feedback_seite(lang):
    """Feedback-Formular; schickt an den Worker (worker.js, POST /api/feedback), der in D1 speichert.
    Ohne JavaScript leitet der Worker auf feedback.html#danke weiter."""
    t = T[lang]
    arten = "".join(f'<label><input type="radio" name="art" value="{k}"{" checked" if k == "wunsch" else ""}> '
                    f'{esc(v)}</label>' for k, v in t["fb_arten"].items())
    mail = esc(ANBIETER[3])
    return f"""<h1>{t['feedback']}</h1>
<p>{esc(t['fb_text'])}</p>
<p class="danke" id="danke" role="status">{esc(t['fb_danke'])}</p>
<form class="feedback" method="post" action="/api/feedback">
<input type="hidden" name="sprache" value="{lang}">
<input type="hidden" name="zurueck" value="">
<fieldset><legend>{esc(t['fb_art'])}</legend>{arten}</fieldset>
<label>{esc(t['fb_nachricht'])}<textarea name="nachricht" required minlength="3" maxlength="4000"></textarea></label>
<label>{esc(t['fb_email'])}<input type="email" name="email" maxlength="200" autocomplete="email"></label>
<div class="topf" aria-hidden="true"><label>Website<input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>
<p class="fb-fehler" hidden>{esc(t['fb_fehler'])} <a href="mailto:{mail}">{mail}</a></p>
<button type="submit">{esc(t['fb_senden'])}</button>
<p class="klein">{t['fb_hinweis']}</p>
</form>
<script>
(function () {{
  var form = document.querySelector(".feedback"), knopf = form.querySelector("button"), fehler = form.querySelector(".fb-fehler");
  try {{
    var r = document.referrer && new URL(document.referrer);
    if (r && r.origin === location.origin) form.zurueck.value = r.pathname;
  }} catch (e) {{}}
  form.addEventListener("submit", function (ev) {{
    ev.preventDefault();
    knopf.disabled = true; knopf.textContent = {json.dumps(t['fb_sendet'])}; fehler.hidden = true;
    fetch(form.action, {{ method: "POST", body: new FormData(form), headers: {{ Accept: "application/json" }} }})
      .then(function (a) {{ if (!a.ok) throw a; return a.json(); }})
      .then(function () {{ document.getElementById("danke").classList.add("da"); }})
      .catch(function () {{ fehler.hidden = false; knopf.disabled = false; knopf.textContent = {json.dumps(t['fb_senden'])}; }});
  }});
}})();
</script>
"""


def zaehlung():
    """GoatCounter-Skript (ohne Cookies); zeigt u. a., von welcher Seite Besucher kommen, z. B. chatgpt.com."""
    if not GOATCOUNTER:
        return ""
    return (f'<script data-goatcounter="https://{GOATCOUNTER}.goatcounter.com/count" async '
            f'src="https://gc.zgo.at/count.js"></script>\n')


def icons(pre):
    """Website-Icon (Dateien aus skripte/favicon/, erzeugt von favicon_erzeugen.py)."""
    return (f'<link rel="icon" href="{pre}favicon.ico" sizes="48x48">\n'
            f'<link rel="icon" href="{pre}favicon.svg" type="image/svg+xml">\n'
            f'<link rel="apple-touch-icon" href="{pre}apple-touch-icon.png">\n')


def stil_url():
    """stil.css mit Versionsanhang aus dem Inhalt: Ändert sich das CSS, laden Browser es sofort neu."""
    if not UI["frisch"]:
        return "stil.css"
    return f"stil.css?v={hashlib.md5(CSS.encode('utf-8')).hexdigest()[:8]}"


def seite(lang, titel, beschreibung, inhalt, pfade):
    """pfade: {sprache: pfad derselben Seite in dieser Sprache}, z. B. {'de': 'de/strecken/x.html', 'en': ...}."""
    t = T[lang]
    pre = "../" * pfade[lang].count("/")
    alternates = "".join(f'<link rel="alternate" hreflang="{l}" href="{ADRESSE}/{p}">\n' for l, p in pfade.items())
    alternates += f'<link rel="alternate" hreflang="x-default" href="{ADRESSE}/{pfade["en"]}">\n'
    sprachwahl = ("" if UI["kopf_fest"] else " | ").join(
        f"<strong>{l.upper()}</strong>" if l == lang else
        f"<a href='{pre}{p}' hreflang='{l}' lang='{l}'>{l.upper()}</a>" for l, p in pfade.items())
    sprach_cls, kopf_cls = ("sprache tg", " class='fest'") if UI["kopf_fest"] else ("sprache", "")
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titel)}</title>
<meta name="description" content="{esc(beschreibung)}">
<link rel="canonical" href="{ADRESSE}/{pfade[lang]}">
{alternates}{icons(pre)}<link rel="stylesheet" href="{pre}{stil_url()}">
<script>try {{ localStorage.setItem("sprache", "{lang}"); }} catch (e) {{}}</script>
</head>
<body>
<header{kopf_cls}><div><a class="marke" href="{pre}{lang}/index.html">same<span class="punkt">·</span>train<span class="untertitel">{t['titel']}</span></a>
<nav><a href="{pre}{lang}/index.html">{t['nav_alle']}</a> · <a href="{pre}{lang}/{t['datei_ergebnisse']}.html">{t['nav_ergebnisse']}</a> · <a href="{pre}{lang}/methodik.html">{t['nav_methodik']}</a></nav></div>
<div class="{sprach_cls}">{sprachwahl}</div></header>
<main>
{inhalt}
</main>
<footer>{t['fuss']} · <a href="{pre}{lang}/methodik.html">{t['methodik']}</a> ·
<a href="{pre}daten/vergleich.csv">{t['rohdaten']}</a> · <a href="{pre}{lang}/impressum.html">{t['impressum']}</a> ·
<a href="{pre}{lang}/datenschutz.html">{t['datenschutz']}</a> · <a href="{pre}{lang}/feedback.html">{t['feedback']}</a></footer>
{zaehlung()}</body>
</html>
"""


def verkaeufer_link(verk, zusatz="", cls="", url=""):
    """Link zur Seite des Verkäufers (oder zu url, z. B. der fertigen Suche); ist ein Provisionslink hinterlegt,
    dieser mit * hinter dem Namen und rel="sponsored"."""
    klasse = f" class='{cls}'" if cls else ""
    if verk in AFFILIATE:
        return f"<a href='{esc(AFFILIATE[verk])}' rel='sponsored noopener'{klasse}>{esc(name(verk))}*{zusatz}</a>"
    return f"<a href='{esc(url) or VERKAEUFER[verk][1]}' rel='nofollow noopener'{klasse}>{esc(name(verk))}{zusatz}</a>"


# Verkäufer, deren Suche sich direkt über die Adresse öffnen lässt: Kürzel in strecken.csv -> Name in vergleich.csv
SUCHLINK_SEITEN = {"db": "bahn.de", "eurostar": "eurostar.com", "elron": "elron.ee"}


def suchlinks():
    """{(Strecke, Verkäufer): Adresse mit {datum}} aus strecken.csv; bahn.de aus dem Adressen-Zwischenspeicher,
    Eurostar mit den Bahnhofsnummern aus eurostar.py, Elron mit den Bahnhofsnamen."""
    try:
        db = json.loads((DATEN / "bahn_de_adressen.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        db = {}
    eurostar = {}
    for knoten in ast.parse((SKRIPTE / "eurostar.py").read_text(encoding="utf-8")).body:
        if isinstance(knoten, ast.Assign) and getattr(knoten.targets[0], "id", "") == "STATIONS":
            eurostar = ast.literal_eval(knoten.value)
    links = {}
    with open(STRECKEN, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            strecke, a, b, seite = r["strecke"].replace(" - ", " – "), r["start"], r["ziel"], r["seite"]
            if seite == "db" and f"{a}|{b}" in db:
                url = re.sub(r"hd=[^&]*", "hd={datum}T08:00:00", db[f"{a}|{b}"])
            elif seite == "eurostar" and a in eurostar and b in eurostar:
                url = (f"https://www.eurostar.com/search/de-de?adult=1&origin={eurostar[a]}"
                       f"&destination={eurostar[b]}&outbound={{datum}}")
            elif seite == "elron":
                url = f"https://elron.pilet.ee/en/otsing/{quote(a)}/{quote(b)}/{{datum}}"
            else:
                continue
            links[(strecke, SUCHLINK_SEITEN[seite])] = url
    return links


SUCHLINKS = {}


def zug_tabelle(verbindungen, stat, lang):
    """Tabelle der Züge eines Abfragetags; Spalten nur für Verkäufer, die an diesem Tag einen Preis hatten,
    in der Reihenfolge der Verkäufertabelle. Innerhalb des Tags nach Vorlauf, dann nach Abfahrt."""
    t = T[lang]
    verkaeufer = [verk for verk, _ in stat if any(verk in v["preise"] for v in verbindungen)]
    kopf = "".join(f"<th class='zahl'>{esc(name(v))}</th>" for v in verkaeufer)
    zug_zeilen = []
    # Bei vielen Zügen nur die 5 mit dem größten Preisunterschied zeigen, der Rest ist aufklappbar
    # (die Zeilen bleiben im HTML, eingeklappt wird erst per JavaScript)
    spanne = lambda v: max(p[0] for p in v["preise"].values()) / min(p[0] for p in v["preise"].values())
    einklappen = UI["zuege_einklappen"] and len(verbindungen) > 7
    sichtbar = {id(v) for v in sorted(verbindungen, key=spanne, reverse=True)[:5]} if einklappen else set()
    for v in sorted(verbindungen, key=lambda v: (v["vorlauf"], v["abfahrt"])):
        low = min(p[0] for p in v["preise"].values())
        zellen = []
        for verk in verkaeufer:
            if verk not in v["preise"]:
                zellen.append("<td class='zahl klein'>–</td>")
                continue
            eur, original, _, tarif = v["preise"][verk]
            orig = ""
            if original:
                orig = f"{original[0].replace(',', '.') if lang == 'en' else original[0]} {original[1]}"
            if tarif == "inkl. geschätzter Servicegebühr" and lang == "en":
                tarif = "incl. estimated service fee"
            info = " · ".join(x for x in (orig, tarif) if x)
            preis = euro(eur, lang)
            if eur <= low + 0.005:
                preis = f"<span class='billig'>{preis}</span>"
            zellen.append(f"<td class='zahl'>{preis}"
                          + (f"<div class='klein'>{esc(info)}</div>" if info else "") + "</td>")
        reise = date.fromisoformat(v["reise_datum"])
        vorlauf = ({0: t["am_reisetag"], 1: t["tag_vorher"]}.get(v["vorlauf"])
                   or t["tage_vorher"].format(n=v["vorlauf"]))
        zu = " class='zu'" if einklappen and id(v) not in sichtbar else ""
        zug_zeilen.append(f"<tr{zu}><td class='vorlauf'>{vorlauf}<div class='klein'>"
                          f"{t['reise_abfrage'].format(r=datum_kurz(reise, lang), a=datum_kurz(v['abfrage'], lang))}"
                          f"</div></td>"
                          f"<td><span class='zeit'>{esc(v['abfahrt'])}–{esc(v['ankunft'])}</span>"
                          f"<div class='klein'>{esc(v['zuege'])}</div></td>"
                          + "".join(zellen) + "</tr>")
    tabelle = (f"<div class='tabelle'><table><thead><tr><th>{t['sp_reisetag']}</th><th>{t['sp_zug']}</th>" + kopf
               + "</tr></thead><tbody>" + "".join(zug_zeilen) + "</tbody></table></div>\n")
    if not einklappen:
        return tabelle
    alle, weniger = t["alle_zeigen"].format(n=len(verbindungen)), t["weniger_zeigen"]
    return (tabelle + f"<button class='mehr-knopf' type='button' hidden data-alle='{esc(alle)}' "
            f"data-weniger='{esc(weniger)}'>{esc(alle)}</button>\n"
            "<script>(function () { var s = document.currentScript, b = s.previousElementSibling, "
            "d = b.previousElementSibling; d.classList.add('eingeklappt'); b.hidden = false; "
            "b.onclick = function () { var zu = d.classList.toggle('eingeklappt'); "
            "b.textContent = zu ? b.dataset.alle : b.dataset.weniger; }; })();</script>\n")


def streckenseite(strecke, verbindungen, lang):
    t = T[lang]
    stat = statistik(verbindungen)
    abfragen = [v["abfrage"] for v in verbindungen]
    stand = max(abfragen)
    s = strecke_in(strecke, lang)
    satz = kurzaussage(strecke, verbindungen, stat, lang)

    best = stat[0][0]
    zeilen = []
    # Verkäufer mit nur wenigen Zügen (z. B. einmal kurz mitgetestet) bekommen keine eigene Zeile, sondern stehen
    # gesammelt unter der Tabelle
    wenige = [(verk, e) for verk, e in stat
              if UI["verkaeufer_wenig"] and verk != best and e["n"] < WENIG_VERKAEUFER_ZUEGE]
    gestrichen_da = luecke_da = False
    for verk, e in stat:
        if (verk, e) in wenige:
            continue
        f = statistics.median(e["faktoren"])
        if verk == best:
            gegen = "–"
        else:
            n, q = gegenueber(verbindungen, best, verk)
            gegen = t["gegen_wert"].format(p=prozent(q, lang), n=n) if n else f"<span class='klein'>{t['kein_gemeinsam']}</span>"
        # Hinweis, wenn die 6er-Regel den Verkäufer gestrichen hat und seitdem keine Preise mehr dazukamen
        hinweis = ""
        if (strecke, verk) in GESTRICHEN:
            seit, n_abfragen = GESTRICHEN[(strecke, verk)]
            if max(v["abfrage"] for v in verbindungen if verk in v["preise"]) <= seit:
                if UI["gestrichen_kurz"]:
                    # nur ein kleines Schild; die Erklärung steht einmal unter der Tabelle
                    hinweis = f"<div><span class='schild-leise'>{esc(t['gestrichen_kurz'].format(d=datum(seit, lang)))} *</span></div>"
                    gestrichen_da = True
                else:
                    hinweis = f"<div class='klein'>{esc(t['gestrichen'].format(d=datum(seit, lang), n=n_abfragen))}</div>"
        # Hinweis, wenn ein Verkäufer noch abgefragt wird, aber an mindestens LUECKE_TAGE späteren Abfragetagen der
        # Strecke keine Preise mehr lieferte (z. B. ÖBB ab 27.10.2026 wegen „Forbidden“, ČD ab 21.10. gesperrt)
        elif (strecke, verk) in IN_LISTE and (strecke, verk) in LETZTE_PREISE:
            zuletzt = LETZTE_PREISE[(strecke, verk)]
            if len({a for a in ABFRAGETAGE[strecke] if a > zuletzt}) >= LUECKE_TAGE:
                hinweis = f"<div><span class='schild-leise'>{esc(t['luecke_kurz'].format(d=datum(zuletzt, lang)))} †</span></div>"
                luecke_da = True
        # Je Zug genau eine von drei Möglichkeiten, die drei Zahlen ergeben zusammen die Zahl der Züge des Verkäufers
        kopf_zelle = (f"<td>{esc(name(verk))}<div class='klein'>{esc(t['rolle'].get(e['rolle'], ''))} · "
                      f"{e['n']} {(t['sp_zug'] if e['n'] == 1 else t['sp_anzahl']) if lang == 'de' else ('train' if e['n'] == 1 else 'trains')}"
                      f"</div>{hinweis}</td>")
        if UI["verkaeufer_balken"]:
            # data-label: auf dem Handy (Kartenansicht ohne Tabellenkopf) steht „gegenüber DB“ direkt vor dem Wert
            zeilen.append(f"<tr>{kopf_zelle}<td>{stapel(e, lang)}</td>"
                          f"<td class='zahl gegen' data-label='{'' if verk == best else esc(t['sp_gegen'].format(v=kurzname(best)))}'>"
                          f"{gegen}</td></tr>")
        else:
            zeilen.append(f"<tr>{kopf_zelle}"
                          f"<td class='zahl'>{e['allein']}{balken(e['allein'] / e['n'])}</td>"
                          f"<td class='zahl'>{e['gleich']}{balken(e['gleich'] / e['n'])}</td>"
                          f"<td class='zahl'>{e['teurer']}{balken(e['teurer'] / e['n'])}</td>"
                          f"<td class='zahl'>{gegen}</td></tr>")
    if UI["verkaeufer_balken"]:
        legende = "".join(f"<span><i class='{c}'></i>{t[k]}</span>"
                          for c, k in (("s-allein", "sp_allein"), ("s-gleich", "sp_gleich"), ("s-teurer", "sp_teurer")))
        spalten = f"<th>{t['sp_wie_oft_billig']}</th>"
        vorspann, tab_cls = f"<div class='stapel-legende'>{legende}</div>", " class='verk'"
    else:
        spalten = (f"<th class='zahl'>{t['sp_allein']}</th><th class='zahl'>{t['sp_gleich']}</th>"
                   f"<th class='zahl'>{t['sp_teurer']}</th>")
        vorspann, tab_cls = "", ""
    uebersicht = (f"{vorspann}<div class='tabelle'><table{tab_cls}><thead><tr><th>{t['sp_verkaeufer']}</th>{spalten}"
                  f"<th class='zahl'>{t['sp_gegen'].format(v=esc(name(best)))}</th>"
                  f"</tr></thead><tbody>" + "".join(zeilen) + "</tbody></table></div>")
    if wenige:
        zuege = lambda n: f"{n} {(t['sp_zug'] if n == 1 else t['sp_anzahl']) if lang == 'de' else ('train' if n == 1 else 'trains')}"
        liste = ", ".join(f"{esc(name(verk))} ({zuege(e['n'])})" for verk, e in wenige)
        uebersicht += f"<p class='klein'>{t['wenig_verk'].format(v=liste)}</p>"
    if gestrichen_da:
        uebersicht += f"<p class='klein'>* {esc(t['gestrichen_erkl'])}</p>"
    if luecke_da:
        uebersicht += f"<p class='klein'>† {esc(t['luecke_erkl'])}</p>"

    # Eine Tabelle je Abfragetag, neueste oben; Spalten nur für Verkäufer mit Preis an diesem Tag
    # (z. B. fehlen gestrichene oder erst später aufgenommene Verkäufer dann ganz statt als Spalte voller „–“)
    tage = collections.defaultdict(list)
    for v in verbindungen:
        tage[v["abfrage"]].append(v)
    zuege = ""
    for tag in sorted(tage, reverse=True):
        zuege += f"<h3>{t['h3_abfrage'].format(d=datum(tag, lang))}</h3>\n" + zug_tabelle(tage[tag], stat, lang)

    # Meist billigster Verkäufer zuerst und hervorgehoben (nicht, wenn alle gleich teuer sind)
    hervor = best if groesster_faktor(verbindungen) >= 1.005 else None
    # Wo möglich direkt zur Suche für den Reisetag des „ab“-Angebots, sonst zur Startseite des Verkäufers
    such_datum = ab_preis(verbindungen)[1]["reise_datum"]
    such = {verk: SUCHLINKS[(strecke, verk)].replace("{datum}", such_datum)
            for verk, _ in stat if (strecke, verk) in SUCHLINKS and verk not in AFFILIATE}
    buchen = "".join("<li>" + (verkaeufer_link(verk, f" <span class='klein'>· {t['buchen_bester']}</span>", "bester",
                                               such.get(verk, ""))
                               if verk == hervor else verkaeufer_link(verk, url=such.get(verk, "")))
                     + "</li>" for verk, _ in stat if verk in VERKAEUFER)
    # Wer insgesamt am billigsten fährt, aber im Vergleich derselben Züge fehlt (z. B. OUIGO), auch verlinken
    g_buchen = gesamt(strecke)
    if g_buchen and g_buchen[0] not in dict(stat) and g_buchen[0] in VERKAEUFER:
        buchen += f"<li>{verkaeufer_link(g_buchen[0])}</li>"
    such_hinweis = (t["erkl_suchlink"].format(d=datum(date.fromisoformat(such_datum), lang),
                                              v=", ".join(esc(name(v)) for v in such)) if such else "")
    provision = any(verk in AFFILIATE for verk, _ in stat)
    stand_text = t["stand_strecke"].format(n=len(verbindungen), von=datum(min(abfragen), lang), bis=datum(stand, lang))
    ab_eur, ab_v, ab_verk = ab_preis(verbindungen)
    ab_link = verkaeufer_link(ab_verk) if ab_verk in VERKAEUFER else esc(name(ab_verk))
    ab_info = t["ab_info"].format(v=ab_link, d=datum(date.fromisoformat(ab_v["reise_datum"]), lang),
                                  z=f"{esc(ab_v['abfahrt'])}–{esc(ab_v['ankunft'])}", a=datum(ab_v["abfrage"], lang))
    g = gesamt(strecke)
    gesamt_block = ""
    if g:
        g_link = verkaeufer_link(g[0]) if g[0] in VERKAEUFER else esc(name(g[0]))
        eigene = (f"<p class='klein'>{esc(t['gesamt_eigene'].format(v=name(g[0])))}</p>"
                  if g[0] not in dict(stat) else "")
        gesamt_block = (f"<div class='ab gesamt'><p class='ab-preis'><span>{t['gesamt_titel']} · {t['sp_ab']}</span> "
                        f"{euro(g[3], lang, 0 if g[3] >= 100 else 2)}</p>"
                        f"<p class='ab-info'>{t['gesamt_info'].format(v=g_link, k=g[1], n=g[2])}</p>{eigene}</div>")
    bz = beispielzug(verbindungen)
    gleis_block = (f"<figure class='gleis-block'><figcaption>{t['gleis_titel'].format(n=len(bz['preise']))}</figcaption>"
                   + gleis(bz, lang, cls="breit") + gleis(bz, lang, breite=340, cls="schmal")
                   + f"<p class='klein'>{t['gleis_info'].format(z=esc(bz['abfahrt'] + '–' + bz['ankunft'] + (' · ' + bz['zuege'] if bz['zuege'] else '')), d=datum(date.fromisoformat(bz['reise_datum']), lang), a=datum(bz['abfrage'], lang))}</p></figure>")
    inhalt = f"""{aktuell(stand, lang)}
<h1>{esc(t['h1_strecke'].format(s=pfeil(s)))}</h1>
<p class="stand">{stand_text}</p>
{gleis_block}
<div class="ab"><p class="ab-preis"><span>{t['sp_ab_zug'] if gesamt_block else t['sp_ab']}</span> {euro(ab_eur, lang, 0 if ab_eur >= 100 else 2)}</p>
<p class="ab-info">{ab_info}</p></div>
{gesamt_block}
<p class="kurz">{esc(satz)}</p>
<h2>{t['h2_buchen']}</h2>
<ul class="buchen">{buchen}</ul>
<p class="klein">{t['erkl_buchen']}{such_hinweis}</p>
{f'<p class="klein">{t["provision"]}</p>' if provision else ''}
<h2>{t['h2_verkaeufer']}</h2>
{uebersicht}
<p class="klein">{t['erkl_verkaeufer2'].format(v=esc(name(best)))}</p>
{sncf_abschnitt(strecke, verbindungen, lang)}{vorlauf_abschnitt(strecke, verbindungen, lang)}<h2>{t['h2_zuege']}</h2>
{zuege}
<p class="klein">{t['erkl_zuege']}</p>
"""
    pfade = {l: strecken_pfad(strecke, l) for l in SPRACHEN}
    return seite(lang, f"{t['titel_strecke'].format(s=s)} – {t['titel']}", satz, inhalt, pfade), stat, stand


def sncf_spanne(strecke):
    """[(Zugart, min, max)] des vollen Tarifs 2. Klasse aus SNCF Open Data (skripte/sncf_tarife_holen.py), nur für
    Strecken in SNCF_STRECKEN. TGV INOUI steht dort je Bahnhofspaar nur in einer Richtung, gilt aber für beide."""
    if strecke not in SNCF_STRECKEN or not SNCF_TARIFE.exists():
        return []
    a, b = SNCF_STRECKEN[strecke]
    spannen = {}
    with open(SNCF_TARIFE, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if ({r["gare_origine"], r["gare_destination"]} == {a, b} and r["classe"] == "2"
                    and r["profil_tarifaire"] == "Tarif Normal" and r["transporteur"] in SNCF_ZUGARTEN):
                spannen[SNCF_ZUGARTEN[r["transporteur"]]] = (float(r["prix_minimum"]), float(r["prix_maximum"]))
    return [(art, *spannen[art]) for art in SNCF_ZUGARTEN.values() if art in spannen]


def sncf_abschnitt(strecke, verbindungen, lang):
    """Abschnitt mit der offiziellen SNCF-Preisspanne für Strecken, auf denen SNCF Connect fehlt."""
    spannen = sncf_spanne(strecke)
    if not spannen:
        return ""
    t = T[lang]
    stand = SNCF_TARIFE_STAND.read_text(encoding="utf-8").strip() if SNCF_TARIFE_STAND.exists() else ""
    geld = lambda x: euro(x, lang, 0 if x == int(x) else 2)
    liste = "".join(f"<li><strong>{art}</strong>: {geld(lo)} – {geld(hi)}</li>" for art, lo, hi in spannen)
    median = statistics.median(min(p[0] for p in v["preise"].values()) for v in verbindungen)
    quelle = t["sncf_quelle"].format(d=datum(date.fromisoformat(stand), lang) if stand else "–")
    return (f"<h2>{t['h2_sncf']}</h2>\n<p>{t['sncf_text']}</p>\n<ul>{liste}</ul>\n"
            f"<p>{t['sncf_median'].format(m=geld(round(median, 2)))}</p>\n"
            # 1.2.Train: Betreiber Jean-Baptiste Marie half mit dem Datensatz; die Seite wird bewusst nicht abgefragt
            f"<p>{t['sncf_buchen'].format(l='<a href=\"https://www.12train.com\" rel=\"noopener\">1.2.Train</a>')}</p>\n"
            f"<p class='klein'>{esc(quelle)}</p>\n")


def faq_fragen(routes, stand, lang):
    """Häufige Fragen mit Antworten aus den Daten: [(frage, antwort)]."""
    t = T[lang]
    alle = [v for vs in routes.values() for v in vs]
    fragen = []

    def heim_preis(v):
        sz = [p[0] for p in v["preise"].values() if p[2] == "Start/Ziel"]
        return min(sz) if sz else None

    mit_heim = [v for v in alle if heim_preis(v) is not None]
    if mit_heim:
        k = sum(1 for v in mit_heim if heim_preis(v) <= min(p[0] for p in v["preise"].values()) + 0.005)
        fragen.append((t["faq_heim_f"], t["faq_heim_a"].format(p=zahl(100 * k / len(mit_heim), lang, 0), k=k,
                                                               n=len(mit_heim))))

    fremd = ("Durchgang", "kein Bezug")
    mit_fremd = [v for v in mit_heim if any(p[2] in fremd for p in v["preise"].values())]
    if mit_fremd:
        billiger = [v for v in mit_fremd
                    if any(p[2] in fremd and p[0] < heim_preis(v) - 0.005 for p in v["preise"].values())]
        if billiger:
            top = collections.Counter(v["strecke"] for v in billiger).most_common(3)
            antwort = t["faq_fremd_ja"].format(k=len(billiger), n=len(mit_fremd),
                                               p=zahl(100 * len(billiger) / len(mit_fremd), lang, 0),
                                               s=", ".join(strecke_in(s, lang) for s, _ in top))
        else:
            antwort = t["faq_fremd_nein"].format(n=len(mit_fremd))
        faktoren = [p[0] / min(q[0] for q in v["preise"].values()) for v in alle
                    for p in v["preise"].values() if p[2] == "kein Bezug"]
        if faktoren:
            antwort += t["faq_fremd_teuer"].format(f=zahl(statistics.median(faktoren), lang))
        fragen.append((t["faq_fremd_f"], antwort))

    vermittler = sorted({verk for v in alle for verk, p in v["preise"].items() if p[2] == "Vermittler"})
    if vermittler:
        faktoren, b = [], 0
        for v in alle:
            low = min(p[0] for p in v["preise"].values())
            for p in v["preise"].values():
                if p[2] == "Vermittler":
                    faktoren.append(p[0] / low)
                    b += p[0] <= low + 0.005
        f = statistics.median(faktoren)
        namen = ", ".join(name(x) for x in vermittler)
        fragen.append((t["faq_vermittler_f"].format(v=namen),
                       t["faq_vermittler_a"].format(start=t["meist_ja"] if f > 1.02 else t["nicht_unbedingt"],
                                                    v=namen, b=b, n=len(faktoren), p=prozent(f, lang).lstrip("+"))))

    # Früh gegen spät: je Strecke Median des billigsten Preises bis 2 Wochen vs. mehr als 4 Wochen vorher
    verhaeltnisse = []
    for vs in routes.values():
        stufen = nach_vorlauf(vs)
        if 1 in stufen and 3 in stufen:
            verhaeltnisse.append(statistics.median(stufen[1]["preise"]) / statistics.median(stufen[3]["preise"]))
    if verhaeltnisse:
        q = statistics.median(verhaeltnisse)
        p = zahl(abs(q - 1) * 100, lang, 0)
        fragen.append((t["faq_wann_f"], t["faq_wann_a"].format(
            start=t["frueh"] if q > 1.05 else t["egal"], r=len(verhaeltnisse),
            p=(t["teurer"] if q >= 1 else t["billiger"]).format(p=p))))
    else:
        fragen.append((t["faq_wann_f"], t["faq_wann_leer"]))

    fragen.append((t["faq_aktuell_f"], t["faq_aktuell_a"].format(d=datum(stand, lang))))
    return fragen


def faq(routes, stand, lang):
    """Häufige Fragen als HTML und als FAQPage-Daten für Suchmaschinen."""
    t = T[lang]
    fragen = faq_fragen(routes, stand, lang)
    html_teil = "".join(f"<h3>{esc(f)}</h3>\n<p>{esc(a)}</p>\n" for f, a in fragen)
    daten = {"@context": "https://schema.org", "@type": "FAQPage", "inLanguage": lang,
             "mainEntity": [{"@type": "Question", "name": f, "acceptedAnswer": {"@type": "Answer", "text": a}}
                            for f, a in fragen]}
    json_ld = json.dumps(daten, ensure_ascii=False).replace("</", "<\\/")
    return (f"<h2>{t['h2_faq']}</h2>\n<div class='faq'>\n{html_teil}</div>\n"
            f'<script type="application/ld+json">{json_ld}</script>\n')


def heimpreis(v):
    """Billigster Preis einer Bahn des Start- oder Ziellandes für diese Verbindung (None, wenn keine dabei war)."""
    sz = [p[0] for p in v["preise"].values() if p[2] == "Start/Ziel"]
    return min(sz) if sz else None


def ergebnisseite(routes, reihenfolge, stats, stand, lang):
    """Die wichtigsten Zahlen über alle Strecken auf einer Seite, zum Verlinken und Zitieren."""
    t = T[lang]
    alle = [v for s in reihenfolge for v in routes[s]]
    r = len(reihenfolge)
    link = lambda s: f"<a href='{t['ordner']}/{slug(strecke_in(s, lang))}.html'>{esc(pfeil(strecke_in(s, lang)))}</a>"

    # Kurzbefunde: eigene Zählungen plus die Antworten aus den häufigen Fragen
    heim_vorn = sum(1 for s in reihenfolge if stats[s][0][1]["rolle"] == "Start/Ziel"
                    and groesster_faktor(routes[s]) >= 1.005)
    gleich = sum(1 for s in reihenfolge if groesster_faktor(routes[s]) < 1.005)
    befunde = [t["befund_strecken"].format(k=heim_vorn, r=r - gleich), t["befund_gleich"].format(k=gleich, r=r)]
    groesste = {}  # je Strecke der Zug mit dem größten Unterschied
    for v in alle:
        f = max(p[0] for p in v["preise"].values()) / min(p[0] for p in v["preise"].values())
        if f > groesste.get(v["strecke"], (0,))[0]:
            groesste[v["strecke"]] = (f, v)
    top = sorted(groesste.values(), key=lambda x: -x[0])[:8]
    if top and top[0][0] >= 1.005:
        f, v = top[0]
        billig = min(v["preise"].items(), key=lambda kv: kv[1][0])
        teuer = max(v["preise"].items(), key=lambda kv: kv[1][0])
        befunde.append(t["befund_max"].format(s=strecke_in(v["strecke"], lang), teuer=name(teuer[0]),
                                              billig=name(billig[0]), f=zahl(f, lang),
                                              pt=euro(teuer[1][0], lang, 0), pb=euro(billig[1][0], lang, 0)))
    kurz = "".join(f"<li>{esc(b)}</li>" for b in befunde)
    kurz += "".join(f"<li><strong>{esc(f)}</strong> {esc(a)}</li>" for f, a in faq_fragen(routes, stand, lang)[:3])

    # Alle Verkäufer über alle Strecken
    vk = collections.defaultdict(lambda: {"n": 0, "billig": 0, "teurer": [], "strecken": set()})
    for v in alle:
        low = min(p[0] for p in v["preise"].values())
        for verk, p in v["preise"].items():
            e = vk[verk]
            e["n"] += 1
            e["billig"] += p[0] <= low + 0.005
            if p[0] > low + 0.005:
                e["teurer"].append(p[0] / low)
            e["strecken"].add(v["strecke"])
    zeilen_vk = []
    for verk, e in sorted(vk.items(), key=lambda kv: (kv[1]["n"] < 10, -kv[1]["billig"] / kv[1]["n"])):
        zeilen_vk.append(f"<tr><td>{esc(name(verk))}</td><td class='zahl'>{len(e['strecken'])}</td>"
                         f"<td class='zahl'>{t['von'].format(b=e['billig'], n=e['n'])}</td>"
                         f"<td class='zahl'>{zahl(100 * e['billig'] / e['n'], lang, 0)} %</td>"
                         f"<td class='zahl'>{prozent(statistics.median(e['teurer']), lang) if e['teurer'] else '–'}</td></tr>")

    # Größte Unterschiede je Strecke
    zeilen_max = []
    for f, v in top:
        if f < 1.05:
            break
        billig = min(v["preise"].items(), key=lambda kv: kv[1][0])
        teuer = max(v["preise"].items(), key=lambda kv: kv[1][0])
        zug = f"{v['abfahrt']}–{v['ankunft']}" + (f" · {esc(v['zuege'])}" if v["zuege"] else "")
        zeilen_max.append(f"<tr><td>{link(v['strecke'])}<br><span class='klein'>{zug} · "
                          f"{datum(date.fromisoformat(v['reise_datum']), lang)}</span></td>"
                          f"<td><span class='billig'>{euro(billig[1][0], lang)}</span><br>"
                          f"<span class='klein'>{esc(name(billig[0]))}</span></td>"
                          f"<td>{euro(teuer[1][0], lang)}<br><span class='klein'>{esc(name(teuer[0]))}</span></td>"
                          f"<td class='zahl'>{zahl(f, lang)}×</td></tr>")

    # Ausländische Bahn billiger als alle Bahnen des Start-/Ziellandes
    fremd = collections.defaultdict(collections.Counter)
    for v in alle:
        h = heimpreis(v)
        if h is None:
            continue
        for verk, p in v["preise"].items():
            if p[2] in ("Durchgang", "kein Bezug") and p[0] < h - 0.005:
                fremd[v["strecke"]][verk] += 1
    zeilen_fremd = [f"<tr><td>{link(s)}</td><td>{', '.join(esc(name(x)) for x, _ in c.most_common())}</td>"
                    f"<td class='zahl'>{t['von'].format(b=max(c.values()), n=len(routes[s]))}</td></tr>"
                    for s, c in sorted(fremd.items(), key=lambda kv: -max(kv[1].values()))]

    von = min(v["abfrage"] for v in alle)
    bis = max(v["abfrage"] for v in alle)
    beschr = t["beschr_ergebnisse"].format(n=len(alle), r=r)
    datei = f"{lang}/{t['datei_ergebnisse']}.html"
    daten = {"@context": "https://schema.org", "@type": "Dataset", "name": t["titel_ergebnisse"],
             "description": beschr, "url": f"{ADRESSE}/{datei}", "inLanguage": lang,
             "license": "https://creativecommons.org/licenses/by/4.0/",
             "creator": {"@type": "Person", "name": ANBIETER[0]},
             "temporalCoverage": f"{von.isoformat()}/{bis.isoformat()}", "dateModified": stand.isoformat(),
             "spatialCoverage": "Europe", "isAccessibleForFree": True,
             "identifier": f"https://doi.org/{DATENSATZ_DOI}",
             "sameAs": [f"https://doi.org/{DATENSATZ_DOI}", DATENSATZ_GITHUB],
             "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv",
                               "contentUrl": f"{ADRESSE}/daten/vergleich.csv"}]}
    json_ld = json.dumps(daten, ensure_ascii=False).replace("</", "<\\/")
    tab_fremd = (f"""<div class="tabelle"><table>
<thead><tr><th>{t['sp_strecke']}</th><th>{t['sp_billiger_bei']}</th><th class="zahl">{t['sp_zuege_n']}</th></tr></thead>
<tbody>{''.join(zeilen_fremd)}</tbody></table></div>""" if zeilen_fremd else f"<p>{t['fremd_keine']}</p>")
    tab_max = (f"""<h2>{t['h2_max']}</h2>
<div class="tabelle"><table>
<thead><tr><th>{t['sp_strecke']}</th><th>{t['sp_billig_bei']}</th><th>{t['sp_teuer_bei']}</th><th class="zahl">{t['sp_faktor']}</th></tr></thead>
<tbody>{''.join(zeilen_max)}</tbody></table></div>
<p class="klein">{t['erkl_max']}</p>""" if zeilen_max else "")
    inhalt = f"""{aktuell(stand, lang)}
<h1>{t['titel_ergebnisse']}</h1>
<p class="stand">{t['stand_ergebnisse'].format(n=len(alle), r=r, v=len(vk), von=datum(von, lang), bis=datum(bis, lang))}</p>
<h2>{t['h2_kurz']}</h2>
<ul class="befunde">{kurz}</ul>
<p class="klein">{t['vorsicht']}</p>
<h2>{t['h2_verkaeufer_alle']}</h2>
<div class="tabelle"><table>
<thead><tr><th>{t['sp_verkaeufer']}</th><th class="zahl">{t['sp_strecken']}</th><th class="zahl">{t['sp_billigst']}</th><th class="zahl">{t['sp_anteil']}</th><th class="zahl">{t['sp_wenn_teurer']}</th></tr></thead>
<tbody>{''.join(zeilen_vk)}</tbody></table></div>
<p class="klein">{t['erkl_verkaeufer_alle']}</p>
{tab_max}
<h2>{t['h2_fremd']}</h2>
<p class="klein">{t['fremd_satz']}</p>
{tab_fremd}
<h2>{t['h2_zitieren']}</h2>
<p>{t['zitieren'].format(d=datum(stand, lang))}</p>
<script type="application/ld+json">{json_ld}</script>
"""
    pfade = {l: f"{l}/{T[l]['datei_ergebnisse']}.html" for l in SPRACHEN}
    return seite(lang, t["titel_ergebnisse"], beschr, inhalt, pfade)


def aktive_zuege(verbindungen):
    """Preise je Zug ohne die von der 6er-Regel gestrichenen Verkäufer; nur Züge mit mindestens 2 Preisen."""
    weg = gestrichen_hier(verbindungen)
    return [p for p in ({k: x for k, x in v["preise"].items() if k not in weg} for v in verbindungen) if len(p) >= 2]


def fremd_billiger(zuege):
    """Züge, bei denen eine Bahn ohne eigenen Start-/Zielbahnhof billiger war als die Bahn des Start- oder Ziellandes,
    die denselben Zug auch anbot: (Counter je ausländischer Bahn, Namen der unterbotenen Bahnen, Züge mit beiden)."""
    fremd, heimnamen, mit_beiden = collections.Counter(), set(), 0
    for p in zuege:
        heim = {k: x[0] for k, x in p.items() if x[2] == "Start/Ziel"}
        aus = {k: x[0] for k, x in p.items() if x[2] in ("Durchgang", "kein Bezug")}
        if heim and aus:
            mit_beiden += 1
            verk, preis = min(aus.items(), key=lambda kv: kv[1])
            if preis < min(heim.values()) - 0.005:
                fremd[verk] += 1
                heimnamen |= set(heim)
    return fremd, heimnamen, mit_beiden


def typischer_unterschied(zuege):
    """Median über die Züge von teuerster ÷ billigster Preis (1 = alle gleich teuer)."""
    return statistics.median(max(x[0] for x in p.values()) / min(x[0] for x in p.values()) for p in zuege) if zuege else 1


def aktive_verbindungen(verbindungen):
    """Die Verbindungen ohne die Preise gestrichener Verkäufer (nur solche mit mindestens 2 Preisen). Auf der
    Startseite rechnen damit Gleis, Gewinner-Schild, Satz und Filter einheitlich."""
    weg = gestrichen_hier(verbindungen)
    out = []
    for v in verbindungen:
        p = {k: x for k, x in v["preise"].items() if k not in weg}
        if len(p) >= 2:
            out.append({**v, "preise": p})
    return out


def zeilen_satz(verbindungen, stat, lang):
    """Ein kurzer Satz für die Startseite, was auf der Strecke passiert, und die Merkmale für die Filter.
    verbindungen: schon ohne gestrichene Verkäufer (aktive_verbindungen). Satz und Filter nutzen dieselben Zahlen:
    „Ausländische Bahn billiger“ = mindestens 3 Züge und 10 % aller Züge; „Großer Unterschied“ = der genannte
    Verkäufer ist im Median mindestens 30 % teurer als der Gewinner."""
    t = T[lang]
    merkmale = {"fremd": False, "gross": False, "gleich": False}
    if not verbindungen or groesster_faktor(verbindungen) < 1.005:
        merkmale["gleich"] = True
        return t["zs_gleich"], merkmale
    zuege = [v["preise"] for v in verbindungen]
    best = stat[0][0]
    teuer = []
    for verk, _ in stat[1:]:
        n, q = gegenueber(verbindungen, best, verk)
        if q and n >= 3:
            teuer.append((q, verk))
    q, teuerster = max(teuer) if teuer else (1, None)
    merkmale["gross"] = q >= 1.3
    fremd, heimnamen, _ = fremd_billiger(zuege)
    if fremd:
        verk, anz = fremd.most_common(1)[0]
        if anz >= 3 and anz / len(zuege) >= 0.1:
            merkmale["fremd"] = True
            return t["zs_fremd"].format(v=kurzname(verk), p=zahl(100 * anz / len(zuege), lang, 0),
                                        h=t["und"].join(kurzname(h) for h in sorted(heimnamen))), merkmale
    if q >= 2:
        return t["zs_faktor"].format(v=kurzname(teuerster), f=zahl(q, lang)), merkmale
    if q >= 1.03:
        return t["zs_prozent"].format(v=kurzname(teuerster), p=prozent(q, lang).lstrip("+")), merkmale
    return t["zs_kaum"], merkmale


def ersparnis(verbindungen):
    """Größter Unterschied in Euro zwischen billigstem und teuerstem noch abgefragten Verkäufer für denselben Zug,
    bei der letzten Abfrage der Strecke."""
    letzte = max(v["abfrage"] for v in verbindungen)
    zuege = aktive_zuege([v for v in verbindungen if v["abfrage"] == letzte])
    return max((max(x[0] for x in p.values()) - min(x[0] for x in p.values()) for p in zuege), default=0)


def kennzahlen(routes, reihenfolge, lang):
    """Drei Kennzahlen oben auf der Startseite."""
    t = T[lang]
    alle = [v for s in reihenfolge for v in routes[s]]
    kacheln = [(f"{len(alle):,}".replace(",", "." if lang == "de" else ","), t["kz_zuege"]),
               (str(len({verk for v in alle for verk in v["preise"]})), t["kz_verk"])]
    kacheln.insert(1, (str(len(reihenfolge)), t["kz_strecken"]))
    # Größter Unterschied in Euro für denselben Zug bei der letzten Abfrage (nur noch abgefragte Verkäufer),
    # über alle Strecken der Hauptliste (mindestens WENIG_ZUEGE Züge, damit es keine Teststrecke ist)
    spanne = max((ersparnis(routes[s]) for s in reihenfolge if len(routes[s]) >= WENIG_ZUEGE), default=0)
    if spanne >= 1:
        kacheln.append((t["kz_bis"].format(e=euro(spanne, lang, 0)), t["kz_spanne"]))
    # Eine ruhige Zeile statt Kästen (die Ergebnisse-Seite ist oben im Menü verlinkt)
    return "<p class='zahlenzeile'>" + "".join(f"<span><b>{w}</b> {esc(l)}</span>" for w, l in kacheln) + "</p>"


def falten(text):
    """Kleinbuchstaben ohne Akzente, für die Suche (z. B. „Kraków“ findet man auch mit „krakow“)."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c))


def interesse(verbindungen):
    """Wie interessant eine Strecke für die Startseite ist (höher = weiter oben):
        ln(1 + Züge) × min(1, Züge / 20) × Verkäufer² × (typischer Unterschied − 1 + Überraschung)
    Gezählt werden nur Verkäufer, die noch abgefragt werden: von der 6er-Regel gestrichene waren nie billiger und
    blähten sonst den Unterschied auf (Berlin–München stand oben, nur weil ČD das 3-Fache verlangte, während DB und
    ÖBB immer gleich teuer waren).
    Züge: verglichene Züge mit mindestens 2 solchen Verkäufern; min(1, Züge/20) dämpft Strecken mit wenigen Zügen.
    Verkäufer: wie viele verschiedene (zum Quadrat, zählt stark). Typischer Unterschied: Median über die Züge von
    teuerster ÷ billigster Preis. Überraschung: Anteil der Züge, bei denen eine Bahn ohne eigenen Start-/Zielbahnhof
    billiger war als die Bahn des Start- oder Ziellandes, die denselben Zug auch anbot (z. B. ÖBB bei München–Verona).
    Alle gleich teuer und keine Überraschung → 0, also ganz unten."""
    zuege = aktive_zuege(verbindungen)
    n = len(zuege)
    if not n:
        return 0
    k = len({verk for p in zuege for verk in p})
    f = statistics.median(max(x[0] for x in p.values()) / min(x[0] for x in p.values()) for p in zuege)
    ueberraschung = 0
    for p in zuege:
        heim = [x[0] for x in p.values() if x[2] == "Start/Ziel"]
        fremd = [x[0] for x in p.values() if x[2] in ("Durchgang", "kein Bezug")]
        if heim and fremd and min(fremd) < min(heim) - 0.005:
            ueberraschung += 1
    return math.log(1 + n) * min(1, n / 20) * k ** 2 * (f - 1 + ueberraschung / n)


def startseite(routes, reihenfolge, stats, stand, lang):
    t = T[lang]
    # Oben die interessantesten Strecken (viele Züge, viele Verkäufer, großer Preisunterschied), siehe interesse()
    sortiert = sorted(reihenfolge, key=lambda s: (-interesse(routes[s]), -len(routes[s])))
    zeilen, weitere = [], []
    staedte = set()
    anzahl = collections.Counter()
    for strecke in sortiert:
        # Auf der Startseite zählen nur Verkäufer, die noch abgefragt werden: so passen Gleis, Gewinner-Schild,
        # Satz und Filter zusammen (gestrichene Verkäufer waren nie billiger und blähten nur Unterschiede auf)
        # Sind alle anderen gestrichen (z. B. Berlin–München: nur noch DB), bleibt kein Vergleich: dann die alten
        # Daten fürs Gleis, aber ein ehrlicher Satz und kein Filter-Merkmal
        aktiv = aktive_verbindungen(routes[strecke])
        vs = aktiv or routes[strecke]
        stat_aktiv = statistik(vs)
        best, b = stat_aktiv[0]
        f = groesster_faktor(vs)
        s = strecke_in(strecke, lang)
        suche = f"{strecke} {strecke_in(strecke, 'en')}".lower()
        if UI["suche_oben"]:
            suche = f"{suche} {falten(suche)}"
        fehlt = ohne_vergleich(routes[strecke], stats[strecke]) if f >= 1.005 else []
        hinweis = f" · {t['fehlt_kurz'].format(v=', '.join(esc(name(x)) for x in fehlt))}" if fehlt else ""
        ab_eur = ab_preis(vs)[0]
        zahlen = t["zeile_zahlen"].format(f=zahl(f, lang, 2 if f < 1.1 else 1), z=len(routes[strecke])) + hinweis
        if aktiv:
            satz_z, merkmale = zeilen_satz(vs, stat_aktiv, lang)
        else:
            satz_z, merkmale = t["zs_nur"].format(v=kurzname(best)), {"fremd": False, "gross": False, "gleich": False}
        if UI["zeilen_satz"]:
            zahlen = f"{esc(satz_z)} · {t['zs_zuege'].format(n=len(routes[strecke]))}{hinweis}"
        daten = "".join(f" data-{k}='1'" for k, ja in merkmale.items() if ja) if UI["filter"] else ""
        anzahl.update(k for k, ja in merkmale.items() if ja)
        e = ersparnis(vs) if UI["spart"] else 0
        spart = (f"<span class='z-spart'>{t['spart'].format(e=euro(e, lang, 0))}</span>" if e >= 1 else "")
        # Eigene Spalte „Gewinner“: Kurzname des meist billigsten Verkäufers als Schild, darunter wie oft
        if f < 1.005:
            sieger = f"<span class='z-sieger'><span class='schild gleich'>{t['alle_gleich']}</span></span>"
        else:
            sieger = (f"<span class='z-sieger'><span class='schild' title='{esc(name(best))}'>{esc(kurzname(best))}</span>"
                      f"<small>{t['von'].format(b=b['billigster'], n=b['n'])}</small></span>")
        # Von/Nach-Suche: Start und Ziel getrennt, je deutsch + englisch + ohne Akzente
        a, z = strecke.split(" – ")[0], strecke.split(" – ")[-1]
        daten += "".join(f" data-{k}='{esc(falten(f'{x} {STADT_EN.get(x, x)}'))}'" for k, x in (("von", a), ("nach", z)))
        staedte.update((strecke_in(a, lang), strecke_in(z, lang)))
        # Für Verbindungen mit Umstieg: Start/Ziel genau (zum Verketten), Name des Umstiegsorts, Ab-Preis
        daten += (f" data-a='{esc(a)}' data-z='{esc(z)}' data-zn='{esc(strecke_in(z, lang))}'"
                  f" data-ab='{ab_eur:.2f}'")
        zeile = (f"<li data-suche='{esc(suche)}'{daten}><a class='zeile' href='{t['ordner']}/{slug(s)}.html'>"
                 f"<span class='z-text'><span class='z-name'>{esc(pfeil(s))}</span>"
                 f"<span class='z-info'>{zahlen}</span></span>{sieger}"
                 f"{gleis(beispielzug(vs), lang, klein=True)}"
                 f"<span class='z-preis'><small>{t['sp_ab']}</small> {euro(ab_eur, lang, 0 if ab_eur >= 100 else 2)}{spart}</span><span class='z-pfeil' aria-hidden='true'>›</span>"
                 f"</a></li>")
        # Strecken mit wenigen Zügen (meist Teststrecken) eingeklappt unter „Weitere Strecken“
        (weitere if UI["wenig_daten"] and len(routes[strecke]) < WENIG_ZUEGE else zeilen).append(zeile)
    n_zuege = sum(len(routes[s]) for s in reihenfolge)
    satz = t["satz_start"].format(v=len(VERKAEUFER), r=len(reihenfolge))
    suchfeld = (f'<input class="suche{" gross" if UI["suche_oben"] else ""}" id="suche" type="search" '
                f'placeholder="{t["suche_gross"] if UI["suche_oben"] else t["suche"]}" '
                f'aria-label="{t["suche_gross"] if UI["suche_oben"] else t["suche"]}" hidden>')
    if UI["suche_von_nach"]:
        # Wie in der DB-App: zwei Felder untereinander, rechts der Knopf zum Tauschen; Vorschläge aus den Städten
        feld = ("<label class='vn-zeile'><span class='vn-punkt{p}' aria-hidden='true'></span>"
                "<span class='vn-l'>{l}</span><input id='{i}' type='search' list='staedte' autocomplete='off' "
                "placeholder='{ph}' aria-label='{l}'></label>")
        suchfeld = (f"<form class='vn' id='vn' role='search' aria-label='{esc(t['vn_suche'])}' hidden>"
                    f"<div class='vn-felder'>"
                    + feld.format(p="", l=t["vn_von"], i="von", ph=esc(t["vn_von_ph"]))
                    + feld.format(p=" ziel", l=t["vn_nach"], i="nach", ph=esc(t["vn_nach_ph"]))
                    + f"</div><button class='vn-tausch' id='tauschen' type='button' aria-label='{esc(t['vn_tauschen'])}' "
                    f"title='{esc(t['vn_tauschen'])}'>⇅</button><datalist id='staedte'>"
                    + "".join(f"<option value='{esc(s)}'>" for s in sorted(staedte, key=falten))
                    + "</datalist></form>")
    if UI["kopf_oben"]:
        # Reihenfolge: Überschrift, ein Satz zum Projekt, Zahlen, Suche
        kopf = (f"<h1>{t['h1_start']}</h1>\n<p class='unterzeile'>{esc(t['satz_kurz'])}</p>\n"
                f"{kennzahlen(routes, reihenfolge, lang)}\n" + (suchfeld + "\n" if UI["suche_oben"] else ""))
    else:
        kopf = (f"<h1>{t['h1_start']}</h1>\n<p class='stand'>{t['stand_start'].format(n=n_zuege, r=len(reihenfolge))}</p>\n"
                + (suchfeld + "\n" if UI["suche_oben"] else "")
                + f"<p class='kurz'>{esc(satz)}{t['satz_start2']}</p>")
    # Filter-Knöpfe mit Anzahl; darunter steht nach dem Klick, wie viele Strecken angezeigt werden
    anzahl["alle"] = len(sortiert)
    chips = ("<div class='chips' id='chips' hidden>" + "".join(
        f"<button class='chip' type='button' data-f='{k}' aria-pressed='{'true' if k == 'alle' else 'false'}'>"
        f"{t['f_' + k]} <span class='anz'>{anzahl[k]}</span></button>"
        for k in ("alle", "fremd", "gross", "gleich") if anzahl[k]) + "</div>"
        + f"<p class='klein' id='anzahl' hidden data-text='{esc(t['f_anzahl'])}'></p>") if UI["filter"] else ""
    weiter = f'<p class="weiter"><a href="{t["datei_ergebnisse"]}.html">{t["zu_ergebnissen"]} →</a></p>'
    weitere_html = (f"<details class='weitere' id='weitere'><summary>{t['weitere'].format(n=len(weitere))}</summary>"
                    f"<ul class='strecken'>{''.join(weitere)}</ul></details>") if weitere else ""
    inhalt = f"""{aktuell(stand, lang)}
{kopf}
{"" if UI["kopf_oben"] else weiter}
<h2>{t['h2_alle']}</h2>
<p class="klein tipp">{t['tipp_zeile']}</p>
{"" if UI["suche_oben"] else suchfeld}
{chips}
<p class="klein" id="gegen" hidden>{esc(t['vn_gegen'])}</p>
<div id="umstieg" hidden data-ueber="{esc(t['vn_ueber'])}" data-zusammen="{esc(t['vn_zusammen'])}">
<p class="klein">{esc(t['vn_umstieg'])}</p><div id="umstieg-liste"></div>
<p class="klein">{esc(t['vn_umst_hinweis'])}</p></div>
<ul class="strecken" id="strecken">{mini_skala(lang)}{''.join(zeilen)}</ul>
{weitere_html}
<p class="klein" id="suche-leer" hidden>{t['suche_leer']}</p>
<p class="klein">{t['erkl_sortierung']} {t['erkl_gleis']} {t['erkl_unterschied']} {t['erkl_ab']}</p>
{faq(routes, stand, lang)}<script>
(function () {{
  var feld = document.getElementById("suche"), leer = document.getElementById("suche-leer");
  var weitere = document.getElementById("weitere"), chips = document.getElementById("chips"), filter = "alle";
  var zeilen = document.querySelectorAll(".strecken li:not(.skala)");
  // Suche: jedes Wort muss vorkommen (Reihenfolge egal, also beide Richtungen), Akzente werden ignoriert
  function falten(s) {{ return s.toLowerCase().normalize("NFD").replace(/[\\u0300-\\u036f]/g, ""); }}
  var von = document.getElementById("von"), nach = document.getElementById("nach");
  var vn = document.getElementById("vn"), gegen = document.getElementById("gegen");
  function passt(z, a, b) {{
    return (!a || z.dataset.von.indexOf(a) >= 0) && (!b || z.dataset.nach.indexOf(b) >= 0)
           && (filter === "alle" || z.dataset[filter] === "1");
  }}
  // Verbindungen mit 1 Umstieg (falls keine, mit 2) aus gemessenen Strecken; Umstiegsort muss genau passen
  function umstiege(a, b) {{
    var alle = [].slice.call(zeilen), gefunden = [], gesehen = {{}};
    function weiter(kette, rest) {{
      var letzte = kette[kette.length - 1];
      alle.forEach(function (z) {{
        if (z.dataset.a !== letzte.dataset.z) return;
        if (kette.some(function (k) {{ return k.dataset.a === z.dataset.z; }})) return;  // keine Schleifen
        var neu = kette.concat([z]);
        if (z.dataset.nach.indexOf(b) >= 0) {{
          var schluessel = neu.map(function (k) {{ return k.dataset.a; }}).join("|") + "|" + z.dataset.z;
          if (!gesehen[schluessel]) {{ gesehen[schluessel] = 1; gefunden.push(neu); }}
        }} else if (rest > 1) weiter(neu, rest - 1);
      }});
    }}
    var start = alle.filter(function (z) {{ return z.dataset.von.indexOf(a) >= 0 && z.dataset.nach.indexOf(b) < 0; }});
    for (var tiefe = 1; tiefe <= 2 && !gefunden.length; tiefe++)
      start.forEach(function (z) {{ weiter([z], tiefe); }});
    function summe(k) {{ return k.reduce(function (s, z) {{ return s + parseFloat(z.dataset.ab || 0); }}, 0); }}
    gefunden.sort(function (x, y) {{ return summe(x) - summe(y); }});
    return gefunden.slice(0, 4).map(function (k) {{ return {{ zeilen: k, summe: summe(k) }}; }});
  }}
  var umst = document.getElementById("umstieg");
  function umstiegZeigen(ketten) {{
    if (!umst) return;
    var liste = document.getElementById("umstieg-liste");
    liste.innerHTML = "";
    umst.hidden = !ketten.length;
    var geld = new Intl.NumberFormat(document.documentElement.lang || "de",
                                     {{ style: "currency", currency: "EUR", maximumFractionDigits: 0 }});
    ketten.forEach(function (k) {{
      var box = document.createElement("div"), kopf = document.createElement("p"), ul = document.createElement("ul");
      box.className = "umst"; kopf.className = "umst-kopf"; ul.className = "strecken";
      var orte = k.zeilen.slice(0, -1).map(function (z) {{ return z.dataset.zn; }}).join(", ");
      var b1 = document.createElement("b"), s2 = document.createElement("span");
      b1.textContent = umst.dataset.ueber.replace("{{s}}", orte);
      s2.textContent = umst.dataset.zusammen.replace("{{p}}", geld.format(k.summe));
      kopf.appendChild(b1); kopf.appendChild(s2);
      k.zeilen.forEach(function (z) {{ var c = z.cloneNode(true); c.hidden = false; ul.appendChild(c); }});
      box.appendChild(kopf); box.appendChild(ul); liste.appendChild(box);
    }});
  }}
  function zeigen() {{
    var w, n = 0, drin = false, test;
    if (vn) {{
      // Von/Nach: erst genau diese Richtung; gibt es sie nicht, die Gegenrichtung mit Hinweis
      var a = falten(von.value).trim(), b = falten(nach.value).trim(), rueck = false;
      w = a || b ? [a, b] : [];
      test = function (z) {{ return rueck ? passt(z, b, a) : passt(z, a, b); }};
      var ketten = [];
      if (a && b && ![].some.call(zeilen, function (z) {{ return passt(z, a, b); }})) {{
        // Keine direkte Strecke: erst Verbindungen mit Umstieg aus gemessenen Strecken, sonst die Gegenrichtung
        ketten = umstiege(a, b);
        if (ketten.length) test = function () {{ return false; }};
        else rueck = true;
      }}
      gegen.hidden = !rueck;
      umstiegZeigen(ketten);
    }} else {{
      w = falten(feld.value).split(/[\\s,;\\/–→>-]+/).filter(Boolean);
      test = function (z) {{
        return w.every(function (x) {{ return z.dataset.suche.indexOf(x) >= 0; }})
               && (filter === "alle" || z.dataset[filter] === "1");
      }};
    }}
    zeilen.forEach(function (z) {{
      var ja = test(z);
      z.hidden = !ja;
      if (ja) {{ n++; if (weitere && weitere.contains(z)) drin = true; }}
    }});
    if (gegen && n === 0) gegen.hidden = true;
    if (weitere && (w.length || filter !== "alle")) weitere.open = drin;
    leer.hidden = n > 0 || (umst && !umst.hidden);
    var anz = document.getElementById("anzahl");
    if (anz) {{ anz.hidden = !(w.length || filter !== "alle") || n === 0; anz.textContent = anz.dataset.text.replace("{{n}}", n); }}
  }}
  if (vn) {{
    vn.hidden = false;
    von.addEventListener("input", zeigen);
    nach.addEventListener("input", zeigen);
    document.getElementById("tauschen").addEventListener("click", function () {{
      var x = von.value; von.value = nach.value; nach.value = x; zeigen();
    }});
    // Enter: bleibt genau eine Strecke übrig, direkt dorthin
    vn.addEventListener("submit", function (e) {{ e.preventDefault(); }});
    vn.addEventListener("keydown", function (e) {{
      if (e.key !== "Enter") return;
      e.preventDefault();
      var sicht = [].filter.call(zeilen, function (z) {{ return !z.hidden; }});
      if (sicht.length === 1) location.href = sicht[0].querySelector("a").href;
      else if (e.target === von) nach.focus();
    }});
  }} else {{
    feld.hidden = false;
    feld.addEventListener("input", zeigen);
  }}
  if (chips) {{
    chips.hidden = false;
    chips.querySelectorAll(".chip").forEach(function (b) {{
      b.addEventListener("click", function () {{
        filter = b.dataset.f;
        chips.querySelectorAll(".chip").forEach(function (c) {{ c.setAttribute("aria-pressed", c === b ? "true" : "false"); }});
        zeigen();
      }});
    }});
  }}
}})();
</script>
"""
    return seite(lang, t["titel_start"], satz, inhalt, {l: f"{l}/index.html" for l in SPRACHEN})


def rohdaten_verzoegert(quelle, ziel, bis):
    """Schreibt nur die Zeilen von vergleich.csv, deren Abfragetag spätestens 'bis' ist. Gibt die Zeilenzahl zurück."""
    n = 0
    with open(quelle, encoding="utf-8", newline="") as f, open(ziel, "w", encoding="utf-8", newline="") as g:
        leser = csv.DictReader(f, delimiter=";")
        schreiber = csv.DictWriter(g, fieldnames=leser.fieldnames, delimiter=";")
        schreiber.writeheader()
        for r in leser:
            abfrage = date.fromisoformat(r["reise_datum"]) - timedelta(days=int(r["vorlauf_tage"]))
            if abfrage <= bis:
                schreiber.writerow(r)
                n += 1
    return n


def einstieg(anzahl):
    """Startseite ohne Sprache: leitet sofort auf die zuletzt gewählte Sprache weiter, sonst auf die des Browsers
    (Deutsch bei deutscher Browsersprache, sonst Englisch; nie nach Standort). Ohne JavaScript (z. B. manche Bots)
    bleibt die Auswahl stehen."""
    alternates = "".join(f'<link rel="alternate" hreflang="{l}" href="{ADRESSE}/{l}/index.html">\n' for l in SPRACHEN)
    namen = {"de": "Deutsch", "en": "English"}
    knoepfe = "".join(f'<a href="{l}/index.html" data-l="{l}" hreflang="{l}">{namen[l]}</a>' for l in ("en", "de"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{T['en']['titel']} · {T['de']['titel']}</title>
<meta name="description" content="{esc(T['en']['satz_start'].format(v=len(VERKAEUFER), r=anzahl))}">
{alternates}<link rel="alternate" hreflang="x-default" href="{ADRESSE}/">
<script>
var l = null;
try {{ l = localStorage.getItem("sprache"); }} catch (e) {{}}
if (l !== "de" && l !== "en") l = (navigator.language || "en").slice(0, 2) === "de" ? "de" : "en";
location.replace(l + "/index.html");
</script>
{icons("")}<link rel="stylesheet" href="{stil_url()}">
</head>
<body>
<main>
<h1>{T['en']['h1_start']}<br><span class="klein">{T['de']['h1_start']}</span></h1>
<div class="wahl">{knoepfe}</div>
</main>
</body>
</html>
"""


def main():
    global ADRESSE, GOATCOUNTER
    args = sys.argv[1:]
    if "--adresse" in args:
        i = args.index("--adresse")
        ADRESSE = args[i + 1].rstrip("/")
        del args[i:i + 2]
    if "--goatcounter" in args:
        i = args.index("--goatcounter")
        GOATCOUNTER = args[i + 1]
        del args[i:i + 2]
    while "--affiliate" in args:
        i = args.index("--affiliate")
        verk, _, link = args[i + 1].partition("=")
        if verk not in VERKAEUFER or not link.startswith("https://"):
            sys.exit("--affiliate erwartet verkäufer=https://..., z. B. bahn.de=https://www.awin1.com/cread.php?...")
        AFFILIATE[verk] = link
        del args[i:i + 2]
    quelle = args[0] if args else str(VERGLEICH)
    routes = lesen(quelle)
    if not routes:
        sys.exit(f"Keine vergleichbaren Verbindungen in {quelle}")

    global SUCHLINKS
    SUCHLINKS = suchlinks()
    (WEBSEITE / "daten").mkdir(parents=True, exist_ok=True)
    (WEBSEITE / "stil.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    for icon in (SKRIPTE / "favicon").iterdir():
        shutil.copyfile(icon, WEBSEITE / icon.name)
    stand_daten = max(v["abfrage"] for vs in routes.values() for v in vs)
    n_csv = rohdaten_verzoegert(quelle, WEBSEITE / "daten" / "vergleich.csv",
                                stand_daten - timedelta(days=SPERRFRIST_TAGE))

    reihenfolge = sorted(routes, key=lambda s: int(routes[s][0]["nr"]))
    for lang in SPRACHEN:
        t = T[lang]
        (WEBSEITE / lang / t["ordner"]).mkdir(parents=True, exist_ok=True)
        stats, stand = {}, None
        for strecke in reihenfolge:
            text, stats[strecke], st = streckenseite(strecke, routes[strecke], lang)
            (WEBSEITE / strecken_pfad(strecke, lang)).write_text(text, encoding="utf-8")
            stand = max(stand or st, st)
        (WEBSEITE / lang / "index.html").write_text(startseite(routes, reihenfolge, stats, stand, lang),
                                                    encoding="utf-8")
        (WEBSEITE / lang / f"{t['datei_ergebnisse']}.html").write_text(
            ergebnisseite(routes, reihenfolge, stats, stand, lang), encoding="utf-8")
        for datei, titel, beschr, text in (("methodik", t["titel_methodik"], t["beschr_methodik"], t["methodik_text"]),
                                           ("impressum", t["impressum"], t["impressum"],
                                            t["impressum_text"].format(anbieter=anbieter_html(), name=esc(ANBIETER[0]))),
                                           ("datenschutz", t["datenschutz"], t["beschr_datenschutz"], datenschutz(lang)),
                                           ("feedback", t["feedback"], t["beschr_feedback"], feedback_seite(lang))):
            pfade = {l: f"{l}/{datei}.html" for l in SPRACHEN}
            (WEBSEITE / lang / f"{datei}.html").write_text(seite(lang, f"{titel} – {t['titel']}", beschr, text, pfade),
                                                           encoding="utf-8")
    (WEBSEITE / "index.html").write_text(einstieg(len(reihenfolge)), encoding="utf-8")

    # Sitemap mit Sprachverknüpfung: jede Seite nennt alle ihre Sprachversionen
    seiten = ([{l: f"{l}/index.html" for l in SPRACHEN}, {l: f"{l}/{T[l]['datei_ergebnisse']}.html" for l in SPRACHEN},
               {l: f"{l}/methodik.html" for l in SPRACHEN}]
              + [{l: strecken_pfad(s, l) for l in SPRACHEN} for s in reihenfolge])
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for pfade in seiten:
        links = "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{ADRESSE}/{p}"/>' for l, p in pfade.items())
        for p in pfade.values():
            xml.append(f"<url><loc>{ADRESSE}/{p}</loc><lastmod>{stand.isoformat()}</lastmod>{links}</url>")
    xml.append("</urlset>")
    (WEBSEITE / "sitemap.xml").write_text("\n".join(xml) + "\n", encoding="utf-8")
    # Such- und Nutzer-Abrufe namentlich erlaubt; alle anderen (auch KI-Training) ebenfalls zugelassen
    robots = "".join(f"User-agent: {c}\n" for c in CRAWLER_ERLAUBT) + "Allow: /\n\n"
    robots += "# Alle anderen Crawler, auch fürs KI-Training\nUser-agent: *\nAllow: /\n\n"
    (WEBSEITE / "robots.txt").write_text(robots + f"Sitemap: {ADRESSE}/sitemap.xml\n", encoding="utf-8")
    # Cloudflare liefert .html-Adressen direkt aus (html_handling = "none" in wrangler.toml); Ordneradressen
    # wie / oder /de/ zeigen deshalb per Umschreiben (200, keine Weiterleitung) auf ihre index.html
    # Browser fragen bei HTML jedes Mal nach, ob es eine neue Version gibt; stil.css hat einen Versionsanhang
    # (stil.css?v=…) und darf deshalb lange gespeichert werden
    if UI["frisch"]:
        frisch = "  Cache-Control: public, max-age=0, must-revalidate\n"
        (WEBSEITE / "_headers").write_text("".join(f"{p}\n{frisch}" for p in ("/*.html", "/", "/de/", "/en/"))
                                           + "/stil.css\n  Cache-Control: public, max-age=31536000, immutable\n",
                                           encoding="utf-8")
    elif (WEBSEITE / "_headers").exists():
        shutil.move(WEBSEITE / "_headers", SKRIPTE.parent / "alte_dateien" / f"_headers_{date.today().isoformat()}")
    (WEBSEITE / "_redirects").write_text("".join(f"/{p} /{p}index.html 200\n" for p in ["", *(f"{l}/" for l in SPRACHEN)]),
                                         encoding="utf-8")
    if INDEXNOW:
        (WEBSEITE / f"{INDEXNOW}.txt").write_text(INDEXNOW, encoding="utf-8")

    print(f"{len(reihenfolge)} Strecken x {len(SPRACHEN)} Sprachen, Stand {stand} -> {WEBSEITE / 'index.html'}")
    print(f"Rohdaten-CSV: {n_csv} Zeilen (Abfragen bis {stand_daten - timedelta(days=SPERRFRIST_TAGE)})")


if __name__ == "__main__":
    main()
