#!/usr/bin/env python3
"""
Variable-width ASCII renderer for Google Docs-style text rows.

This version treats every output line as a search problem: choose a variable
width sequence of glyph screenshots whose rendered pixels minimize mean
absolute distance from a horizontal strip of the source image.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageOps


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}

# Current final_data capture order, sorted by filename:
# lowercase, uppercase, digits, then symbols.
DEFAULT_CAPTURE_ORDER = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "1234567890"
    "!@#$%^&*()-_+={}[]|\\;\"'?/.,~`"
)


@dataclass(frozen=True)
class Glyph:
    char: str
    pixels: np.ndarray
    width: int
    height: int
    path: str | None = None
    synthetic: bool = False


@dataclass(frozen=True)
class BeamState:
    text: str
    width: int
    error_sum: float


@dataclass(frozen=True)
class LineResult:
    line_index: int
    text: str
    score: float
    distance: float
    rendered_width: int
    char_count: int

    def to_json(self) -> dict[str, Any]:
        return {
            "line_index": self.line_index,
            "score": self.score,
            "distance": self.distance,
            "rendered_width": self.rendered_width,
            "char_count": self.char_count,
            "text": self.text,
        }


@dataclass(frozen=True)
class CandidateEvaluation:
    num_lines: int
    sampled_lines: list[int]
    mean_score: float
    mean_distance: float
    score_per_line: float
    tuning_score: float

    def to_json(self) -> dict[str, Any]:
        return {
            "num_lines": self.num_lines,
            "sampled_lines": self.sampled_lines,
            "mean_score": self.mean_score,
            "mean_distance": self.mean_distance,
            "score_per_line": self.score_per_line,
            "tuning_score": self.tuning_score,
        }


def _composite_on_white(image: Image.Image) -> Image.Image:
    if "A" not in image.getbands():
        return image.convert("L")

    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    background.alpha_composite(rgba)
    return background.convert("L")


def image_to_array(image: Image.Image) -> np.ndarray:
    gray = _composite_on_white(image)
    return np.asarray(gray, dtype=np.float32) / 255.0


def load_image_array(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        return image_to_array(image)


def image_paths(root: Path) -> list[Path]:
    return sorted(
        path for path in root.iterdir() if path.suffix.lower() in IMAGE_EXTS
    )


def decode_char_label(label: str) -> str:
    if label == "space":
        return " "
    if label == "tab":
        return "\t"
    if len(label) == 1:
        return label
    try:
        decoded = label.encode("utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        decoded = label
    if len(decoded) != 1:
        raise ValueError(f"Character label must decode to exactly one character: {label!r}")
    return decoded


def load_manifest(manifest_path: Path, glyph_dir: Path) -> list[tuple[str, Path]]:
    data = json.loads(manifest_path.read_text())

    if isinstance(data, dict) and "glyphs" in data:
        data = data["glyphs"]

    if isinstance(data, dict) and "order" in data:
        order = data["order"]
        if isinstance(order, list):
            chars = [decode_char_label(str(label)) for label in order]
        else:
            chars = list(str(order))
        paths = image_paths(glyph_dir)
        if len(chars) != len(paths):
            raise ValueError(
                f"Manifest order has {len(chars)} characters, but {glyph_dir} has "
                f"{len(paths)} images."
            )
        return list(zip(chars, paths))

    if isinstance(data, dict):
        return [
            (decode_char_label(char), glyph_dir / str(file_name))
            for char, file_name in data.items()
        ]

    if isinstance(data, list):
        pairs = []
        for item in data:
            if not isinstance(item, dict) or "char" not in item or "file" not in item:
                raise ValueError(
                    "Manifest list entries must be objects with 'char' and 'file'."
                )
            pairs.append((decode_char_label(str(item["char"])), glyph_dir / item["file"]))
        return pairs

    raise ValueError("Unsupported glyph manifest format.")


def load_glyphs(
    glyph_dir: Path,
    manifest_path: Path | None = None,
    add_synthetic_space: bool = True,
    synthetic_space_width: int | None = None,
) -> list[Glyph]:
    if manifest_path:
        char_paths = load_manifest(manifest_path, glyph_dir)
    else:
        paths = image_paths(glyph_dir)
        if len(paths) != len(DEFAULT_CAPTURE_ORDER):
            raise ValueError(
                f"{glyph_dir} has {len(paths)} images, but the built-in order maps "
                f"{len(DEFAULT_CAPTURE_ORDER)} glyphs. Pass --glyph-manifest for a "
                "custom mapping."
            )
        char_paths = list(zip(DEFAULT_CAPTURE_ORDER, paths))

    glyphs: list[Glyph] = []
    expected_height: int | None = None
    for char, path in char_paths:
        if not path.exists():
            raise FileNotFoundError(f"Glyph image not found: {path}")

        pixels = load_image_array(path)
        height, width = pixels.shape
        if expected_height is None:
            expected_height = height
        elif height != expected_height:
            raise ValueError(
                f"All glyphs must have the same height. {path} is {height}px, "
                f"expected {expected_height}px."
            )

        glyphs.append(
            Glyph(
                char=char,
                pixels=pixels,
                width=width,
                height=height,
                path=str(path),
            )
        )

    if not glyphs:
        raise ValueError(f"No glyph images found in {glyph_dir}")

    if add_synthetic_space and all(glyph.char != " " for glyph in glyphs):
        height = glyphs[0].height
        width = synthetic_space_width or min(glyph.width for glyph in glyphs)
        if width <= 0:
            raise ValueError("Synthetic space width must be positive.")
        glyphs.insert(
            0,
            Glyph(
                char=" ",
                pixels=np.ones((height, width), dtype=np.float32),
                width=width,
                height=height,
                synthetic=True,
            ),
        )

    return glyphs


def split_into_strips(
    source: np.ndarray,
    num_lines: int,
    line_width: int,
    glyph_height: int,
) -> list[np.ndarray]:
    if num_lines <= 0:
        raise ValueError("num_lines must be positive.")

    height, width = source.shape
    edges = np.linspace(0, height, num_lines + 1)
    strips: list[np.ndarray] = []

    for index in range(num_lines):
        top = int(round(edges[index]))
        bottom = int(round(edges[index + 1]))
        if bottom <= top:
            bottom = min(height, top + 1)
        cropped = source[top:bottom, :]
        image = Image.fromarray(np.clip(cropped * 255.0, 0, 255).astype(np.uint8))
        resized = image.resize((line_width, glyph_height), Image.Resampling.LANCZOS)
        strips.append(np.asarray(resized, dtype=np.float32) / 255.0)

    return strips


def candidate_num_lines(min_lines: int, max_lines: int, step: int) -> list[int]:
    if min_lines <= 0 or max_lines < min_lines:
        raise ValueError("Expected 0 < min_lines <= max_lines.")
    if step <= 0:
        raise ValueError("line step must be positive.")

    values = list(range(min_lines, max_lines + 1, step))
    if values[-1] != max_lines:
        values.append(max_lines)
    return values


def trailing_white_suffix_error(target: np.ndarray) -> np.ndarray:
    column_errors = np.abs(1.0 - target).sum(axis=0)
    suffix = np.zeros(target.shape[1] + 1, dtype=np.float64)
    suffix[:-1] = np.cumsum(column_errors[::-1])[::-1]
    return suffix


def render_text_line(text: str, glyphs_by_char: dict[str, Glyph], line_width: int) -> np.ndarray:
    glyph_height = next(iter(glyphs_by_char.values())).height
    rendered = np.ones((glyph_height, line_width), dtype=np.float32)
    cursor = 0
    for char in text:
        glyph = glyphs_by_char[char]
        end = min(cursor + glyph.width, line_width)
        usable = end - cursor
        if usable > 0:
            rendered[:, cursor:end] = glyph.pixels[:, :usable]
        cursor += glyph.width
        if cursor >= line_width:
            break
    return rendered


def beam_search_strip(
    target: np.ndarray,
    glyphs: list[Glyph],
    line_index: int,
    beam_width: int,
    max_chars: int | None = None,
) -> LineResult:
    glyph_height, line_width = target.shape
    if beam_width <= 0:
        raise ValueError("beam_width must be positive.")
    if any(glyph.height != glyph_height for glyph in glyphs):
        raise ValueError("Glyph height does not match target strip height.")

    min_width = min(glyph.width for glyph in glyphs)
    if max_chars is None:
        max_chars = math.ceil(line_width / min_width)
    if max_chars <= 0:
        raise ValueError("max_chars must be positive.")

    white_suffix_error = trailing_white_suffix_error(target)
    total_pixels = float(glyph_height * line_width)
    segment_error_cache: dict[tuple[int, int], float] = {}

    def segment_error(glyph_index: int, x: int) -> float:
        key = (glyph_index, x)
        cached = segment_error_cache.get(key)
        if cached is not None:
            return cached

        glyph = glyphs[glyph_index]
        end = x + glyph.width
        err = float(np.abs(target[:, x:end] - glyph.pixels).sum())
        segment_error_cache[key] = err
        return err

    def final_distance(state: BeamState) -> float:
        return (state.error_sum + white_suffix_error[state.width]) / total_pixels

    beam = [BeamState(text="", width=0, error_sum=0.0)]
    best_state = beam[0]
    best_distance = final_distance(best_state)

    for _ in range(max_chars):
        expanded: list[BeamState] = []
        for state in beam:
            for glyph_index, glyph in enumerate(glyphs):
                new_width = state.width + glyph.width
                if new_width > line_width:
                    continue
                expanded.append(
                    BeamState(
                        text=state.text + glyph.char,
                        width=new_width,
                        error_sum=state.error_sum + segment_error(glyph_index, state.width),
                    )
                )

        if not expanded:
            break

        expanded.sort(key=lambda state: (final_distance(state), state.error_sum, state.text))
        beam = expanded[:beam_width]

        for state in beam:
            distance = final_distance(state)
            if distance < best_distance:
                best_state = state
                best_distance = distance

    return LineResult(
        line_index=line_index,
        text=best_state.text.rstrip(),
        score=1.0 - best_distance,
        distance=best_distance,
        rendered_width=best_state.width,
        char_count=len(best_state.text.rstrip()),
    )


def choose_candidate(
    evaluations: list[CandidateEvaluation],
    selection_metric: str,
) -> CandidateEvaluation:
    if selection_metric == "balanced":
        return max(
            evaluations,
            key=lambda item: (item.tuning_score, item.mean_score, item.num_lines),
        )
    if selection_metric == "score_per_line":
        return max(evaluations, key=lambda item: (item.score_per_line, item.mean_score))
    if selection_metric == "mean_score":
        return max(evaluations, key=lambda item: (item.mean_score, item.num_lines))
    raise ValueError(f"Unsupported selection metric: {selection_metric}")


def resolution_factor(num_lines: int, min_lines: int, max_lines: int) -> float:
    if max_lines <= min_lines:
        return 0.0
    return (num_lines - min_lines) / (max_lines - min_lines)


def sample_line_indices(
    num_lines: int,
    sample_size: int,
    rng: random.Random,
    sample_mode: str,
) -> list[int]:
    count = min(sample_size, num_lines)
    if sample_mode == "random":
        return sorted(rng.sample(range(num_lines), count))
    if sample_mode != "stratified":
        raise ValueError(f"Unsupported sample mode: {sample_mode}")

    raw_indices = [
        min(num_lines - 1, int(((index + 0.5) / count) * num_lines))
        for index in range(count)
    ]
    indices = sorted(set(raw_indices))
    if len(indices) == count:
        return indices

    for index in range(num_lines):
        if len(indices) == count:
            break
        if index not in indices:
            indices.append(index)
    return sorted(indices)


def asciify(
    input_path: Path,
    glyph_dir: Path,
    output_path: Path,
    report_path: Path,
    glyph_manifest: Path | None,
    min_lines: int,
    max_lines: int,
    fixed_num_lines: int | None,
    line_step: int,
    sample_lines: int,
    sample_mode: str,
    beam_width: int,
    seed: int,
    line_width: int | None,
    selection_metric: str,
    resolution_weight: float,
    add_synthetic_space: bool,
    synthetic_space_width: int | None,
    max_chars: int | None,
    quiet: bool,
) -> dict[str, Any]:
    glyphs = load_glyphs(
        glyph_dir=glyph_dir,
        manifest_path=glyph_manifest,
        add_synthetic_space=add_synthetic_space,
        synthetic_space_width=synthetic_space_width,
    )
    source = load_image_array(input_path)
    glyph_height = glyphs[0].height
    resolved_line_width = line_width or source.shape[1]
    rng = random.Random(seed)

    evaluations: list[CandidateEvaluation] = []
    sample_cache: dict[tuple[int, int], LineResult] = {}

    if fixed_num_lines is not None:
        if fixed_num_lines <= 0:
            raise ValueError("--num-lines must be positive.")
        chosen_num_lines = fixed_num_lines
        if not quiet:
            print(f"Using fixed num_lines={chosen_num_lines}", file=sys.stderr)
    else:
        for num_lines in candidate_num_lines(min_lines, max_lines, line_step):
            if not quiet:
                print(f"Sampling num_lines={num_lines}", file=sys.stderr)

            strips = split_into_strips(source, num_lines, resolved_line_width, glyph_height)
            sampled = sample_line_indices(num_lines, sample_lines, rng, sample_mode)
            results = []
            for line_index in sampled:
                result = beam_search_strip(
                    target=strips[line_index],
                    glyphs=glyphs,
                    line_index=line_index,
                    beam_width=beam_width,
                    max_chars=max_chars,
                )
                sample_cache[(num_lines, line_index)] = result
                results.append(result)

            mean_score = float(np.mean([result.score for result in results]))
            mean_distance = float(np.mean([result.distance for result in results]))
            tuning_score = mean_score + (
                resolution_weight * resolution_factor(num_lines, min_lines, max_lines)
            )
            evaluations.append(
                CandidateEvaluation(
                    num_lines=num_lines,
                    sampled_lines=sampled,
                    mean_score=mean_score,
                    mean_distance=mean_distance,
                    score_per_line=mean_score / num_lines,
                    tuning_score=tuning_score,
                )
            )

        chosen = choose_candidate(evaluations, selection_metric)
        chosen_num_lines = chosen.num_lines
        if not quiet:
            print(f"Chosen num_lines={chosen_num_lines}", file=sys.stderr)

    chosen_strips = split_into_strips(
        source,
        chosen_num_lines,
        resolved_line_width,
        glyph_height,
    )
    line_results: list[LineResult] = []
    for line_index, strip in enumerate(chosen_strips):
        cached = sample_cache.get((chosen_num_lines, line_index))
        if cached is not None:
            line_results.append(cached)
            continue

        if not quiet:
            print(
                f"Rendering line {line_index + 1}/{chosen_num_lines}",
                file=sys.stderr,
            )

        line_results.append(
            beam_search_strip(
                target=strip,
                glyphs=glyphs,
                line_index=line_index,
                beam_width=beam_width,
                max_chars=max_chars,
            )
        )

    line_results.sort(key=lambda result: result.line_index)
    mean_score = float(np.mean([result.score for result in line_results]))
    mean_distance = float(np.mean([result.distance for result in line_results]))
    if fixed_num_lines is not None:
        evaluations.append(
            CandidateEvaluation(
                num_lines=chosen_num_lines,
                sampled_lines=[],
                mean_score=mean_score,
                mean_distance=mean_distance,
                score_per_line=mean_score / chosen_num_lines,
                tuning_score=mean_score,
            )
        )

    ascii_art = "\n".join(result.text for result in line_results) + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ascii_art)

    glyph_summary = [
        {
            "char": glyph.char,
            "width": glyph.width,
            "height": glyph.height,
            "path": glyph.path,
            "synthetic": glyph.synthetic,
        }
        for glyph in glyphs
    ]
    report = {
        "input": str(input_path),
        "glyph_dir": str(glyph_dir),
        "glyph_manifest": str(glyph_manifest) if glyph_manifest else None,
        "output": str(output_path),
        "num_lines_mode": "fixed" if fixed_num_lines is not None else "auto",
        "chosen_num_lines": chosen_num_lines,
        "selection_metric": selection_metric,
        "line_width": resolved_line_width,
        "glyph_height": glyph_height,
        "beam_width": beam_width,
        "sample_lines": sample_lines,
        "sample_mode": sample_mode,
        "seed": seed,
        "resolution_weight": resolution_weight,
        "mean_score": mean_score,
        "mean_distance": mean_distance,
        "candidate_evaluations": [item.to_json() for item in evaluations],
        "lines": [result.to_json() for result in line_results],
        "glyphs": glyph_summary,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))
    return report


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render an image as variable-width Google Docs-style ASCII art."
    )
    parser.add_argument("input", type=Path, help="Source image to asciify.")
    parser.add_argument(
        "--glyph-dir",
        type=Path,
        default=Path("final_data"),
        help="Directory containing one screenshot per glyph.",
    )
    parser.add_argument(
        "--glyph-manifest",
        type=Path,
        default=None,
        help="Optional JSON mapping glyph characters to screenshot files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/ascii.txt"),
        help="Text file for generated ASCII art.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("output/report.json"),
        help="JSON report with tuning and per-line scores.",
    )
    parser.add_argument("--min-lines", type=int, default=20)
    parser.add_argument("--max-lines", type=int, default=112)
    parser.add_argument(
        "--num-lines",
        type=int,
        default=None,
        help="Render exactly this many lines and skip automatic num_lines tuning.",
    )
    parser.add_argument("--line-step", type=int, default=5)
    parser.add_argument("--sample-lines", type=int, default=5)
    parser.add_argument(
        "--sample-mode",
        choices=("stratified", "random"),
        default="stratified",
        help="How to choose sample strips during automatic tuning.",
    )
    parser.add_argument("--beam-width", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--line-width",
        type=int,
        default=None,
        help="Output line width in pixels. Defaults to the source image width.",
    )
    parser.add_argument(
        "--selection-metric",
        choices=("balanced", "mean_score", "score_per_line"),
        default="balanced",
        help="Metric used to choose num_lines.",
    )
    parser.add_argument(
        "--resolution-weight",
        type=float,
        default=0.03,
        help=(
            "Extra score given to the maximum line count in balanced tuning. "
            "Use 0 for raw mean_score behavior."
        ),
    )
    parser.add_argument(
        "--no-synthetic-space",
        action="store_true",
        help="Do not add a blank space glyph when the captures do not include one.",
    )
    parser.add_argument(
        "--synthetic-space-width",
        type=int,
        default=None,
        help="Width in pixels for the synthetic space glyph. Defaults to min glyph width.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=None,
        help="Optional hard cap for characters per output line.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    asciify(
        input_path=args.input,
        glyph_dir=args.glyph_dir,
        output_path=args.output,
        report_path=args.report,
        glyph_manifest=args.glyph_manifest,
        min_lines=args.min_lines,
        max_lines=args.max_lines,
        fixed_num_lines=args.num_lines,
        line_step=args.line_step,
        sample_lines=args.sample_lines,
        sample_mode=args.sample_mode,
        beam_width=args.beam_width,
        seed=args.seed,
        line_width=args.line_width,
        selection_metric=args.selection_metric,
        resolution_weight=args.resolution_weight,
        add_synthetic_space=not args.no_synthetic_space,
        synthetic_space_width=args.synthetic_space_width,
        max_chars=args.max_chars,
        quiet=args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
