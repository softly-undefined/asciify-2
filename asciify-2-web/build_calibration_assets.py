#!/usr/bin/env python3
"""Pack the Python renderer's calibration models for the static web app."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT.parent / "calibration-models"
OUTPUT_ROOT = ROOT / "calibration"
FONT_SIZES = (1, 5, 8, 11, 15, 20, 25, 30, 35)
SIZE_ONE_LINE_WIDTH = 9019
SIZE_ONE_SAFE_LINE_WIDTH = round(SIZE_ONE_LINE_WIDTH * 0.95)
SIZE_ONE_ACTUAL_POINTS = 2.25


def build_font(font_size: int) -> None:
    source = SOURCE_ROOT / str(font_size)
    model = json.loads((source / "model.json").read_text())
    manifest = json.loads((source / "manifest.json").read_text())["glyphs"]
    scale = float(model["raster"]["pixels_per_point"])

    glyphs = []
    for item in manifest:
        with Image.open(source / item["file"]) as image:
            gray = image.convert("L")
            glyphs.append(
                {
                    "char": item["char"],
                    "width": gray.width,
                    "pixels": base64.b64encode(gray.tobytes()).decode("ascii"),
                }
            )

    chars = [glyph["char"] for glyph in glyphs]
    advances = [
        float(model["advances_points"][char]) * scale
        for char in chars
    ]
    pair_advances = [
        (
            float(model["pair_advances_points"][left + right]) * scale
            if left + right in model["pair_advances_points"]
            else -1
        )
        for left in chars
        for right in chars
    ]

    packed = {
        "fontSize": font_size,
        "lineWidth": (
            SIZE_ONE_SAFE_LINE_WIDTH
            if font_size == 1
            else round(
                SIZE_ONE_LINE_WIDTH
                * SIZE_ONE_ACTUAL_POINTS
                / float(model["font"]["size_points"])
            )
        ),
        "glyphHeight": int(model["raster"]["height_pixels"]),
        "advances": advances,
        "pairAdvances": pair_advances,
        "glyphs": glyphs,
    }
    destination = OUTPUT_ROOT / f"{font_size}.json"
    destination.write_text(json.dumps(packed, separators=(",", ":")))
    print(f"Wrote {destination.relative_to(ROOT)}")


def main() -> None:
    OUTPUT_ROOT.mkdir(exist_ok=True)
    for font_size in FONT_SIZES:
        build_font(font_size)


if __name__ == "__main__":
    main()
