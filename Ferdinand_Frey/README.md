# Same train, different price

Semester project for *Best Research and Data Analysis Practices from CERN* (autumn 2026), Ferdinand Frey.

Question: If you buy a ticket for the same European train from different sellers (the national railways of the
start and destination country, other railways, ticket resellers), how much does the price differ, which seller is
usually the cheapest, and does that depend on how early you book?

Every day a set of Selenium scripts asks up to 16 sellers for the price of the same trains on about 100 routes,
for travel dates 1, 7, 21 and 42 days ahead. The analysis matches identical trains across sellers and compares them.
Results are published at [sametrain.eu](https://sametrain.eu).

## Data

| File | Content |
|---|---|
| `daten/preise.csv` | Raw data: one row per connection found per query (query date and time, travel date, route, seller, times, train numbers, fare name, price, currency, remark) |
| `daten/abfragen_log.csv` | One row per query: success, number of connections, error |
| `daten/kurse.csv` | ECB euro reference rates, used to convert CHF, PLN, CZK, HUF and RON prices to euro |
| `listen/strecken.csv` | Which routes are queried at which seller (`nr;strecke;seite;start;ziel`) |
| `daten/vergleich.csv`, `daten/billigste_fahrt.csv` | Results, written by `skripte/auswertung.py` |

The data were collected by the scripts in this folder from the sellers' public websites, 2nd class, one adult,
no discount cards. This folder holds a snapshot: raw data up to 7 days before the newest query (here up to
1 November 2026), the same delay as the public dataset. The full, regularly updated dataset is on Zenodo
([10.5281/zenodo.23669337](https://doi.org/10.5281/zenodo.23669337)) and
[GitHub](https://github.com/UrzasMine/same-train-different-price), licence CC BY 4.0.

Prices count only if they are for the whole route. Prices for just part of it are kept but marked
`bemerkung = nur Teilpreis` and ignored.

## How to run

The analysis needs Python 3 (tested with 3.14) and one package (`certifi`, used to fetch missing exchange rates):

```bash
git clone https://github.com/<your-username>/2026_FF_Student_Projects.git
cd 2026_FF_Student_Projects/Ferdinand_Frey
python -m venv .venv
.venv\Scripts\activate          # Windows; on Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python skripte/auswertung.py
```

`auswertung.py` reads `daten/preise.csv` and rewrites `daten/vergleich.csv` and `daten/billigste_fahrt.csv`.
On the committed data the output is identical to the committed files (`git status` shows no change).
On Windows, if you redirect the output to a file, set `PYTHONUTF8=1` first (station names contain Polish letters).

Collecting new prices (optional, not reproducible): `python taeglich.py` queries all routes for the travel dates
1, 7, 21 and 42 days ahead. It needs Windows and Google Chrome, takes several hours, and gives different numbers on
every run because live prices change and websites change their layout. A single seller can be queried with
`python skripte/<seller>.py <travel date> <time>`. Code comments and column names are in German.

## Results (snapshot up to 1 November 2026)

5,847 trains on 83 routes and 49 travel dates were offered by at least two sellers.
For 5,207 of them (89 %) the sellers asked different prices; the median gap between the cheapest and the most
expensive offer was 17 €, the largest 243 €.

| Seller | Compared trains | Cheapest (or tied) | Average surcharge over the cheapest |
|---|---:|---:|---:|
| bahn.de | 3,202 | 66 % | 23 % |
| omio.com (reseller) | 2,630 | 4 % | 18 % |
| oebb.at | 1,883 | 53 % | 40 % |
| eurostar.com | 1,219 | 100 % | 0 % |
| cd.cz | 996 | 51 % | 33 % |
| sbb.ch | 977 | 30 % | 14 % |
| trenitalia.com | 786 | 58 % | 21 % |
| b-europe.com | 664 | 91 % | 1 % |
| mav.hu | 630 | 74 % | 4 % |
| intercity.pl | 387 | 70 % | 9 % |

In short: no seller is always the cheapest. Railways of the start or destination country were the cheapest (or tied)
for 67 % of their offers, other railways for about half, and the reseller Omio for 4 %.
Per-route results, including prices by booking lead time, are on [sametrain.eu](https://sametrain.eu).

Figures: `grafiken/gleicher_zug_anderer_preis.png`, `grafiken/interrail_wo_buchen.png`.

## Folder structure

```
Ferdinand_Frey/
├── README.md
├── requirements.txt
├── taeglich.py            daily run: all routes, 4 travel dates, then the analysis
├── fortsetzen.py          continues an interrupted daily run
├── skripte/               one script per seller (db.py, oebb.py, ...), shared code, analysis, website
├── listen/                route lists
├── daten/                 raw data and results
└── grafiken/              figures
```
