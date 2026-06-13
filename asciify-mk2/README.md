# Asciify mk2

`asciify_mk2.py` renders an image as variable-width ASCII intended for the
default Google Docs text settings. Each glyph is loaded from the screenshots in
`final_data`, so thin characters consume fewer pixels than wide characters.

## Current glyph set

The current `final_data` screenshots are mapped by sorted filename in this
order:

```text
abcdefghijklmnopqrstuvwxyz
ABCDEFGHIJKLMNOPQRSTUVWXYZ
1234567890
!@#$%^&*()-_+={}[]|\;"'?/.,~`
```

That is 91 captured glyphs. A synthetic blank space is added by default because
the current screenshots do not include a space. The current set is also missing
`:`, `<`, and `>`.

If you add or reorder screenshots, pass `--glyph-manifest` with a JSON mapping
instead of relying on the built-in order.

## Usage

Run from inside `asciify-mk2`:

```bash
python3 asciify_mk2.py path/to/input.png \
  --glyph-dir final_data \
  --output output/ascii.txt \
  --report output/report.json
```

Important options:

- `--beam-width`: beam size for each horizontal strip. Higher is slower and
  usually better.
- `--line-width`: output line width in pixels. Defaults to the input image
  width.
- `--num-lines`: render exactly this many lines and skip automatic tuning.
- `--min-lines`: minimum candidate line count. Defaults to `20`.
- `--max-lines`: maximum candidate line count. Defaults to `112`.
- `--sample-mode`: defaults to `stratified`, which spreads sampled strips across
  the image. Use `random` to reproduce the first plan more closely.
- `--selection-metric`: defaults to `balanced`. This uses sampled match quality
  plus a small resolution bonus so the tuner does not always prefer the minimum
  line count.
- `--resolution-weight`: the maximum line-count bonus used by `balanced`
  tuning. Defaults to `0.03`.
- `--synthetic-space-width`: pixel width for the synthetic space glyph. Defaults
  to the narrowest captured glyph.

## What the pipeline does

1. Loads the glyph screenshots and measures each glyph's pixel width.
2. If `--num-lines` is set, splits the input image into exactly that many
   horizontal strips. Otherwise, tries `20, 25, 30, ... 110, 112`.
3. Samples five stratified strips for each candidate line count.
4. Runs beam search on each sampled strip.
5. Chooses the best line count with `mean_score + resolution_bonus`.
6. Reuses sampled results for the chosen line count and renders the remaining
   lines.
7. Writes ASCII output plus a JSON report with tuning and per-line scores.

The distance metric is mean absolute pixel distance between a resized source
strip and the rendered glyph row. Scores are `1 - distance`, so higher is
better.

The original `mean_score / num_lines` metric is still available with
`--selection-metric score_per_line`, but it is no longer the default because
`mean_score` is bounded near `0..1`; dividing by the number of lines strongly
biases the result toward the minimum allowed line count.
