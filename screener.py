#!/usr/bin/env python3
"""Stage-1 mechanical screener for Saidjon's swing strategy.

Input:  data/prices.parquet (long format: ticker,date,open,high,low,close,volume)
Output: out/shortlist.json  — top candidates with full metric evidence
        out/screen_summary.txt

Scores two setup families on daily data:
  A) Reversal: price near support (swing lows / 50 or 200 SMA), reversal candle
     (hammer / bullish engulfing / pin bar) on above-average volume, RSI low or
     bullish divergence, MACD histogram turning up.
  B) Breakout: break of N-day high / resistance on >=1.5x volume with a strong
     body closing near high; or a retest of a breakout from the last 10 sessions.

Liquidity filter: price >= $5, avg dollar volume >= $5M.
No pick is made here — this only nominates candidates for AI review.
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

TOP_N = 30


def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def analyze_ticker(g: pd.DataFrame):
    # drop corrupt rows (partial fetches can leave volume with NaN prices)
    g = g.dropna(subset=["open", "high", "low", "close"])
    g = g.sort_values("date").reset_index(drop=True)
    if len(g) < 120:
        return None
    c, h, l, o, v = g.close, g.high, g.low, g.open, g.volume
    last = g.iloc[-1]
    price = float(last.close)

    # liquidity
    adv = float((c * v).tail(50).mean())
    if price < 5 or adv < 5e6:
        return None

    # volatility floor: true-range ATR(14) must be >= 3% of price
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()
    atr_pct = float(atr14.iloc[-1] / price * 100)
    if not np.isfinite(atr_pct) or atr_pct < 3.0:
        return None

    sma20 = c.rolling(20).mean()
    sma50 = c.rolling(50).mean()
    sma200 = c.rolling(200).mean() if len(g) >= 200 else pd.Series(np.nan, index=c.index)
    vol50 = v.rolling(50).mean()
    r = rsi(c)
    ema12, ema26 = c.ewm(span=12).mean(), c.ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    hist = macd - signal
    atr = (h - l).rolling(14).mean()

    vol_ratio = float(v.iloc[-1] / vol50.iloc[-1]) if vol50.iloc[-1] else 0.0

    # ---------- candle anatomy (last bar + prev) ----------
    def candle(i):
        cd = g.iloc[i]
        rng = cd.high - cd.low
        body = abs(cd.close - cd.open)
        if rng <= 0:
            return {}
        return dict(
            body_pct=body / rng,
            close_pos=(cd.close - cd.low) / rng,     # 1.0 = closed at high
            lower_wick=(min(cd.close, cd.open) - cd.low) / rng,
            upper_wick=(cd.high - max(cd.close, cd.open)) / rng,
            green=cd.close > cd.open,
        )

    c0, c1 = candle(-1), candle(-2)
    hammer = bool(c0 and c0["lower_wick"] >= 0.5 and c0["close_pos"] >= 0.6)
    engulf = bool(
        c0 and c0["green"] and not g.iloc[-2].close > g.iloc[-2].open
        and last.close > g.iloc[-2].open and last.open < g.iloc[-2].close
    )
    momentum_candle = bool(c0 and c0["green"] and c0["body_pct"] >= 0.6 and c0["close_pos"] >= 0.75)

    # ---------- support / resistance from swing points ----------
    win = g.tail(120).reset_index(drop=True)
    lows, highs = [], []
    for i in range(2, len(win) - 2):
        if win.low[i] == win.low[i - 2:i + 3].min():
            lows.append(float(win.low[i]))
        if win.high[i] == win.high[i - 2:i + 3].max():
            highs.append(float(win.high[i]))

    def nearest_below(levels, x):
        cand = [lv for lv in levels if lv <= x * 1.01]
        return max(cand) if cand else None

    def nearest_above(levels, x):
        cand = [lv for lv in levels if lv >= x * 0.99]
        return min(cand) if cand else None

    support = nearest_below(lows, price)
    resistance = nearest_above(highs, price)
    hi60 = float(h.tail(60).max())
    hi120 = float(h.tail(120).max())

    near = lambda level, tol: level is not None and abs(price - level) / price <= tol

    # ---------- REVERSAL score ----------
    rev = 0.0
    rev_notes = []
    at_support = near(support, 0.03)
    at_sma50 = not np.isnan(sma50.iloc[-1]) and abs(price - sma50.iloc[-1]) / price <= 0.03
    at_sma200 = not np.isnan(sma200.iloc[-1]) and abs(price - sma200.iloc[-1]) / price <= 0.03
    if at_support: rev += 2; rev_notes.append(f"at swing support {support:.2f}")
    if at_sma50: rev += 1.5; rev_notes.append("at 50SMA")
    if at_sma200: rev += 1.5; rev_notes.append("at 200SMA")
    if hammer: rev += 2; rev_notes.append("hammer/pin bar")
    if engulf: rev += 2; rev_notes.append("bullish engulfing")
    if (hammer or engulf) and vol_ratio >= 1.2:
        rev += 1.5; rev_notes.append(f"volume {vol_ratio:.1f}x on reversal candle")
    if r.iloc[-1] < 38: rev += 1; rev_notes.append(f"RSI {r.iloc[-1]:.0f}")
    # bullish divergence: price lower low vs 20 bars ago, RSI higher low
    lb = min(25, len(g) - 1)
    if l.iloc[-1] <= l.tail(lb).min() * 1.01 and r.iloc[-1] > r.tail(lb).min() + 3:
        rev += 1.5; rev_notes.append("bullish RSI divergence")
    if hist.iloc[-1] > hist.iloc[-2] > hist.iloc[-3]:
        rev += 0.5; rev_notes.append("MACD hist rising")
    # need a base: don't catch knives — price shouldn't be >12% under 20SMA
    if not np.isnan(sma20.iloc[-1]) and price < sma20.iloc[-1] * 0.88:
        rev *= 0.5; rev_notes.append("WARN: extended below 20SMA (knife risk)")
    if not (at_support or at_sma50 or at_sma200):
        rev *= 0.4  # no level = no reversal setup

    # ---------- BREAKOUT score ----------
    brk = 0.0
    brk_notes = []
    # fresh break: made new 60d high within last 3 bars
    recent3_hi = float(h.tail(3).max())
    prior_hi60 = float(h.iloc[-63:-3].max()) if len(g) >= 63 else hi60
    broke = recent3_hi >= prior_hi60 * 0.999 and price >= prior_hi60 * 0.98
    if broke:
        brk += 2.5; brk_notes.append(f"broke 60d high {prior_hi60:.2f}")
        if vol_ratio >= 1.5: brk += 2; brk_notes.append(f"volume {vol_ratio:.1f}x")
        elif vol_ratio >= 1.2: brk += 1; brk_notes.append(f"volume {vol_ratio:.1f}x (ok)")
        if momentum_candle: brk += 1.5; brk_notes.append("momentum candle, closed near high")
    # retest: broke prior_hi within last 10 bars, now pulled back to within 2.5% of level
    if len(g) >= 73:
        lvl = float(h.iloc[-73:-10].max())
        broke_ago = bool((h.tail(10) >= lvl * 0.999).any())
        if broke_ago and abs(price - lvl) / price <= 0.025 and price >= lvl * 0.97:
            brk += 3; brk_notes.append(f"retesting broken level {lvl:.2f}")
            if c0 and c0.get("green"): brk += 0.5; brk_notes.append("holding green on retest")
    # pre-breakout coil: tight range near resistance
    rng20 = (h.tail(20).max() - l.tail(20).min()) / price
    if resistance and near(resistance, 0.02) and rng20 < 0.10:
        brk += 1.5; brk_notes.append(f"coiling under resistance {resistance:.2f} (20d range {rng20*100:.0f}%)")

    # trend context
    uptrend = not np.isnan(sma50.iloc[-1]) and price > sma50.iloc[-1] and \
        (np.isnan(sma200.iloc[-1]) or sma50.iloc[-1] > sma200.iloc[-1])
    if brk > 0 and uptrend: brk += 0.5

    # ---------- PULLBACK score (Setup C: buy the dip in an uptrend) ----------
    pb = 0.0
    pb_notes = []
    hi20 = float(h.tail(20).max())
    off_high = (hi20 - price) / hi20 * 100  # % below 20d high
    ema20 = c.ewm(span=20).mean()
    at_ema20 = abs(price - ema20.iloc[-1]) / price <= 0.025
    at_50 = not np.isnan(sma50.iloc[-1]) and abs(price - sma50.iloc[-1]) / price <= 0.025
    if uptrend and 3 <= off_high <= 15:
        pb += 1.5; pb_notes.append(f"uptrend, {off_high:.0f}% off 20d high")
        if at_ema20: pb += 1.5; pb_notes.append("at 20EMA")
        if at_50: pb += 1.5; pb_notes.append("at 50SMA")
        # pullback on quiet volume (last 3 bars below average)
        if float(v.tail(3).mean()) < float(vol50.iloc[-1]) * 0.9:
            pb += 0.5; pb_notes.append("volume dried up on pullback")
        # reversal cue off the dip
        if hammer or engulf: pb += 1.5; pb_notes.append("reversal candle at the dip")
        elif c0 and c0.get("green") and last.close > g.iloc[-2].high:
            pb += 1; pb_notes.append("green candle reclaiming prior high")
        if 35 <= r.iloc[-1] <= 55: pb += 0.5; pb_notes.append(f"RSI reset to {r.iloc[-1]:.0f}")
    if not (at_ema20 or at_50):
        pb *= 0.5  # dip without a level to lean on

    score = max(rev, brk, pb)
    if score < 3.5:
        return None

    setup = {rev: "reversal", brk: "breakout", pb: "pullback"}[score]
    notes_by = {"reversal": rev_notes, "breakout": brk_notes, "pullback": pb_notes}
    return dict(
        ticker=str(last.ticker), setup=setup, score=round(score, 2),
        rev_score=round(rev, 2), brk_score=round(brk, 2), pb_score=round(pb, 2),
        price=round(price, 2),
        notes=notes_by[setup],
        atr_pct=round(atr_pct, 2),
        rsi=round(float(r.iloc[-1]), 1), vol_ratio=round(vol_ratio, 2),
        sma20=round(float(sma20.iloc[-1]), 2),
        sma50=round(float(sma50.iloc[-1]), 2) if not np.isnan(sma50.iloc[-1]) else None,
        sma200=round(float(sma200.iloc[-1]), 2) if not np.isnan(sma200.iloc[-1]) else None,
        support=round(support, 2) if support else None,
        resistance=round(resistance, 2) if resistance else None,
        hi60=round(hi60, 2), atr=round(float(atr.iloc[-1]), 2),
        adv_musd=round(adv / 1e6, 1),
        last_date=str(last.date)[:10],
    )


def main():
    df = pd.read_parquet(ROOT / "data" / "prices.parquet")
    results = []
    for t, g in df.groupby("ticker"):
        try:
            row = analyze_ticker(g)
            if row:
                results.append(row)
        except Exception as e:
            print(f"{t}: ERROR {e}")
    results.sort(key=lambda x: -x["score"])
    short = results[:TOP_N]
    (OUT / "shortlist.json").write_text(json.dumps(short, indent=1))
    lines = [f"Screened {df.ticker.nunique()} tickers -> {len(results)} candidates, kept top {len(short)}", ""]
    for x in short:
        lines.append(f"{x['ticker']:>6} {x['setup']:<9} score {x['score']:>4} @ {x['price']:>8} | {'; '.join(x['notes'])}")
    (OUT / "screen_summary.txt").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
