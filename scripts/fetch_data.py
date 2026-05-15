#!/usr/bin/env python3
"""
Fetches live market data, macro indicators, news, and computes auto-alerts.
Writes output to data.json in the repo root.
Runs daily via GitHub Actions.
"""

import yfinance as yf
import feedparser
import requests
import json
import os
from datetime import datetime, timezone

# ─── MARKET DATA (yfinance, no API key needed) ────────────────────────────────

def fetch_market():
    symbols = {
        'NVDA': 'Nvidia',
        'SOXX': 'Semiconductor ETF',
        'ORCL': 'Oracle',
        'CRWV': 'CoreWeave',
    }
    result = {}
    for sym, name in symbols.items():
        try:
            t = yf.Ticker(sym)
            info = t.info
            hist = t.history(period='ytd', auto_adjust=True)

            price = info.get('currentPrice') or info.get('regularMarketPrice') or 0
            pe    = info.get('trailingPE') or 0
            chg   = info.get('regularMarketChangePercent') or 0

            ytd = 0.0
            if len(hist) > 1:
                ytd = (hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100

            result[sym] = {
                'name':       name,
                'price':      round(float(price), 2),
                'pe':         round(float(pe), 1),
                'change_pct': round(float(chg), 2),
                'ytd_pct':    round(float(ytd), 1),
            }
            print(f"  {sym}: ${price:.2f}  PE={pe:.1f}  chg={chg:.2f}%  ytd={ytd:.1f}%")
        except Exception as e:
            print(f"  ERROR {sym}: {e}")
            result[sym] = {'name': name, 'price': 0, 'pe': 0, 'change_pct': 0, 'ytd_pct': 0}
    return result

# ─── MACRO DATA (FRED API — free key at fred.stlouisfed.org) ─────────────────

def fetch_macro():
    result = {}
    key = os.environ.get('FRED_API_KEY', '')
    if not key:
        print("  No FRED_API_KEY found — skipping macro data")
        return result

    def fred_latest(series_id):
        try:
            r = requests.get(
                'https://api.stlouisfed.org/fred/series/observations',
                params={'series_id': series_id, 'api_key': key,
                        'sort_order': 'desc', 'limit': 1, 'file_type': 'json'},
                timeout=10
            )
            obs = r.json()['observations']
            return float(obs[0]['value']) if obs else None
        except Exception as e:
            print(f"  FRED {series_id} error: {e}")
            return None

    # Shiller CAPE via Nasdaq Data Link (MULTPL dataset, free DEMO key)
    try:
        r = requests.get(
            'https://data.nasdaq.com/api/v3/datasets/MULTPL/SHILLER_PE_RATIO_MONTH.json',
            params={'api_key': 'DEMO', 'rows': 1}, timeout=10
        )
        if r.status_code == 200:
            val = r.json()['dataset']['data'][0][1]
            result['cape'] = round(float(val), 1)
            print(f"  CAPE: {result['cape']}")
    except Exception as e:
        print(f"  CAPE error: {e}")

    # Buffett Indicator: household equity market value / GDP
    # NCBEILQ027S = Nonfinancial Corporate Business; Corporate Equities, Liability (billions)
    # GDP = Gross Domestic Product (billions)
    mktcap = fred_latest('NCBEILQ027S')
    gdp    = fred_latest('GDP')
    if mktcap and gdp:
        result['buffett'] = round(mktcap / gdp * 100, 1)
        print(f"  Buffett: {result['buffett']}%")

    # 10-Year Treasury Yield (DGS10) and Fed Funds Rate (DFF)
    dgs10 = fred_latest('DGS10')
    if dgs10:
        result['treasury_10y'] = round(dgs10, 2)
        print(f"  10-Yr Treasury: {result['treasury_10y']}%")

    dff = fred_latest('DFF')
    if dff:
        result['fed_funds'] = round(dff, 2)
        print(f"  Fed Funds: {result['fed_funds']}%")

    return result

# ─── TREASURY YIELD fallback via yfinance (no key needed) ────────────────────

def fetch_treasury_yield():
    """10-year US Treasury yield via ^TNX — works without FRED key."""
    try:
        t = yf.Ticker('^TNX')
        info = t.info
        price = info.get('regularMarketPrice') or info.get('currentPrice')
        if price:
            val = round(float(price), 2)
            print(f"  10-Yr Yield (yfinance): {val}%")
            return val
    except Exception as e:
        print(f"  Treasury yfinance error: {e}")
    return None

# ─── BUBBLE HISTORY (NVDA monthly, normalized to Jan 2023) ───────────────────

def fetch_bubble_history():
    """Monthly NVDA closes from Jan 2023, normalized to first close = 1.0."""
    result = []
    try:
        t = yf.Ticker('NVDA')
        hist = t.history(start='2023-01-01', auto_adjust=True)
        if hist.empty:
            return result
        try:
            monthly = hist['Close'].resample('ME').last()
        except ValueError:
            monthly = hist['Close'].resample('M').last()
        baseline = float(monthly.iloc[0])
        for i, (date, price) in enumerate(monthly.items()):
            result.append({
                'm':    i,
                'date': date.strftime('%Y-%m'),
                'v':    round(float(price) / baseline, 2),
            })
        latest = result[-1]
        print(f"  NVDA bubble: {len(result)} months, now={latest['v']:.2f}x (m={latest['m']})")
    except Exception as e:
        print(f"  Bubble history error: {e}")
    return result

# ─── NEWS (Google News RSS, no key needed) ────────────────────────────────────

NEWS_QUERIES = [
    'OpenAI IPO revenue miss bubble 2026',
    'AI bubble capex Microsoft Google Meta Amazon',
    'Nvidia semiconductor overvalued 2026',
    'OpenAI CoreWeave Oracle financial',
]

def fetch_news():
    articles = []
    seen = set()
    for q in NEWS_QUERIES:
        url = f'https://news.google.com/rss/search?q={q.replace(" ", "+")}&hl=en-US&gl=US&ceid=US:en'
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:4]:
                raw_title = entry.get('title', '')
                # Google News format: "Headline — Source"
                parts = raw_title.rsplit(' - ', 1)
                title  = parts[0].strip()
                source = parts[1].strip() if len(parts) > 1 else ''
                if title and title not in seen:
                    seen.add(title)
                    articles.append({
                        'title':  title,
                        'url':    entry.get('link', ''),
                        'source': source,
                        'date':   entry.get('published', ''),
                    })
                    if len(articles) >= 15:
                        return articles
        except Exception as e:
            print(f"  RSS error ({q[:30]}): {e}")
    return articles

# ─── AUTO-ALERTS (rule-based signal detection) ────────────────────────────────

def compute_alerts(market):
    alerts = []

    def add(level, msg):
        alerts.append({'level': level, 'msg': msg})

    nvda  = market.get('NVDA', {})
    soxx  = market.get('SOXX', {})
    orcl  = market.get('ORCL', {})
    crwv  = market.get('CRWV', {})

    # ─ Oracle (OpenAI proxy)
    if orcl.get('change_pct', 0) < -5:
        add('red',    f"ORCL dropped {orcl['change_pct']:.1f}% today — OpenAI/Oracle contract stress signal")
    elif orcl.get('change_pct', 0) < -2:
        add('yellow', f"ORCL down {orcl['change_pct']:.1f}% — watch for OpenAI news")

    # ─ CoreWeave (AI infra stress)
    if crwv.get('change_pct', 0) < -7:
        add('red',    f"CRWV dropped {crwv['change_pct']:.1f}% — AI infrastructure financing stress")
    elif crwv.get('change_pct', 0) < -3:
        add('yellow', f"CRWV down {crwv['change_pct']:.1f}% — CoreWeave under pressure")

    # ─ Nvidia
    if nvda.get('change_pct', 0) < -7:
        add('red',    f"NVDA dropped {nvda['change_pct']:.1f}% — semiconductor demand signal")
    elif nvda.get('change_pct', 0) > 7:
        add('yellow', f"NVDA surged {nvda['change_pct']:.1f}% — bubble extending signal")

    if nvda.get('pe', 0) > 70:
        add('red',    f"Nvidia P/E hit {nvda['pe']}x — extreme valuation territory")

    # ─ SOXX YTD
    if soxx.get('ytd_pct', 0) > 90:
        add('red',    f"SOXX up {soxx['ytd_pct']:.0f}% YTD — Burry's 1999 warning level exceeded")
    elif soxx.get('ytd_pct', 0) > 60:
        add('yellow', f"SOXX up {soxx['ytd_pct']:.0f}% YTD — entering Burry's danger zone")

    return alerts

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n=== Bubble Tracker Data Update {datetime.now(timezone.utc).isoformat()} ===\n")

    print("Fetching market data...")
    market = fetch_market()

    print("\nFetching macro indicators...")
    macro = fetch_macro()

    # Fill in treasury yield via yfinance if FRED didn't provide it
    if 'treasury_10y' not in macro:
        print("\nFetching Treasury yield (yfinance fallback)...")
        ty = fetch_treasury_yield()
        if ty:
            macro['treasury_10y'] = ty

    print("\nFetching news...")
    news = fetch_news()
    print(f"  Got {len(news)} articles")

    print("\nComputing auto-alerts...")
    alerts = compute_alerts(market)
    print(f"  {len(alerts)} alerts generated")

    print("\nFetching NVDA bubble history...")
    bubble_history = fetch_bubble_history()

    data = {
        'updated':        datetime.now(timezone.utc).isoformat(),
        'market':         market,
        'macro':          macro,
        'news':           news,
        'alerts':         alerts,
        'bubble_history': bubble_history,
    }

    with open('data.json', 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ data.json written  ({len(news)} news items, {len(alerts)} alerts)\n")

if __name__ == '__main__':
    main()
