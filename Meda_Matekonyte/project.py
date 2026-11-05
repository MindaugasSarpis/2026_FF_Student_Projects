"""
World Happiness Map (2015-2019)
-------------------------------
Interactive choropleth: deep green = happiest, deep red = unhappiest.
Use the slider (or the Play button) to move between years.

Install once (in the VS Code terminal):
    python3 -m pip install pandas plotly pycountry
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import pycountry

# ---------------------------------------------------------------------------
# 1) EDIT THIS: folder that contains 2015.csv ... 2019.csv
# ---------------------------------------------------------------------------
DATA_DIR = Path("/Users/meda/Documents/Meda_Matekonyte/2026_FF_Student_Projects/Meda_Matekonyte")   # <-- change me (tip: drag the folder into Terminal to see its path)
YEARS = [2015, 2016, 2017, 2018, 2019]
OUTPUT_HTML = DATA_DIR / "happiness_map.html"

# ---------------------------------------------------------------------------
# 2) Column names differ between the yearly files, so we normalise them
# ---------------------------------------------------------------------------
COUNTRY_COLS = ["Country", "Country or region"]
SCORE_COLS = ["Happiness Score", "Happiness.Score", "Score"]

# Names that pycountry can't resolve on its own -> ISO-3 codes.
# (Somaliland and Northern Cyprus have no ISO code and no separate shape
#  on the map, so they are left out on purpose.)
MANUAL_ISO = {
    "Congo (Brazzaville)": "COG",
    "Congo (Kinshasa)": "COD",
    "Hong Kong S.A.R., China": "HKG",
    "Ivory Coast": "CIV",
    "Kosovo": "XKX",
    "Macedonia": "MKD",
    "Palestinian Territories": "PSE",
    "Russia": "RUS",
    "Swaziland": "SWZ",
    "Taiwan Province of China": "TWN",
    "Trinidad & Tobago": "TTO",
    "Turkey": "TUR",
}
SKIP = {"North Cyprus", "Northern Cyprus", "Somaliland Region", "Somaliland region"}


def to_iso3(name: str):
    name = name.strip()
    if name in SKIP:
        return None
    if name in MANUAL_ISO:
        return MANUAL_ISO[name]
    try:
        return pycountry.countries.lookup(name).alpha_3
    except LookupError:
        print(f"  [warning] no ISO code for '{name}' - skipped")
        return None


def first_existing(df: pd.DataFrame, candidates: list[str]) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    raise KeyError(f"None of {candidates} found in columns {list(df.columns)}")


def load_year(year: int) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"{year}.csv")
    country_col = first_existing(df, COUNTRY_COLS)
    score_col = first_existing(df, SCORE_COLS)

    out = pd.DataFrame(
        {
            "Country": df[country_col].str.strip(),
            "Score": pd.to_numeric(df[score_col], errors="coerce"),
        }
    )
    out["Year"] = year
    out["ISO3"] = out["Country"].map(to_iso3)
    out = out.dropna(subset=["Score", "ISO3"])
    out["Rank"] = out["Score"].rank(ascending=False, method="min").astype(int)
    out["OutOf"] = len(out)
    return out


def main() -> None:
    data = pd.concat([load_year(y) for y in YEARS], ignore_index=True)
    data = data.sort_values(["Year", "Rank"])

    # Same colour scale for every year so colours are comparable over time
    vmin, vmax = data["Score"].min(), data["Score"].max()

    colorscale = [
        [0.00, "#67000d"],  # deep dark red   (unhappiest)
        [0.25, "#d73027"],  # red
        [0.50, "#fee08b"],  # yellow
        [0.75, "#1a9850"],  # green
        [1.00, "#00441b"],  # deep dark green (happiest)
    ]

    fig = px.choropleth(
        data,
        locations="ISO3",
        color="Score",
        hover_name="Country",
        hover_data={"ISO3": False, "Year": False, "Score": ":.3f", "Rank": True},
        animation_frame="Year",
        color_continuous_scale=colorscale,
        range_color=(vmin, vmax),
        projection="natural earth",
        title="World Happiness Score by Country",
        labels={"Score": "Happiness score"},
    )

    fig.update_geos(
        showcountries=True,
        countrycolor="#999999",
        showcoastlines=False,
        showframe=False,
        showland=True,
        landcolor="#e5e5e5",  # grey = no data for that country/year
        showocean=True,
        oceancolor="#dceefb",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=60, b=0),
        height=720,
        coloraxis_colorbar=dict(title="Happiness<br>score"),
    )

    fig.write_html(OUTPUT_HTML, include_plotlyjs="cdn")
    print(f"Saved: {OUTPUT_HTML}")
    fig.show()  # opens in your browser


if __name__ == "__main__":
    main()