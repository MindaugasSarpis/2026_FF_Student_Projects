"""Shrink the animal photos so the repository stays small.

Reads and overwrites every .jpg in site/images: at most 600 pixels wide, saved at a smaller file size.
Keep a backup of the originals before running this.
Run from the project folder:  python scripts/shrink_images.py
"""
from pathlib import Path

from PIL import Image, ImageOps

IMAGE_DIR = Path(__file__).resolve().parent.parent / "site" / "images"
MAX_WIDTH = 600

for path in sorted(IMAGE_DIR.glob("*.jpg")):
    with Image.open(path) as original:
        # Apply the camera's rotation, because saving drops it.
        img = ImageOps.exif_transpose(original).convert("RGB")

    if img.width > MAX_WIDTH:
        new_height = round(img.height * MAX_WIDTH / img.width)
        img = img.resize((MAX_WIDTH, new_height))

    img.save(path, "JPEG", quality=80, optimize=True)
    print(path.name, path.stat().st_size // 1024, "KB")