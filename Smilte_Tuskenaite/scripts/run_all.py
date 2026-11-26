import subprocess
import sys
from pathlib import Path

# Find the scripts folder from this file's location, so it runs anywhere
SCRIPTS = Path(__file__).resolve().parent

# The steps, in the order they must run
STEPS = [
    "analyse_cff.py",
    "plot_cff_vs_mass.py",
    "build_site_data.py",
    "make_vision_images.py",
]

for step in STEPS:
    print(f"--- Running {step} ---")
    # sys.executable is the same Python that is running this file
    # check=True stops everything if a step fails
    subprocess.run([sys.executable, str(SCRIPTS / step)], check=True)

print("All steps finished.")