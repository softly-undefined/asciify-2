# Asciify 2 Web

Static frontend for Asciify 2. It can be hosted directly on GitHub Pages.

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
