"""Grafik für r/dataisbeautiful: Wie viel teurer war jeder Verkäufer als der billigste – für denselben Zug?
Liest daten/vergleich.csv (ohne Zeilen mit verdacht=ja), schreibt grafiken/gleicher_zug_anderer_preis.png (Englisch).

Aufruf: python skripte/grafik_reddit.py"""
import csv
import statistics
from collections import defaultdict
from datetime import date, timedelta

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from pfade import DATEN, VERGLEICH

ZIEL = DATEN.parent / "grafiken" / "gleicher_zug_anderer_preis.png"
MIN_VERGLEICHE = 50  # Verkäufer mit weniger Vergleichen weglassen
OHNE = {"eurostar.com"}  # nicht als Balken zeigen (zählt aber in den Kennzahlen mit)

NAMEN = {"eurostar.com": "Eurostar", "b-europe.com": "SNCB Europe", "mav.hu": "MÁV (Hungary)",
         "bahn.de": "Deutsche Bahn", "intercity.pl": "PKP Intercity", "oebb.at": "ÖBB (Austria)",
         "trenitalia.com": "Trenitalia", "ltglink.lt": "LTG Link (Lithuania)", "cd.cz": "České dráhy",
         "sbb.ch": "SBB (Switzerland)", "omio.com": "Omio (reseller)", "elron.ee": "Elron (Estonia)"}
# Stufen des Aufschlags gegenüber dem billigsten Verkäufer desselben Zuges (obere Grenze in %, Beschriftung)
STUFEN = [(0.5, "Cheapest"), (10, "+1–10%"), (25, "+10–25%"), (50, "+25–50%"), (100, "+50–100%"),
          (float("inf"), "More than double")]
# Billigste: Blaugrün; Aufschläge: Gelb -> Orange -> Rot -> Weinrot (mit validate_palette.js geprüft)
FARBEN = ["#13866a", "#fcdc8a", "#f6983f", "#de4f2c", "#a51f3e", "#581530"]
FLAECHE, TINTE, TINTE2, LEISE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
SCHRIFT = "Segoe UI"


def zahl(s):
    return float(s.replace(",", "."))


def tag(d, jahr=True):
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return f"{d:%b} {d.day}, {d.year}" if jahr else f"{d:%b} {d.day}"


def daten():
    zeilen = [z for z in csv.DictReader(open(VERGLEICH, encoding="cp1252"), delimiter=";") if z["verdacht"] != "ja"]
    pro_zug = defaultdict(list)
    for z in zeilen:
        pro_zug[(z["reise_datum"], z["strecke"], z["abfahrt"])].append(zahl(z["preis_eur"]))
    spannen = [max(p) / min(p) - 1 for p in pro_zug.values() if len(p) >= 2]
    anteile = defaultdict(lambda: [0] * len(STUFEN))
    for z in zeilen:
        a = zahl(z["aufschlag_prozent"])
        anteile[z["verkaeufer"]][next(i for i, (grenze, _) in enumerate(STUFEN) if a <= grenze)] += 1
    anteile = {v: c for v, c in anteile.items() if sum(c) >= MIN_VERGLEICHE and v not in OHNE}
    abfragen = [date.fromisoformat(z["reise_datum"]) - timedelta(days=int(z["vorlauf_tage"])) for z in zeilen]
    kennzahlen = {"zuege": len(spannen),
                  "abfrage_von": min(abfragen), "abfrage_bis": max(abfragen),
                  "unterschied": sum(s > 0.005 for s in spannen) / len(spannen),
                  "median": statistics.median(spannen),
                  "doppelt": sum(s >= 1 for s in spannen) / len(spannen),
                  "strecken": len({z["strecke"] for z in zeilen}),
                  "von": min(z["reise_datum"] for z in zeilen), "bis": max(z["reise_datum"] for z in zeilen)}
    return anteile, kennzahlen


def main():
    anteile, k = daten()
    reihen = sorted(anteile, key=lambda v: (anteile[v][0] / sum(anteile[v]), -sum(anteile[v])))
    plt.rcParams.update({"font.family": SCHRIFT, "text.color": TINTE})

    fig = plt.figure(figsize=(10, 11.2), dpi=200, facecolor=FLAECHE)
    L = 0.06  # linker Rand (Bruchteil der Breite)

    # Kopf
    fig.text(L, 0.955, "Same train. Same day. Same seat class.", fontsize=25, weight="bold")
    fig.text(L, 0.935, f"{k['zuege']:,} train departures on {k['strecken']} European routes, each priced on the same day "
             f"at several booking sites.\nTravel dates {tag(k['von'], False)} – {tag(k['bis'])}, "
             f"prices checked {tag(k['abfrage_von'], False)} – {tag(k['abfrage_bis'])}.",
             fontsize=11.5, color=TINTE2, linespacing=1.4, va="top")

    # Drei Kennzahlen
    werte = [(f"{k['unterschied']:.0%}", "of trains had different prices\ndepending on the booking site"),
             (f"{k['median']:.0%}", "median gap between the cheapest\nand the most expensive site"),
             (f"1 in {round(1 / k['doppelt'])}", "trains: at least one site\ncharged more than double")]
    for i, (zahl_, text) in enumerate(werte):
        x = L + i * 0.31
        fig.text(x, 0.825, zahl_, fontsize=30, weight="bold", color=TINTE)
        fig.text(x, 0.78, text, fontsize=10.5, color=TINTE2, linespacing=1.35)

    # Diagramm
    ax = fig.add_axes([0.255, 0.085, 0.70, 0.60], facecolor=FLAECHE)
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, len(reihen) - 0.4)
    ax.axis("off")
    hoehe = 0.62
    for y, v in enumerate(reihen):
        c = anteile[v]
        n = sum(c)
        rahmen = FancyBboxPatch((0, y - hoehe / 2), 1, hoehe, boxstyle="round,pad=0,rounding_size=0.012",
                                mutation_aspect=hoehe * 3.2, facecolor="none", edgecolor="none")
        ax.add_patch(rahmen)
        links = 0
        for i, anzahl in enumerate(c):
            breite = anzahl / n
            if breite == 0:
                continue
            seg = ax.barh(y, breite, left=links, height=hoehe, color=FARBEN[i], edgecolor=FLAECHE, linewidth=1.6)
            seg[0].set_clip_path(rahmen)
            if breite >= 0.07:
                ax.text(links + breite / 2, y, f"{breite:.0%}", ha="center", va="center", fontsize=9.5,
                        color="white" if i in (0, 3, 4, 5) else TINTE, weight="bold")
            links += breite
        fig.text(0.245, ax.transData.transform((0, y))[1] / fig.dpi / fig.get_size_inches()[1] + 0.006,
                 NAMEN.get(v, v), ha="right", va="center", fontsize=11.5, weight="semibold")
        fig.text(0.245, ax.transData.transform((0, y))[1] / fig.dpi / fig.get_size_inches()[1] - 0.012,
                 f"{n:,} prices", ha="right", va="center", fontsize=9, color=LEISE)

    # Legende über dem Diagramm, in Leserichtung der Balken
    fig.text(0.255, 0.712, "Price compared with the cheapest site for the identical train", fontsize=11,
             color=TINTE2, weight="semibold")
    x = 0.255
    for (_, name), farbe in zip(STUFEN, FARBEN):
        fig.patches.append(FancyBboxPatch((x, 0.688), 0.014, 0.011, boxstyle="round,pad=0,rounding_size=0.002",
                                          transform=fig.transFigure, facecolor=farbe, edgecolor="none"))
        t = fig.text(x + 0.019, 0.6935, name, fontsize=9.5, va="center", color=TINTE2)
        fig.canvas.draw()
        x = t.get_window_extent().x1 / fig.bbox.width + 0.018

    # Fuß
    fig.text(L, 0.045, "Prices for 1 adult, 2nd class, no discount cards; lowest fare shown for that exact departure. "
             "Sites compared only\nwhen queried on the same day. Sites with fewer than "
             f"{MIN_VERGLEICHE} comparisons left out.", fontsize=8.8, color=LEISE, linespacing=1.4)
    fig.text(L, 0.018, f"Data: own daily automated price checks, {tag(k['abfrage_von'], False)} – {tag(k['abfrage_bis'])}"
             " · Data and chart: sametrain.eu",
             fontsize=8.8, color=TINTE2)

    ZIEL.parent.mkdir(exist_ok=True)
    fig.savefig(ZIEL, facecolor=FLAECHE)
    print(ZIEL)


if __name__ == "__main__":
    main()
