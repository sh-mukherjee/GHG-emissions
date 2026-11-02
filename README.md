# OECD GHG Emissions Dashboard

An interactive [marimo](https://marimo.io) dashboard of OECD greenhouse-gas
emissions by country and sector, pulled from the
[OECD SDMX API](https://sdmx.oecd.org) (dataflow
`OECD.CFE.EDS:DSD_REG_CLIM@DF_GHG(2.4)`, *Greenhouse gas emissions - Regions*).

It runs **entirely in the browser** via WebAssembly, so it is hosted as a static
site — no server, no cold start, no hosting bill.

## Why the data is bundled

The original version fetched ~3,000 series from the network every time the
process started. On a sleeping free-tier host that meant a cold boot plus a full
API re-download on every visit.

Instead, `scripts/snapshot.py` downloads the data once and writes
`public/ghg.parquet` (~41k rows, ~380 KB). The app loads that file at startup,
which takes milliseconds.

## Layout

```
app.py                     the marimo notebook (the dashboard)
scripts/snapshot.py        downloads OECD SDMX data -> public/ghg.parquet
public/ghg.parquet         committed data snapshot
.github/workflows/pages.yml         export to WASM + deploy to GitHub Pages
.github/workflows/refresh-data.yml  weekly data refresh
```

## Local development

```bash
# rebuild the data snapshot (only needed when you want fresh data)
uv run scripts/snapshot.py

# run the app locally with live reload
uv run marimo edit app.py
```

## Deploying

### GitHub Pages (recommended, free)

1. Push this repository to GitHub.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. Run the **Refresh GHG data snapshot** workflow once (Actions tab → Run
   workflow) so `public/ghg.parquet` exists, then push to `main`.
   `.github/workflows/pages.yml` exports the notebook with
   `marimo export html-wasm` and publishes it.

The site appears at `https://<user>.github.io/<repo>/`.

### Hugging Face Spaces (free "Static" SDK)

Only *Static* Spaces are free now; Docker and Gradio Spaces require a paid plan.
Build the export locally and upload it:

```bash
marimo export html-wasm app.py -o dist --mode run
```

Then create a Space with the **Static** SDK and upload the *contents* of `dist/`
(`index.html`, `assets/`, `public/`). Note that `marimo export html-wasm` puts
the notebook's own `public/` directory at the root of `dist/`.

### Cloudflare

```bash
marimo export html-wasm app.py -o dist --mode run --include-cloudflare
npx wrangler deploy
```

## Refreshing the data

The `Refresh GHG data snapshot` workflow runs every Monday, rebuilds the Parquet
file, and commits it if anything changed — which in turn redeploys the site. You
can also trigger it manually from the Actions tab.

> **Data source notes.** The OECD SDMX endpoint is fast (the full extract is a
> single ~14 MB CSV that downloads in a few seconds). `scripts/snapshot.py` uses
> `format=csvfilewithlabels` so the dashboard shows readable labels
> ("United States", "GHG emissions from agriculture") rather than SDMX codes
> ("USA", "GHG_AGRICULTURE"). It still retries with backoff on network errors.

## Notes on the WASM build

- `app.py` declares its dependencies with PEP 723 metadata using
  `sys_platform` markers: pinned versions locally, Pyodide's built-in versions
  in the browser. Altair, pandas, numpy and pyarrow all ship with Pyodide.
- `requests` is intentionally **not** a runtime dependency — it is only used by
  the snapshot script. The app makes no network calls at all.
- In the browser the notebook fetches `public/ghg.parquet` with
  `pyodide.http.pyfetch` (binary-safe) instead of reading from a filesystem.
