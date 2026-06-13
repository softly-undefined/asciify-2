#!/usr/bin/env python3
"""
smart_crop_black.py

For every image in a directory tree this script removes columns from the right
until it encounters the first column that contains **at least one black pixel**.
That column (and all columns to its left) are kept; everything to its right is
deleted.  The result is written to a corresponding output directory while
preserving the original folder structure.

Usage
-----
    python smart_crop_black.py \
        --input_dir  /path/to/input_images \
        --output_dir /path/to/cropped_images

Supported formats
-----------------
Any format supported by Pillow (PNG, JPG, BMP, TIFF, WEBP, …).

Dependencies
------------
- Python 3.8+
- Pillow   (pip install pillow)
- tqdm      (pip install tqdm) – optional, shows progress bar
"""

import argparse
import sys
from pathlib import Path
from typing import Iterable

try:
    from PIL import Image
except ImportError:
    print("Missing Pillow. Install it with: pip install pillow")
    sys.exit(1)

try:
    from tqdm import tqdm
    USE_TQDM = True
except ImportError:
    USE_TQDM = False


# ----------------------------------------------------------------------------- #
# Helpers
# ----------------------------------------------------------------------------- #
def _is_black(pixel, mode: str) -> bool:
    """Return True if the pixel is considered black for the given mode."""
    if mode in ("RGB", "RGBA"):
        # For RGBA we ignore the alpha channel – a fully opaque black pixel
        if len(pixel) == 4:
            return pixel[:3] == (0, 0, 0) and pixel[3] == 255
        return pixel == (0, 0, 0)
    if mode == "L":
        return pixel == 0
    # fallback: treat pixel as black if all channels are zero
    return all(c == 0 for c in pixel)


def _column_has_black(pixels, x, height, mode: str) -> bool:
    """Return True if column `x` contains at least one black pixel."""
    for y in range(height):
        if _is_black(pixels[x, y], mode):
            return True
    return False


def find_keep_black_cutoff(im: Image.Image) -> int:
    """
    Scan the image right‑to‑left and return the first column index that
    contains a black pixel.  The image will be cropped to [0, cutoff)
    where `cutoff = index + 1`.  If no such column exists, return -1.
    """
    width, height = im.size
    mode = im.mode

    pixels = im.load()

    for x in range(width - 1, -1, -1):
        if _column_has_black(pixels, x, height, mode):
            return x + 1  # keep this column and all to the left

    return -1  # nothing to crop


def crop_to_keep_black(img_path: Path, out_path: Path) -> None:
    """Crop the image at `img_path` and write the result to `out_path`."""
    with Image.open(img_path) as im:
        cutoff = find_keep_black_cutoff(im)
        if cutoff == -1:
            cropped = im.copy()           # no cropping needed
        else:
            cropped = im.crop((0, 0, cutoff, im.height))

        out_path.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(out_path)


def get_image_paths(root: Path) -> Iterable[Path]:
    """Return an iterator over image files under `root` (recursively)."""
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
    return (p for p in root.rglob("*") if p.suffix.lower() in exts)


# ----------------------------------------------------------------------------- #
# CLI
# ----------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crop images by removing trailing columns until a black pixel is found."
    )
    parser.add_argument(
        "--input_dir",
        type=Path,
        required=True,
        help="Path to the directory containing the original images.",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        required=True,
        help="Where the cropped images will be written.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_root = args.input_dir
    output_root = args.output_dir

    if not input_root.is_dir():
        print(f"Input directory {input_root} does not exist.", file=sys.stderr)
        sys.exit(1)

    image_paths = list(get_image_paths(input_root))
    if not image_paths:
        print(f"No image files found in {input_root}.")
        return

    iterator = tqdm(image_paths, desc="Cropping") if USE_TQDM else image_paths

    for img_path in iterator:
        rel_path = img_path.relative_to(input_root)
        out_path = output_root / rel_path
        try:
            crop_to_keep_black(img_path, out_path)
        except Exception as exc:
            print(f"Failed to process {img_path}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
