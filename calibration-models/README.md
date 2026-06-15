# Calibrated Google Docs font sizes

Each numbered directory contains a normalized glyph raster set, manifest, and
layout model extracted from the corresponding PDF in `calibration-pdfs/`.

Available displayed Google Docs sizes: `1`, `5`, `8`, `11`, `15`, `20`, `25`,
`30`, and `35`. Google Docs internally renders displayed size `1` as `2.25pt`.

All models are normalized to the same 11pt search coordinate system, so the
default `9019px` paste-safe maximum width and aspect-preserving line calculation remain
consistent when switching sizes.

The calibration text at 15pt and larger physically wrapped in Google Docs. The
15pt model still measured every unique pair elsewhere in the document. Larger
models infer only the unique pair adjustments lost exactly at wrap boundaries
from the 11pt model:

- 15pt: 0 inferred pairs out of 8,836.
- 20pt: 30 inferred pairs out of 8,836.
- 25pt: 144 inferred pairs out of 8,836.
- 30pt: 209 inferred pairs out of 8,836.
- 35pt: 235 inferred pairs out of 8,836.
