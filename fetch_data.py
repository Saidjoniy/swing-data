#!/usr/bin/env python3
"""Fetch ~1y of daily OHLCV for all watchlist tickers via yfinance.

Runs wherever network access to Yahoo Finance exists (GitHub Action or
an allowlisted sandbox). Output: data/prices.parquet (long format).
"""
import sys
import time
import pandas as pd
import yfinance as yf
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "data"
OUT.mkdir(exist_ok=True)

def main():
    tickers = [t.strip().upper() for t in (ROOT / "watchlist.txt").read_text().splitlines() if t.strip()]
    print(f"Fetching {len(tickers)} tickers...")
    frames = []
    CHUNK = 50
    for i in range(0, len(tickers), CHUNK):
        chunk = tickers[i:i + CHUNK]
        for attempt in range(3):
            try:
                df = yf.download(chunk, period="1y", interval="1d",
                                 group_by="ticker", auto_adjust=True,
                                 threads=True, progress=False)
                break
            except Exception as e:
                print(f"chunk {i}: retry {attempt+1} after error: {e}", file=sys.stderr)
                time.sleep(15)
        else:
            continue
        for t in chunk:
            try:
                sub = df[t].dropna(how="all")
            except KeyError:
                continue
            if sub.empty:
                continue
            sub = sub.reset_index()
            sub.columns = [c.lower() for c in sub.columns]
            sub["ticker"] = t
            frames.append(sub[["ticker", "date", "open", "high", "low", "close", "volume"]])
        print(f"  {min(i+CHUNK, len(tickers))}/{len(tickers)} done")
        time.sleep(2)

    all_df = pd.concat(frames, ignore_index=True)
    all_df["date"] = pd.to_datetime(all_df["date"]).dt.tz_localize(None)
    all_df.to_parquet(OUT / "prices.parquet", index=False)
    got = all_df["ticker"].nunique()
    print(f"Saved {got} tickers, {len(all_df)} rows -> data/prices.parquet")
    missing = sorted(set(tickers) - set(all_df["ticker"].unique()))
    if missing:
        print(f"MISSING ({len(missing)}): {','.join(missing)}")

if __name__ == "__main__":
    main()
