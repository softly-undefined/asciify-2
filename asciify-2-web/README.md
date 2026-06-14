# Asciify 2 Web

Static frontend for Asciify 2. It supports the original monochrome renderer, a
color-aware beam search, and a post-color mode that preserves the monochrome
search's text exactly before fitting colors to its characters. Color modes copy
rich colored text for pasting into Google Docs. It can be hosted directly on
GitHub Pages.

Deploy the complete contents of this directory together. The HTML uses
versioned asset URLs so browsers and CDNs load matching copies of `app.js`,
`worker.js`, and `styles.css`. Rich clipboard writes work automatically on
HTTPS sites and localhost; other hosts use the browser's legacy copy fallback.

## Run locally

The app loads calibration files with `fetch`, so serve the directory over
HTTP instead of opening `index.html` directly:

```bash
python3 -m http.server 8000 --directory asciify-2-web
```

Then open <http://localhost:8000>.

## Rebuild calibration assets

If the source calibration models change, rebuild the packed web copies:

```bash
python3 asciify-2-web/build_calibration_assets.py
```
