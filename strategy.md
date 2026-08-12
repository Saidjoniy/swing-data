# Saidjon's Swing Strategy — v1

## Account
- Deposit: $25,000
- Position size: $1,500–2,000 per stock (~12–16 max concurrent positions)
- Instruments: US-listed stocks only
- Hold time: 1–2 weeks (swing)
- Decision timeframe: Daily chart (weekly for trend context)

## Setup A — Reversal (primary)
Trigger conditions (all should align):
1. Price at/near a key support level, demand zone, or major MA (20/50/200) — within ~3%
2. Reversal candlestick confirmed: hammer, bullish engulfing, pin bar
3. Volume on the reversal candle above average (confirmation required)
Supporting evidence (raises conviction, not mandatory):
- RSI oversold (<35–40) or bullish RSI/MACD divergence
- MACD histogram turning up / bullish cross forming
- Weekly trend not in freefall (avoid falling knives without a base)

## Setup B — Strong breakout
Trigger conditions:
1. Clean break of resistance, prior high, or trendline
2. High volume on the breakout (>1.5x average)
3. Big-bodied momentum candle closing near its high (no long upper wick)
4. Retest entries are valid: breakout within last ~10 sessions, price pulled back to
   the broken level (now support) and holding — often the better R:R entry

## Setup C — Daily pullback (buy the dip in an uptrend)
Trigger conditions:
1. Established uptrend: price > 50SMA, 50SMA > 200SMA
2. Orderly pullback of ~3–15% from the recent high (not a crash), ideally on
   shrinking volume
3. Price at a logical dip-buy level: 20EMA, 50SMA, or a prior breakout level
4. Reversal cue at the level: hammer/engulfing, or a green candle reclaiming the
   prior day's high; RSI reset toward 35–55 is supportive
Stop below the pullback low; target = prior high first, then trend continuation.

## Universe volatility rule
Only trade stocks with true-range ATR(14) >= 3% of price. The screener enforces
this dynamically every run; quieter names are ignored even if they are in the
watchlist file.

## Risk & exits
- Stop: below structure (reversal low / broken level / support), NOT a fixed %
- Minimum reward:risk = 2:1 or the pick is rejected
- Targets: next resistance / prior high, or fixed R:R target
- Earnings: no filter — trading through earnings is allowed (mention date if within 7 days)

## Fundamentals — veto only
Technicals select; fundamentals only reject:
- Fraud/accounting scandal, going-concern risk
- Guidance collapse or business model broken by recent news
- Sector in acute crisis
A boring/neutral fundamental picture is fine.

## Report format (every 2 days)
- Top 5–10 picks, medium-depth write-up each:
  setup type (Reversal/Breakout/Retest), entry zone, stop, target, R:R,
  position size in shares for a $1,500–2,000 allocation, one-line fundamental check
- Scan universe: the ~490-ticker watchlist first, plus flag exceptional setups outside it
- Not financial advice; decision support only — final call is Saidjon's
