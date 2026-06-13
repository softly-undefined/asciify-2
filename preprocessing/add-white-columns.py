#!/usr/bin/env python3
"""
add_white_columns.py

Adds a specified number of white columns to the right side of every image in a
directory tree and writes the results to a new output directory while keeping
the original folder structure.

Usage
-----
    python add_white_columns.py \
        --input_dir  path/to/input_images \
        --output_dir path/to/output_images \
        --cols 3          # (default 3)

Supported image formats
-----------------------
Any format Pillow can read (PNG, JPG, BMP, TIFF, WEBP, …).

Dependencies
------------
- Python 3.8+
- Pillow   (pip install pillow)
- tqdm      (pip install tqdm) – optional, shows a progress bar
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


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _white_pixel(mode: str):
    """Return a tuple representing a white pixel for the given mode."""
    if mode in ("RGB", "RGBA"):
        if mode == "RGBA":
            return (255, 255, 255, 255)
        return (255, 255, 255)
    if mode == "L":
        return 255
    # Fallback – create a pixel that is maxed in every channel
    return tuple(255 for _ in range(len(mode)))


def add_white_columns(im: Image.Image, cols: int = 3) -> Image.Image:
    """Return a new image with `cols` white columns added to the right."""
    if cols <= 0:
        return im.copy()

    # For modes we can't directly paste a colour (e.g. 'P'), convert to RGB.
    if im.mode not in ("RGB", "RGBA", "L"):
        im = im.convert("RGB")

    width, height = im.size
    new_width = width + cols

    # Create a new blank image with the new width, same mode, and white background
    white = _white_pixel(im.mode)
    new_im = Image.new(im.mode, (new_width, height), white)

    # Paste the original image onto the left side
    new_im.paste(im, (0, 0))
    return new_im


def get_image_paths(root: Path) -> Iterable[Path]:
    """Yield image files under `root` (recursively)."""
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
    return (p for p in root.rglob("*") if p.suffix.lower() in exts)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add white columns to the right side of images."
    )
    parser.add_argument(
        "--input_dir",
        type=Path,
        required=True,
        help="Directory containing the original images.",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        required=True,
        help="Directory where the modified images will be written.",
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=3,
        help="Number of white columns to add to the right side (default: 3).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_root = args.input_dir
    output_root = args.output_dir
    cols = args.cols

    if not input_root.is_dir():
        print(f"Input directory {input_root} does not exist.", file=sys.stderr)
        sys.exit(1)

    image_paths = list(get_image_paths(input_root))
    if not image_paths:
        print(f"No image files found in {input_root}.")
        return

    iterator = tqdm(image_paths, desc="Adding white columns") if USE_TQDM else image_paths

    for img_path in iterator:
        rel_path = img_path.relative_to(input_root)
        out_path = output_root / rel_path
        try:
            with Image.open(img_path) as im:
                new_im = add_white_columns(im, cols)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                new_im.save(out_path)
        except Exception as exc:
            print(f"Failed to process {img_path}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
