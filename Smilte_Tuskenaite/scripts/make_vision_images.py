from pathlib import Path

import pandas as pd
from PIL import Image, ImageFilter

# Find the project folder from this file's location, so it runs anywhere
ROOT = Path(__file__).resolve().parent.parent
VISION = ROOT / "site" / "vision"
PARAMS_FILE = ROOT / "data" / "vision_parameters.csv"

# Assumptions (written down so they can be changed and explained)
FIELD_DEGREES = 10   # we pretend the photo covers 10 degrees of the view

# Dichromats have two cone types, so red and green look alike.
# This matrix mixes the red and green channels together.
DICHROMAT_MATRIX = (
    0.625, 0.375, 0.0, 0,
    0.7,   0.3,   0.0, 0,
    0.0,   0.3,   0.7, 0,
)


def apply_colour_model(image, model):
    """Change the picture's colours according to the cone types."""
    if model == "dichromat":
        return image.convert("RGB", DICHROMAT_MATRIX)
    if model == "monochromat":
        return image.convert("L").convert("RGB")   # greyscale
    # trichromat: like us. tetrachromat: the extra (UV) colour cannot be
    # shown on a screen, so the colours stay as they are.
    return image


def apply_acuity(image, acuity_cpd):
    """Blur the picture to match how much fine detail the animal resolves."""
    pixels_per_degree = image.width / FIELD_DEGREES
    # The finest stripe pattern the animal can see repeats every
    # (1 / acuity) degrees. Convert that to pixels, use half as blur size.
    period_px = pixels_per_degree / acuity_cpd
    blur_px = period_px / 2
    return image.filter(ImageFilter.GaussianBlur(blur_px))


original = Image.open(VISION / "scene.jpg").convert("RGB")
params = pd.read_csv(PARAMS_FILE)

for _, row in params.iterrows():
    view = apply_colour_model(original, row["colour_model"])
    view = apply_acuity(view, row["acuity_cpd"])
    out_file = VISION / f"{row['species_id']}.jpg"
    view.save(out_file, quality=85)
    print("Saved", out_file.name)