"""Baut aus der öffentlichen Rohdaten-CSV (webseite/daten/vergleich.csv, 7 Tage verzögert) den Ordner
veroeffentlichung/paket/ – fertig als GitHub-Repo, aus dem Zenodo bei jedem Release eine Version mit DOI macht.
Dazu dieselben Daten für Kaggle (veroeffentlichung/kaggle/, mit dataset-metadata.json) und Hugging Face
(veroeffentlichung/huggingface/, README mit Dataset-Card-Kopf).

    python skripte/datensatz_paket.py               Paket neu bauen
    python skripte/datensatz_paket.py --doi 10.5281/zenodo.1234567   Concept-DOI eintragen (danach immer dabei)

Inhalt: README.md (Englisch, kurz Deutsch), data/vergleich.csv, LICENSE.md, CITATION.cff, .zenodo.json.
Zahlen (Zeilen, Strecken, Zeitraum, Version) werden aus der CSV berechnet. Anleitung: veroeffentlichung/anleitung.md"""
import csv
import json
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

from pfade import BASIS, WEBSEITE
from webseite import ADRESSE, ANBIETER

QUELLE = WEBSEITE / "daten" / "vergleich.csv"
PAKET = BASIS / "veroeffentlichung" / "paket"
KAGGLE = BASIS / "veroeffentlichung" / "kaggle"
HUGGINGFACE = BASIS / "veroeffentlichung" / "huggingface"
KAGGLE_ID = "ferdinandfrey/european-train-fares-same-train"  # <kaggle-nutzername>/<slug>; "" = nicht verlinken
HF_ID = ""  # <hf-nutzername>/<name>, z. B. "UrzasMine/same-train-different-price"; "" = Hugging Face aus
GITHUB = "https://github.com/UrzasMine/same-train-different-price"
DOI_DATEI = BASIS / "veroeffentlichung" / "doi.txt"  # Concept-DOI, sobald Zenodo sie vergeben hat
AUTOR = ANBIETER[0]
AFFILIATION = "Vilnius University"
TITEL = "Same train, different price: daily fare comparison of European railway sellers"

VERKAEUFER = {  # Name in der CSV -> (Anzeige, Land)
    "bahn.de": ("Deutsche Bahn (bahn.de)", "DE"), "oebb.at": ("ÖBB", "AT"), "sbb.ch": ("SBB", "CH"),
    "cd.cz": ("České dráhy", "CZ"), "intercity.pl": ("PKP Intercity", "PL"), "mav.hu": ("MÁV", "HU"),
    "ltglink.lt": ("LTG Link", "LT"), "elron.ee": ("Elron", "EE"), "trenitalia.com": ("Trenitalia", "IT"),
    "eurostar.com": ("Eurostar", "FR/BE/NL/DE/UK"), "b-europe.com": ("SNCB International (b-europe.com)", "BE"),
    "omio.com": ("Omio (reseller)", "–"),
}

SPALTEN = """| Column | Meaning |
|---|---|
| reise_datum | travel date |
| nr, strecke | route number and name (German city names, e.g. "München - Wien") |
| abfahrt, ankunft | departure / arrival of the matched train |
| zuege | train numbers, if shown |
| verkaeufer | seller website (e.g. bahn.de, oebb.at) |
| rolle | seller's role: Start/Ziel = railway of origin/destination country, Durchgang = transit country, kein Bezug = unrelated, Vermittler = reseller (Omio) |
| abfahrt_verkaeufer, ankunft_verkaeufer | times as shown by this seller |
| preis, waehrung | fare in local currency |
| preis_eur | fare in EUR (ECB reference rate of the check date) |
| tarif | fare name or note, if any |
| billigster_eur | cheapest fare among all sellers for this train |
| aufschlag_prozent | markup over the cheapest seller, in % |
| verdacht | "ja" if the highest fare is at least 3× the lowest (worth checking) |
| vorlauf_tage | booking lead time: days between check and travel |
| paarung | how the train was matched: "gleiche Zeiten" (same times) or "gleiche Zugnummer" (same train number) |"""


def kennzahlen():
    with open(QUELLE, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    reise = sorted(r["reise_datum"] for r in rows)
    abfrage = sorted(str(date.fromisoformat(r["reise_datum"]) - timedelta(days=int(r["vorlauf_tage"]))) for r in rows)
    zuege = {(r["reise_datum"], r["vorlauf_tage"], r["nr"], r["abfahrt"], r["ankunft"]) for r in rows}
    return {"zeilen": len(rows), "zuege": len(zuege), "strecken": len({r["strecke"] for r in rows}),
            "verkaeufer": sorted({r["verkaeufer"] for r in rows}), "reise_von": reise[0], "reise_bis": reise[-1],
            "abfrage_von": abfrage[0], "abfrage_bis": abfrage[-1]}


def readme(k, doi, csv_pfad="data/vergleich.csv"):
    doi_link = f"[{doi}](https://doi.org/{doi})" if doi else "on Zenodo (DOI follows with the first release)"
    spiegel = [f"[GitHub]({GITHUB})"] + ([f"[Kaggle](https://www.kaggle.com/datasets/{KAGGLE_ID})"] if KAGGLE_ID else [])         + ([f"[Hugging Face](https://huggingface.co/datasets/{HF_ID})"] if HF_ID else [])
    verk = "\n".join(f"| {VERKAEUFER.get(v, (v, ''))[0]} | {VERKAEUFER.get(v, (v, ''))[1]} |" for v in k["verkaeufer"])
    zitat = (f"{AUTOR} ({k['abfrage_bis'][:4]}). *{TITEL}* (Version {k['abfrage_bis']}) [Data set]. "
             + (f"Zenodo. https://doi.org/{doi}" if doi else f"{ADRESSE}"))
    return f"""# Same train, different price

**Daily fare comparison of European railway ticket sellers – open data (CC BY 4.0)**

🌐 Results per route: **{ADRESSE}** · 📄 Citable dataset: {doi_link}
· Mirrors: {" · ".join(spiegel)}

Many European trains can be booked on several websites: the railway of the departure country, the railway of the
destination country, sometimes a transit railway or a reseller. This dataset records every day whether they charge
the same for the same train – and how that depends on how far ahead you book.

**Current version {k['abfrage_bis']}:** {k['zeilen']:,} rows · {k['zuege']:,} train offers compared ·
{k['strecken']} routes · {len(k['verkaeufer'])} sellers · checks from {k['abfrage_von']} to {k['abfrage_bis']}
(travel dates {k['reise_von']} – {k['reise_bis']}).

## Data

[`{csv_pfad}`]({csv_pfad}) – one row per train and seller, **semicolon-separated, decimal comma**, UTF-8.

```python
import pandas as pd
df = pd.read_csv("{csv_pfad}", sep=";", decimal=",")
```

{SPALTEN}

The file contains only checks that are at least 7 days old; current fares are shown on the website.

## Sellers

| Seller | Country |
|---|---|
{verk}

Not included: SNCF Connect, Trainline and Rail Europe (captcha or access block), NS International, SŽ, ZSSK and
others (no suitable online search or blocked automated access). Bot protection is never bypassed.

## Method

- Every day an automated browser opens each seller's website and searches the same connections, as a person would.
- Travel dates: 1, 7, 21 and 42 days ahead; trains from 8 a.m.
- Stored: the lowest fare shown for 1 adult, 2nd class, no discount card.
- Same train = same departure and arrival time, or same train number with times at most 15–20 min apart.
- Only fares checked on the same day are compared.
- CHF, CZK, PLN → EUR at the ECB reference rate of the check date.
- Excluded: fares valid only for part of the route, connections without a fare.
- Omio: an estimated service fee (about 6.5 % of the fare, at least €2) is added.
- Sellers unrelated to a route that were never cheaper than the origin/destination railway in 6 checks are dropped
  from that route; routes where all sellers charged the same on 6 travel days are checked on Mondays only.

Full description: {ADRESSE}/en/methodik.html

## Limitations

The lowest fare can be a saver fare at one seller and a flexible fare at another. Fares change constantly; each
row is a snapshot. Booking fees charged at payment are not included for railways. Discount cards are not taken into
account. No guarantee of accuracy.

## License and citation

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Please credit
“Train Price Comparison (sametrain.eu)” with a link to {ADRESSE}, or cite:

> {zitat}

University project, Data Analysis course, {AFFILIATION}, 2026. Feedback: {ADRESSE}/en/feedback.html

---

**Deutsch:** Täglicher Vergleich der Preise verschiedener Bahn-Verkäufer für denselben Zug am selben Abfragetag
(1 Erwachsener, 2. Klasse, ohne Ermäßigung). Auswertung pro Strecke auf {ADRESSE}/de/index.html,
Daten unter CC BY 4.0 mit Quellenangabe „Zugpreis-Vergleich (sametrain.eu)“ und Link.
"""


def zenodo_json(k):
    return {
        "title": TITEL,
        "upload_type": "dataset",
        "version": k["abfrage_bis"],
        "description": (
            "<p>Do railway ticket sellers charge the same price for the same train? This dataset compares the fares "
            f"that {len(k['verkaeufer'])} sellers (national railways and the reseller Omio) show for identical European "
            f"train connections on {k['strecken']} routes, checked on the same day. Every day an automated browser "
            "searches each seller's website for travel 1, 7, 21 and 42 days ahead and stores the lowest fare shown "
            "for 1 adult, 2nd class, without discount card.</p>"
            f"<p>Version {k['abfrage_bis']}: {k['zeilen']} rows (one per train and seller), checks from "
            f"{k['abfrage_von']} to {k['abfrage_bis']}. Semicolon-separated CSV with decimal comma. Only checks at "
            "least 7 days old are included.</p>"
            f"<p>Results per route and full method: <a href=\"{ADRESSE}\">{ADRESSE}</a></p>"),
        "creators": [{"name": ", ".join(reversed(AUTOR.split(" ", 1))), "affiliation": AFFILIATION}],
        "license": "cc-by-4.0",
        "language": "eng",
        "keywords": ["rail fares", "train tickets", "price comparison", "Europe", "ticket sellers",
                     "dynamic pricing", "booking lead time", "web scraping", "transport economics"],
        "related_identifiers": [
            {"identifier": f"{ADRESSE}/en/index.html", "relation": "isDocumentedBy", "resource_type": "other"},
            {"identifier": f"{ADRESSE}/en/methodik.html", "relation": "isDescribedBy", "resource_type": "other"},
        ],
        "dates": [{"type": "Collected", "start": k["abfrage_von"], "end": k["abfrage_bis"]}],
    }


def citation_cff(k, doi):
    nach, vor = reversed(AUTOR.split(" ", 1))
    return f"""cff-version: 1.2.0
message: "If you use this dataset, please cite it as below and link to {ADRESSE}."
type: dataset
title: "{TITEL}"
version: "{k['abfrage_bis']}"
date-released: "{date.today()}"
license: CC-BY-4.0
url: "{ADRESSE}"
authors:
  - family-names: "{nach}"
    given-names: "{vor}"
    affiliation: "{AFFILIATION}"
""" + (f'doi: "{doi}"\n' if doi else "") + """keywords:
  - rail fares
  - price comparison
  - Europe
"""


LIZENZ = f"""# License

The data in `data/` is licensed under the **Creative Commons Attribution 4.0 International License (CC BY 4.0)**.

You may share and adapt it for any purpose, including commercially, as long as you give appropriate credit:
“Train Price Comparison (sametrain.eu)” with a link to {ADRESSE}, or a citation of the Zenodo DOI.

Full legal text: https://creativecommons.org/licenses/by/4.0/legalcode
"""


def huggingface_readme(k, doi):
    kopf = f"""---
license: cc-by-4.0
pretty_name: "Same train, different price: European rail fares by seller"
language:
  - en
tags:
  - rail
  - trains
  - prices
  - europe
  - transportation
size_categories:
  - 1K<n<10K
configs:
  - config_name: default
    data_files: data/vergleich.csv
    sep: ";"
---

"""
    return kopf + readme(k, doi)


def kaggle_metadaten(k):
    return {"title": "European Train Fares: Same Train, Different Seller",
            "subtitle": "Daily fares from rail ticket sellers for identical trains across Europe",
            "id": KAGGLE_ID, "licenses": [{"name": "CC-BY-4.0"}],
            "keywords": ["transportation", "europe", "travel", "economics", "tabular"],
            "resources": [{"path": "vergleich.csv", "description": "One row per train and seller, "
                           "semicolon-separated, decimal comma"}]}


def main():
    args = sys.argv[1:]
    if "--doi" in args:
        DOI_DATEI.write_text(args[args.index("--doi") + 1].strip() + "\n", encoding="utf-8")
    doi = DOI_DATEI.read_text(encoding="utf-8").strip() if DOI_DATEI.exists() else ""
    k = kennzahlen()
    (PAKET / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy2(QUELLE, PAKET / "data" / "vergleich.csv")
    (PAKET / "README.md").write_text(readme(k, doi), encoding="utf-8")
    (PAKET / "LICENSE.md").write_text(LIZENZ, encoding="utf-8")
    (PAKET / "CITATION.cff").write_text(citation_cff(k, doi), encoding="utf-8")
    (PAKET / ".zenodo.json").write_text(json.dumps(zenodo_json(k), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if HF_ID:
        (HUGGINGFACE / "data").mkdir(parents=True, exist_ok=True)
        shutil.copy2(QUELLE, HUGGINGFACE / "data" / "vergleich.csv")
        (HUGGINGFACE / "README.md").write_text(huggingface_readme(k, doi), encoding="utf-8")
    KAGGLE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(QUELLE, KAGGLE / "vergleich.csv")
    meta = kaggle_metadaten(k)
    meta["description"] = readme(k, doi, csv_pfad="vergleich.csv")
    (KAGGLE / "dataset-metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Paket in {PAKET}: Version {k['abfrage_bis']}, {k['zeilen']} Zeilen, {k['strecken']} Strecken, "
          f"{len(k['verkaeufer'])} Verkäufer" + (f", DOI {doi}" if doi else ", noch ohne DOI"))


if __name__ == "__main__":
    main()
