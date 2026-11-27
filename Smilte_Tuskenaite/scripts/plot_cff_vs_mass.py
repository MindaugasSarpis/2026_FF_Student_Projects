"""Plot flicker fusion frequency against body mass.

Reads:  data/raw/flicker_fusion_raw.csv   (never edited by hand)
Writes: results/cff_vs_mass.png
Run from the project folder:  python scripts/plot_cff_vs_mass.py
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Paths are built from this file's location, so the script works from any folder.
ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = ROOT / "data" / "raw" / "flicker_fusion_raw.csv"
RESULTS_DIR = ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

df = pd.read_csv(RAW_FILE)
print("Rows and columns:", df.shape)
print(df[["latin_name", "flicker_fusion_hz", "body_mass_g"]].head())

fig, ax = plt.subplots(figsize=(8, 5))
colours = {"H": "tab:orange", "L": "tab:blue"}
labels = {"H": "High light", "L": "Low light"}
for level in ("H", "L"):
    part = df[df["light_level"] == level]
    ax.scatter(part["body_mass_g"], part["flicker_fusion_hz"],
               color=colours[level], label=labels[level], s=45)

human = df[df["latin_name"] == "Homo sapiens"].iloc[0]
ax.annotate("Human", (human["body_mass_g"], human["flicker_fusion_hz"]),
            textcoords="offset points", xytext=(8, 6))

ax.set_xscale("log")
ax.set_xlabel("Body mass (g, log scale)")
ax.set_ylabel("Flicker fusion frequency (Hz)")
ax.set_title("Flicker fusion frequency vs body mass, 34 vertebrates")
ax.legend()
fig.tight_layout()
out_file = RESULTS_DIR / "cff_vs_mass.png"
fig.savefig(out_file, dpi=150)
print("Saved:", out_file)
