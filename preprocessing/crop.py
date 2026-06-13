# this file crops a directory of images in an identical way for each image

#!/usr/bin/env python3
"""
crop_images.py

A small utility that crops every image in a directory tree by the *same*
dimensions and saves the results into an output directory.

Usage
-----
    python crop_images.py \
        --input_dir  /path/to/input_images \
        --output_dir /path/to/cropped_images \
        --width  200 \
        --height 200
    # This will centre‑crop a 200×200 square from every image

    # Crop with a custom box (left, upper, right, lower)
    python crop_images.py \
        --input_dir  /path/to/input_images \
        --output_dir /path/to/cropped_images \
        --box 50 30 250 230

    # Optional: crop from the top‑left corner
    python crop_images.py \
        --input_dir  /path/to/input_images \
        --output_dir /path/to/cropped_images \
        --box 0 0 200 200

Supported formats
-----------------
Any image type supported by Pillow (PNG, JPG, BMP, TIFF, …).

Dependencies
------------
- Python 3.8+
- Pillow   (pip install pillow)
- tqdm      (pip install tqdm) – optional, shows progress bar
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Tuple, List

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
def parse_box(box_str: str) -> Tuple[int, int, int, int]:
    """Parse a string of four integers into a tuple."""
    parts = box_str.split()
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "box must contain exactly four integers: left upper right lower"
        )
    return tuple(int(p) for p in parts)

def get_image_paths(root: Path) -> List[Path]:
    """Recursively find all image files under root."""
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
    return [p for p in root.rglob("*") if p.suffix.lower() in exts]

def ensure_dir(path: Path):
    """Create a directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Main logic
# --------------------------------------------------------------------------- #
def crop_image(
    img_path: Path,
    out_path: Path,
    box: Tuple[int, int, int, int] = None,
    center_crop: Tuple[int, int] = None,
) -> None:
    """
    Crop a single image and save the result.

    Parameters
    ----------
    img_path : Path
        Path to the source image.
    out_path : Path
        Path where the cropped image will be written.
    box : Tuple[int, int, int, int], optional
        Explicit crop rectangle (left, upper, right, lower).
    center_crop : Tuple[int, int], optional
        Width and height of a centre‑crop. Ignored if `box` is supplied.
    """
    with Image.open(img_path) as im:
        if box is None and center_crop is None:
            raise ValueError("Either box or center_crop must be supplied")

        if box:
            left, upper, right, lower = box
            # Validate
            if left < 0 or upper < 0 or right > im.width or lower > im.height:
                raise ValueError(
                    f"Crop box {box} is out of bounds for image {img_path}"
                )
            crop_box = (left, upper, right, lower)
        else:
            crop_w, crop_h = center_crop
            # Center crop logic
            left = (im.width - crop_w) // 2
            upper = (im.height - crop_h) // 2
            right = left + crop_w
            lower = upper + crop_h
            crop_box = (left, upper, right, lower)

        cropped = im.crop(crop_box)
        # Make sure output directory exists
        ensure_dir(out_path.parent)
        cropped.save(out_path)


def process_directory(
    input_dir: Path,
    output_dir: Path,
    box: Tuple[int, int, int, int] = None,
    center_crop: Tuple[int, int] = None,
):
    """
    Process all images in `input_dir`, cropping them and writing to
    `output_dir` while preserving sub‑directory structure.
    """
    image_paths = get_image_paths(input_dir)
    if not image_paths:
        print(f"No images found in {input_dir}")
        return

    iterator = tqdm(image_paths, desc="Cropping") if USE_TQDM else image_paths

    for img_path in iterator:
        # Compute relative path
        rel_path = img_path.relative_to(input_dir)
        out_path = output_dir / rel_path
        try:
            crop_image(img_path, out_path, box=box, center_crop=center_crop)
        except Exception as exc:
            print(f"Failed to crop {img_path}: {exc}", file=sys.stderr)

# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crop all images in a directory tree by the same size."
    )
    parser.add_argument(
        "--input_dir",
        required=True,
        type=Path,
        help="Path to the directory containing the original images.",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        type=Path,
        help="Where the cropped images will be written.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--box",
        type=parse_box,
        metavar="LEFT UPPER RIGHT LOWER",
        help=(
            "Four integers specifying the crop rectangle. "
            "Example: \"50 30 250 230\""
        ),
    )
    group.add_argument(
        "--center_crop",
        nargs=2,
        type=int,
        metavar=("WIDTH", "HEIGHT"),
        help="Crop a centre rectangle of the given width and height.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    center_crop = tuple(args.center_crop) if args.center_crop else None

    process_directory(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        box=args.box,
        center_crop=center_crop,
    )


if __name__ == "__main__":
    main()
