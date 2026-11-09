"""Einfache Grafik für r/interrail: Auf welcher Seite ist derselbe Zug billiger, und wie viel zahlt man auf der anderen mehr?
Liest daten/vergleich.csv (ohne Zeilen mit verdacht=ja), schreibt grafiken/interrail_wo_buchen.png (Englisch).
Pro Strecke: Median der Preisdifferenz (teurer - billiger Verkäufer) über alle Züge, die beide am selben Tag hatten.

Aufruf: python skripte/grafik_interrail.py"""
import csv
import statistics
from collections import defaultdict
from datetime import date, timedelta

import matplotlib.pyplot as plt

from pfade import DATEN, VERGLEICH

ZIEL = DATEN.parent / "grafiken" / "interrail_wo_buchen.png"
# (Strecke in vergleich.csv, billigerer Verkäufer, teurerer Verkäufer, Beschriftung)
STRECKEN = [("Budapest - München", "mav.hu", "oebb.at", "Budapest → Munich"),
            ("Zürich - München", "bahn.de", "oebb.at", "Zurich → Munich"),
            ("Prag - München", "cd.cz", "bahn.de", "Prague → Munich"),
            ("Wien - Nürnberg", "bahn.de", "oebb.at", "Vienna → Nuremberg"),
            ("Wien - Budapest", "mav.hu", "oebb.at", "Vienna → Budapest"),
            ("München - Wien", "bahn.de", "oebb.at", "Munich → Vienna"),
            ("Wien - Venedig", "oebb.at", "trenitalia.com", "Vienna → Venice"),
            ("München - Verona", "oebb.at", "bahn.de", "Munich → Verona"),
            ("Vilnius - Warschau", "intercity.pl", "ltglink.lt", "Vilnius → Warsaw"),
            ("Warschau - Berlin", "intercity.pl", "bahn.de", "Warsaw → Berlin"),
            ("Berlin - Prag", "cd.cz", "bahn.de", "Berlin → Prague")]
NAMEN = {"mav.hu": "MÁV", "oebb.at": "ÖBB", "bahn.de": "DB", "cd.cz": "ČD", "trenitalia.com": "Trenitalia",
         "intercity.pl": "PKP", "ltglink.lt": "LTG Link", "sbb.ch": "SBB"}
BALKEN = "#de4f2c"
FLAECHE, TINTE, TINTE2, LEISE, GITTER = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e4e3df"
SCHRIFT = "Segoe UI"


def zahl(s):
    return float(s.replace(",", "."))


def tag(d):
    return f"{d:%b} {d.day}"


def lesen():
    for kodierung in ("utf-8", "cp1252"):
        try:
            with open(VERGLEICH, encoding=kodierung) as f:
                return [z for z in csv.DictReader(f, delimiter=";") if z["verdacht"] != "ja"]
        except UnicodeDecodeError:
            pass


def daten():
    zeilen = lesen()
    zuege = defaultdict(dict)
    for z in zeilen:
        zuege[(z["strecke"], z["reise_datum"], z["abfahrt"])][z["verkaeufer"]] = zahl(z["preis_eur"])
    ergebnis = []
    for strecke, billig, teuer, name in STRECKEN:
        d = [p[teuer] - p[billig] for (s, _, _), p in zuege.items() if s == strecke and billig in p and teuer in p]
        ergebnis.append({"name": name, "billig": billig, "teuer": teuer, "median": statistics.median(d),
                         "n": len(d), "teurer": sum(x > 0.5 for x in d)})
    abfragen = [date.fromisoformat(z["reise_datum"]) - timedelta(days=int(z["vorlauf_tage"])) for z in zeilen]
    return sorted(ergebnis, key=lambda e: -e["median"]), min(abfragen), max(abfragen)


def main():
    reihen, von, bis = daten()
    for e in reihen:
        print(f"{e['name']:22} {NAMEN[e['billig']]:>13} < {NAMEN[e['teuer']]:<11} +{e['median']:5.1f} EUR  "
              f"teurer bei {e['teurer']}/{e['n']}")
    plt.rcParams.update({"font.family": SCHRIFT, "text.color": TINTE})

    fig = plt.figure(figsize=(10, 10), dpi=200, facecolor=FLAECHE)
    L = 0.06
    fig.text(L, 0.945, "Same train, cheaper on another website", fontsize=25, weight="bold")
    fig.text(L, 0.922, "How much more you typically pay if you book the identical train on the wrong railway's site.\n"
             "2nd class, 1 adult, no discount card, both sites checked on the same day.",
             fontsize=11.5, color=TINTE2, linespacing=1.4, va="top")

    oben, unten = 0.80, 0.10
    ax = fig.add_axes([0.43, unten, 0.47, oben - unten], facecolor=FLAECHE)
    groesst = max(e["median"] for e in reihen)
    ax.set_xlim(0, groesst * 1.12)
    ax.set_ylim(len(reihen) - 0.4, -0.6)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_yticks([])
    ax.tick_params(axis="x", colors=LEISE, labelsize=9.5, length=0)
    ax.xaxis.set_major_formatter(lambda x, _: f"€{x:.0f}")
    ax.xaxis.tick_top()
    ax.grid(axis="x", color=GITTER, linewidth=0.8)
    ax.set_axisbelow(True)

    for y, e in enumerate(reihen):
        ax.barh(y, e["median"], height=0.52, color=BALKEN)
        ax.text(e["median"] + groesst * 0.015, y, f"+€{e['median']:.0f}", va="center", fontsize=12, weight="bold")
        y_fig = ax.transData.transform((0, y))[1] / fig.bbox.height
        fig.text(L, y_fig + 0.010, e["name"], va="center", fontsize=13, weight="semibold")
        fig.text(L, y_fig - 0.013, f"Book at {NAMEN[e['billig']]}, not {NAMEN[e['teuer']]} "
                 f"· dearer on {e['teurer']} of {e['n']} trains",
                 va="center", fontsize=9.3, color=TINTE2)

    fig.text(L, 0.045, "Typical = median difference over all trains both sites sold on the same day; "
             "sometimes both cost the same.\nPrices for point-to-point tickets, not passes.",
             fontsize=8.8, color=LEISE, linespacing=1.4)
    fig.text(L, 0.018, f"Data: own daily automated price checks, {tag(von)} – {tag(bis)}, {bis.year} · sametrain.eu",
             fontsize=8.8, color=TINTE2)

    ZIEL.parent.mkdir(exist_ok=True)
    fig.savefig(ZIEL, facecolor=FLAECHE)
    print(ZIEL)


if __name__ == "__main__":
    main()
