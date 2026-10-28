# Other Eyes: an atlas of creatures

Interactive semester project: how animals see the world, where they live, and fun facts.

## Files
- `index.html` page structure
- `style.css` look and layout
- `script.js` vision effects, map, fact cards
- `data/species.json` all species info (add an entry to add a species)
- `images/sample-scene.jpg` demo image (replace with your own photo you have rights to)

## Publish with GitHub Pages
1. Upload all files (keep the `data` and `images` folders) to a public repo.
2. Settings > Pages > Source: `main` branch, `/ (root)`, then Save.
3. Your site appears at `https://USERNAME.github.io/REPO/` after a minute or two.

## Run locally
Run `python -m http.server` in this folder and open http://localhost:8000
(opening index.html by double-click will not load the JSON data).

## To do before submitting
- [ ] Replace the placeholder range shapes with real IUCN range polygons
- [ ] Verify every fact and status, and list your sources on the page
- [ ] Swap in your own photo(s) for the vision demo


## Data and sources

Data folder layout:
- `data/raw/`: data exactly as received, never edited by hand
- `data/processed/`: cleaned data, written by scripts
- `scripts/`: the Python code

**Research question:** Do smaller animals see "faster" than larger ones? (flicker fusion frequency compared with body mass)

**Main dataset:** `data/raw/flicker_fusion_raw.csv`, 34 vertebrate species, typed from the paper below and checked against the PDF.

- Healy, K., McNally, L., Ruxton, G. D., Cooper, N. & Jackson, A. L. (2013). Metabolic rate and body size are linked with perception of temporal information. *Animal Behaviour* 86(4), 685–696. Table 1.