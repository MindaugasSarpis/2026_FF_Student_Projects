"""Vergleicht die Preise derselben Verbindung bei verschiedenen Verkäufern.

    python skripte/auswertung.py              alle Reisetage
    python skripte/auswertung.py 2026-10-22   nur ein Reisetag

Zwei Verbindungen verschiedener Verkäufer gelten als dieselbe, wenn Strecke und Reisetag gleich sind und
    - Abfahrt und Ankunft übereinstimmen ("gleiche Zeiten"), oder
    - sie eine Zugnummer gemeinsam haben und die Zeiten nur wenig abweichen ("gleiche Zugnummer"),
      z. B. weil ein Verkäufer bis zu einem anderen Bahnhof derselben Stadt rechnet.
Je Verkäufer zählt der niedrigste Preis der letzten Abfrage; wurde derselbe Reisetag an einem Tag mehrmals
abgefragt, gilt davon nur die erste erfolgreiche Abfrage des Tages. Das Ergebnis steht zusätzlich in
daten/vergleich.csv (eine Zeile je Verbindung und Verkäufer).

Rolle des Verkäufers (aus listen/strecken_laender.csv):
    Start/Ziel  - sein Land ist Abfahrts- oder Ankunftsland
    Durchgang   - der Zug fährt durch sein Land
    kein Bezug  - weder noch
    Vermittler  - verkauft Tickets vieler Bahnen, ohne selbst Züge zu fahren (Omio)
"""
import collections
import csv
import re
import statistics
import sys
from datetime import date as Date

from kurse import euro_rate
from pfade import ABFRAGEN_LOG, BILLIGSTE_FAHRT, LAENDER, PREISE, VERGLEICH

# Verkäufer und ihr Land (Eurostar fährt die Züge selbst: zählt auf seinen Strecken als Start/Ziel)
SELLERS = {
    "bahn.de": {"DE"}, "oebb.at": {"AT"}, "sbb.ch": {"CH"}, "ltglink.lt": {"LT"}, "elron.ee": {"EE"},
    "vivi.lv": {"LV"}, "koleo.pl": {"PL"}, "intercity.pl": {"PL"}, "trenitalia.com": {"IT"},
    "mav.hu": {"HU"}, "cd.cz": {"CZ"}, "b-europe.com": {"BE"}, "ouigo.com": {"FR"}, "eurostar.com": {"DE", "BE", "FR"},
    "nsinternational.com": {"NL"}, "regiojet.com": {"CZ"}, "cfrcalatori.ro": {"RO"},
    "omio.com": set(),  # Vermittler, siehe role()
}
VERMITTLER = {"omio.com"}
# Kürzel der Seite in strecken.csv und abfragen_log.csv -> Verkäufer in preise.csv
QUELLE = {
    "db": "bahn.de", "oebb": "oebb.at", "sbb": "sbb.ch", "ltg": "ltglink.lt", "elron": "elron.ee", "vivi": "vivi.lv",
    "koleo": "koleo.pl", "pkp": "intercity.pl", "trenitalia": "trenitalia.com", "mav": "mav.hu", "cd": "cd.cz",
    "sncb": "b-europe.com", "ouigo": "ouigo.com", "eurostar": "eurostar.com", "omio": "omio.com",
    "ns": "nsinternational.com", "regiojet": "regiojet.com", "cfr": "cfrcalatori.ro",
}
# Fremdwährungen werden mit dem EZB-Referenzkurs des Abfragetags umgerechnet (siehe kurse.py)
used_rates = {}
# Ab diesem Faktor zwischen teuerstem und billigstem Verkäufer wird ein Paar zum Nachprüfen markiert
# (möglicher Teilpreis oder Spar- gegen Normalpreis); in die Statistik geht es trotzdem ein
SUSPICIOUS = 3.0
# Vorlauf = Tage zwischen Abfrage und Reisetag, für die Auswertung in Gruppen zusammengefasst
LEAD_GROUPS = [(10, "bis 10 Tage"), (30, "11 bis 30 Tage"), (10000, "über 30 Tage")]
# Paarung über die Zugnummer: so viele Minuten dürfen Abfahrt bzw. Ankunft höchstens abweichen
MAX_DEP_DIFF, MAX_ARR_DIFF = 15, 20

day = sys.argv[1] if len(sys.argv) > 1 else ""
with open(LAENDER, encoding="utf-8-sig", newline="") as f:
    countries = {r["nr"]: r for r in csv.DictReader(f, delimiter=";")}


def role(seller, nr):
    if seller in VERMITTLER:
        return "Vermittler"
    c, lands = countries[nr], SELLERS[seller]
    if lands & {c["start_land"], c["ziel_land"]}:
        return "Start/Ziel"
    return "Durchgang" if lands & set(c["durchgang"].split()) else "kein Bezug"


def euro(r):
    if not r["preis"]:
        return None
    rate, rate_day = euro_rate(r["waehrung"], r["abfrage_datum"])
    if r["waehrung"] != "EUR":
        used_rates[(r["waehrung"], r["abfrage_datum"])] = (rate, rate_day)
    price = round(float(r["preis"].replace(",", ".")) * rate, 2)
    if r["quelle"] in VERMITTLER:
        price += servicegebuehr(price)
    return price


def servicegebuehr(price):
    """Omio schlägt beim Bezahlen eine Servicegebühr auf, die in der Suche fehlt. Geschätzt aus den von Hand
    abgelesenen Werten in daten/omio_gebuehren.csv: etwa 6,5 % des Ticketpreises, auf ganze Euro gerundet,
    mindestens 2 € (16,90 → 2, 54 → 4, 142 → 9). In preise.csv bleibt der Preis ohne Gebühr."""
    return max(2, round(price * 0.065))


def minutes(clock):
    return int(clock[:2]) * 60 + int(clock[3:])


def train_numbers(text):
    """Zugnummern als Menge: 'EC 48 + S5' -> {'48'}, '31/145' -> {'31', '145'}."""
    return {n.lstrip("0") for n in re.findall(r"\d{2,5}", text)}


def lead_group(r):
    days = (Date.fromisoformat(r["reise_datum"]) - Date.fromisoformat(r["abfrage_datum"])).days
    return days, next(name for limit, name in LEAD_GROUPS if days <= limit)


with open(PREISE, encoding="utf-8", newline="") as f:
    price_rows = [r for r in csv.DictReader(f, delimiter=";")
                  if r["quelle"] in SELLERS and r["strecke_nr"] in countries and (not day or r["reise_datum"] == day)]

# Wurde ein Reisetag am selben Tag mehrmals abgefragt, zählt je Strecke und Verkäufer nur die erste erfolgreiche
# Abfrage dieses Tages laut abfragen_log.csv (Status wie ERLEDIGT in alle_strecken.py): eine Wiederholung nach einem
# Fehlschlag zählt, eine zweite erfolgreiche Abfrage (z. B. doppelter Lauf nach einem Neustart) nicht.
# Abfragen ohne erfolgreichen Logeintrag (z. B. von Hand gestartet): die früheste Zeit in preise.csv
ERLEDIGT = {"gespeichert", "keine Verbindungen"}
first_query, log_starts = {}, collections.defaultdict(list)
for r in price_rows:
    k = (r["strecke_nr"], r["reise_datum"], r["abfrage_datum"], r["quelle"])
    first_query[k] = min(first_query.get(k, "99:9"), r["abfrage_uhrzeit"][:4])
with open(ABFRAGEN_LOG, encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f, delimiter=";"):
        log_starts[(r["nr"], r["reise_datum"], r["abfrage_datum"], QUELLE.get(r["seite"]))].append(
            (r["abfrage_uhrzeit"], r["status"]))
# Zeitfenster der ersten erfolgreichen Abfrage: von ihrem Start bis zum Start der nächsten Abfrage
window = {}
for k, starts in log_starts.items():
    starts.sort()
    ok = next((i for i, (_, status) in enumerate(starts) if status in ERLEDIGT), None)
    if ok is not None:
        window[k] = (starts[ok][0], starts[ok + 1][0] if ok + 1 < len(starts) else "99:99")


def counts(r):
    k = (r["strecke_nr"], r["reise_datum"], r["abfrage_datum"], r["quelle"])
    if k in window:
        return window[k][0] <= r["abfrage_uhrzeit"] < window[k][1]
    return r["abfrage_uhrzeit"][:4] == first_query[k]


# (nr, reisetag) -> (verkäufer, abfahrt, ankunft) -> Zeilen der letzten Abfrage
offers = collections.defaultdict(lambda: collections.defaultdict(list))
for r in price_rows:
    if counts(r):
        rows = offers[(r["strecke_nr"], r["reise_datum"])][(r["quelle"], r["abfahrt"], r["ankunft"])]
        stamp = (r["abfrage_datum"], r["abfrage_uhrzeit"][:4])
        if rows and (rows[0]["abfrage_datum"], rows[0]["abfrage_uhrzeit"][:4]) < stamp:
            rows.clear()
        rows.append(r)


def same_connection(a, rows_a, b, rows_b):
    """'' wenn verschieden, sonst die Art der Übereinstimmung."""
    if a[0] == b[0]:
        return ""
    if a[1:] == b[1:]:
        return "gleiche Zeiten"
    shared = train_numbers(rows_a[0]["zuege"]) & train_numbers(rows_b[0]["zuege"])
    if (shared and abs(minutes(a[1]) - minutes(b[1])) <= MAX_DEP_DIFF
            and abs(minutes(a[2]) - minutes(b[2])) <= MAX_ARR_DIFF):
        return "gleiche Zugnummer"
    return ""


out, by_role, no_price = [], collections.defaultdict(list), collections.defaultdict(lambda: [0, 0])
by_lead = collections.defaultdict(lambda: collections.defaultdict(list))  # Vorlaufgruppe -> Verkäufer -> Aufschläge
pair_kinds = collections.Counter()
for (nr, date), conns in sorted(offers.items(), key=lambda kv: (int(kv[0][0]), kv[0][1])):
    # Verbindungen zu Gruppen zusammenfassen; je Gruppe höchstens eine Verbindung pro Verkäufer
    groups = []
    for key in sorted(conns, key=lambda k: (k[1], k[2], k[0])):
        for group in groups:
            if any(k[0] == key[0] for k in group["keys"]):
                continue
            kinds = [same_connection(key, conns[key], other, conns[other]) for other in group["keys"]]
            if any(kinds):
                group["keys"].append(key)
                if "gleiche Zugnummer" in kinds and "gleiche Zeiten" not in kinds:
                    group["art"] = "gleiche Zugnummer"
                break
        else:
            groups.append({"keys": [key], "art": "gleiche Zeiten"})

    for group in groups:
        best = {}
        for key in group["keys"]:
            priced = [(euro(r), r) for r in conns[key] if euro(r) is not None]
            counter = no_price[role(key[0], nr)]
            counter[0] += 1
            counter[1] += not priced
            if priced:
                best[key[0]] = min(priced, key=lambda x: x[0]) + (key,)
        if len(best) < 2:
            continue
        pair_kinds[group["art"]] += 1
        low, high = min(b[0] for b in best.values()), max(b[0] for b in best.values())
        suspicious = low > 0 and high / low >= SUSPICIOUS
        dep, arr = group["keys"][0][1:]
        trains = next((b[1]["zuege"] for b in best.values() if b[1]["zuege"]), "")
        for seller, (price, r, key) in sorted(best.items(), key=lambda kv: kv[1][0]):
            extra = round((price / low - 1) * 100) if low else ""
            by_role[role(seller, nr)].append(extra)
            days, lead = lead_group(r)
            by_lead[lead][seller].append(extra)
            out.append([date, nr, countries[nr]["strecke"], dep, arr, trains, seller, role(seller, nr), key[1], key[2],
                        r["preis"], r["waehrung"], f"{price:.2f}".replace(".", ","),
                        "inkl. geschätzter Servicegebühr" if seller in VERMITTLER else r["tarif"],
                        f"{low:.2f}".replace(".", ","), extra, "ja" if suspicious else "", days, group["art"]])

header = ["reise_datum", "nr", "strecke", "abfahrt", "ankunft", "zuege", "verkaeufer", "rolle", "abfahrt_verkaeufer",
          "ankunft_verkaeufer", "preis", "waehrung", "preis_eur", "tarif", "billigster_eur", "aufschlag_prozent",
          "verdacht", "vorlauf_tage", "paarung"]
with open(VERGLEICH, "w", newline="", encoding="utf-8") as f:
    csv.writer(f, delimiter=";").writerows([header] + out)

# Billigste Fahrt je Strecke und Reisetag über alle Züge, auch solche, die nur ein Verkäufer anbietet
# (z. B. OUIGO, RegioJet). vergleich.csv kennt nur Züge mit mindestens zwei Verkäufern und beantwortet daher nicht,
# wo man die Strecke insgesamt am billigsten fährt. Gleiche Abfragen wie oben (letzte gezählte Abfrage je Reisetag).
cheapest = []
for (nr, date), conns in sorted(offers.items(), key=lambda kv: (int(kv[0][0]), kv[0][1])):
    priced = [(euro(r), key, r) for key, rows in conns.items() for r in rows if euro(r) is not None]
    if not priced:
        continue
    price, key, r = min(priced, key=lambda x: (x[0], x[1][1]))
    sellers = {k[0] for k in conns}
    cheapest.append([date, nr, countries[nr]["strecke"], r["abfrage_datum"], lead_group(r)[0], key[0], key[1], key[2],
                     r["zuege"], f"{price:.2f}".replace(".", ","), len(sellers)])
with open(BILLIGSTE_FAHRT, "w", newline="", encoding="utf-8") as f:
    csv.writer(f, delimiter=";").writerows([["reise_datum", "nr", "strecke", "abfrage_datum", "vorlauf_tage", "verkaeufer",
                                             "abfahrt", "ankunft", "zuege", "preis_eur", "verkaeufer_abgefragt"]] + cheapest)

last = None
for row in out:
    key = tuple(row[:5])
    if key != last:
        note = ("   VERDACHT" if row[16] else "") + ("   (über Zugnummer)" if row[18] == "gleiche Zugnummer" else "")
        print(f"\n{row[1]:>2} {row[2]:20} {row[0][5:]} {row[3]}-{row[4]}  [{row[5][:34]}]" + note)
        last = key
    print(f"      {row[6]:15} {row[7]:10} {row[8]}-{row[9]} {row[12]:>8} €  +{row[15]:>3} %  {row[13]}")

print(f"\n{sum(pair_kinds.values())} Verbindungen mit Preis bei mindestens zwei Verkäufern -> vergleich.csv")
print("  gepaart über " + ", ".join(f"{kind}: {n}" for kind, n in pair_kinds.most_common()))
print("\nAufschlag gegenüber dem billigsten Verkäufer, nach Rolle (einschließlich der markierten Fälle):")
for name in ("Start/Ziel", "Durchgang", "kein Bezug", "Vermittler"):
    values = by_role.get(name, [])
    total, missing = no_price[name]
    if values:
        print(f"  {name:10}  {len(values):>3} Preise, Median +{statistics.median(values):.0f} %, "
              f"am billigsten in {sum(v == 0 for v in values) * 100 // len(values)} % der Fälle"
              f" | ohne Preis: {missing} von {total} gefundenen Verbindungen")
    elif total:
        print(f"  {name:10}  keine vergleichbaren Preise | ohne Preis: {missing} von {total} gefundenen Verbindungen")
print("\nWie oft war ein Verkäufer der billigste, nach Vorlauf (Zahl der Vergleiche in Klammern):")
print("  " + " " * 15 + "".join(f"{name:>18}" for _, name in LEAD_GROUPS))
for seller in sorted({s for group in by_lead.values() for s in group}):
    cells = []
    for _, name in LEAD_GROUPS:
        values = by_lead[name].get(seller, [])
        cells.append(f"{sum(v == 0 for v in values) * 100 // len(values)} % ({len(values)})" if values else "-")
    print(f"  {seller:15}" + "".join(f"{c:>18}" for c in cells))
print("\nUmrechnung mit EZB-Referenzkursen des Abfragetags:")
for (currency, asked), (rate, rate_day) in sorted(used_rates.items()):
    print(f"  Abfrage {asked}: 1 {currency} = {rate:.5f} EUR (Kurs vom {rate_day})")
