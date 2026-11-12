"""Prepare the data for the website.

Joins the raw flicker fusion table with the common names and writes a small
JavaScript file that the website loads.

Reads:  data/raw/flicker_fusion_raw.csv, data/species_names.csv
Writes: site/species_data.js
Run from the project folder:  python scripts/build_site_data.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = ROOT / "data" / "raw" / "flicker_fusion_raw.csv"
NAMES_FILE = ROOT / "data" / "species_names.csv"
SITE_DIR = ROOT / "site"
SITE_DIR.mkdir(exist_ok=True)

species = pd.read_csv(RAW_FILE)
names = pd.read_csv(NAMES_FILE)

# Add the common name to each species, matching on species_id.
table = species.merge(names, on="species_id", how="left")

# Stop with a clear message if any species has no common name.
missing = table[table["common_name"].isna()]
if len(missing) > 0:
    raise SystemExit(f"No common name for: {list(missing['species_id'])}")

columns = ["species_id", "common_name", "latin_name",
           "flicker_fusion_hz", "body_mass_g", "light_level"]
records = table[columns].to_dict(orient="records")

# Write the records as a JavaScript variable, so index.html works by double-click.
out_file = SITE_DIR / "species_data.js"
out_file.write_text("const SPECIES = " + json.dumps(records, indent=2) + ";\n", encoding="utf-8")
print("Saved:", out_file, "with", len(records), "species")