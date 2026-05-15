# AI Bubble Tracker

A mobile dashboard that tracks AI bubble indicators with daily auto-updated market data, macro indicators, and news.

## How it works

- **GitHub Actions** runs every weekday at 9 am US Eastern
- Fetches live prices (yfinance), macro data (FRED), and news (Google RSS)
- Writes `data.json` and commits it to the repo
- **GitHub Pages** serves `index.html`, which fetches `data.json` on every page load

## Setup (5 minutes)

### 1. Create the repo

Go to [github.com/new](https://github.com/new) and create a public repo named `bubble-tracker`.

### 2. Push this folder

```bash
cd /Users/beomjoopark/bubble-tracker
git init
git add .
git commit -m "init"
git remote add origin https://github.com/YOUR_USERNAME/bubble-tracker.git
git push -u origin main
```

### 3. Enable GitHub Pages

Go to your repo → **Settings → Pages** → Source: **Deploy from a branch** → Branch: `main` → folder: `/ (root)` → Save.

Your dashboard will be live at: `https://YOUR_USERNAME.github.io/bubble-tracker/`

### 4. (Optional) Add FRED API key for Buffett Indicator

Free key at [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html).

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

- Name: `FRED_API_KEY`
- Value: your key

Without it, the Buffett Indicator and CAPE won't auto-update (they stay at seed values until you add the key).

### 5. Add to Android home screen

1. Open the GitHub Pages URL in Chrome
2. Tap ⋮ menu → "Add to Home screen"
3. Opens like an app from then on

## Manual trigger

In your repo → **Actions** → "Update Bubble Data" → **Run workflow** button to fetch data immediately.

## Files

| File | Purpose |
|------|---------|
| `index.html` | Dashboard (all UI, fetches data.json on load) |
| `data.json` | Auto-updated daily by GitHub Actions |
| `scripts/fetch_data.py` | Python data fetcher |
| `.github/workflows/update.yml` | Daily automation schedule |
