"""Measure how flicker fusion frequency changes with body mass.

For each light level, fits a straight line: CFF = intercept + slope * log10(mass).
The slope is the change in Hz for every 10x increase in body mass.

Reads:  data/raw/flicker_fusion_raw.csv
Writes: results/fit_summary.csv
Run from the project folder:  python scripts/analyse_cff.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = ROOT / "data" / "raw" / "flicker_fusion_raw.csv"
RESULTS_DIR = ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

df = pd.read_csv(RAW_FILE)
df["log10_mass"] = np.log10(df["body_mass_g"])

rows = []
for level, part in [("all", df), ("H", df[df["light_level"] == "H"]), ("L", df[df["light_level"] == "L"])]:
    slope, intercept = np.polyfit(part["log10_mass"], part["flicker_fusion_hz"], 1)
    r = part["log10_mass"].corr(part["flicker_fusion_hz"])
    rows.append({
        "light_level": level,
        "n_species": len(part),
        "slope_hz_per_10x_mass": round(slope, 2),
        "intercept_hz": round(intercept, 1),
        "correlation_r": round(r, 2),
    })

summary = pd.DataFrame(rows)
print(summary.to_string(index=False))
summary.to_csv(RESULTS_DIR / "fit_summary.csv", index=False)
print("Saved:", RESULTS_DIR / "fit_summary.csv")