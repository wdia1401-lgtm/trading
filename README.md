# YM Initial Balance Playbook — Pine Script Strategy

A TradingView **Pine Script v6 strategy** that implements the edgeful
*"full IB playbook on YM"* (5 rules, 128 NY sessions, 12/08/25 – 06/08/26).

> Educational / research use only. The playbook's own caveats apply: 128
> sessions is 6 months, several condition stacks fire fewer than 20 times, and
> historical hit rates are context, **not** a forecast. Nothing here is
> financial advice.

File: [`ym_ib_playbook_strategy.pine`](./ym_ib_playbook_strategy.pine)

## Quick start

1. Open TradingView → **Pine Editor**.
2. Paste the contents of `ym_ib_playbook_strategy.pine` → **Add to chart**.
3. Use it on **YM** (`YM1!` / `CBOT_MINI:YM1!`) on a **5-minute** chart — the
   playbook's stats were measured on 5-minute candles with a 09:30–10:30 ET IB.
4. Tune inputs in the strategy settings; check **Strategy Tester** for results.

## The core idea

The Initial Balance is the high/low of the first hour (09:30–10:30 ET). The
playbook's edge is that **by 10:30 you can usually tell which side will break**,
then the **clock** tells you whether to trust the break and **extension levels**
tell you whether to hold to the bell or scalp.

## How the 5 rules map to the code

| Rule | Playbook finding | In the strategy |
|------|------------------|-----------------|
| **R1 – 10:30 direction trigger** | *1A:* IB low forms first **and** the first hour closes in the **top 25%** → IB high breaks first (**97.4%**). *1B:* high forms first **and** close in **bottom 25%** → IB low breaks first (**97.2%**). | The primary entry signal. `longTrig` / `shortTrig`. In *Anticipation* mode it enters **inside the range at 10:30**; in *Breakout* mode it places a stop order at the favored level. |
| **R2 – day color** | *2A:* green IB + large (>0.7%) → green day (**89.7%**). *2B:* high breaks first, before 12:00, green IB → green day (**97.4%**, 100% if also large). *2C:* low breaks first, before 12:00, red IB → red day (**86.1%**). | `runnerActive`. On runner days, `holdRunners` drops the profit target and **rides to the bell** (target day color, not extension). |
| **R3 – the clock** | Early break (before 12:00) holds, opposite side survives (**94.6%**). After 12:00 → elevated double-break / fade risk (~43%, a *filter*, not a setup). | `noonHour`. In Breakout mode, an unfilled order is **cancelled after noon**. The stop sits on the **opposite IB side** (R3A "statistically safe stop"). |
| **R4 – extension targets** | Small IB (<0.47%) breaking down reaches the **−0.5x** extension (**84.6%**). Upside extensions are weaker. Huge IB (>0.9%) → rotation, closes back inside (**76.2%**). | `adaptiveTargets`: small IB → **0.5x** target, otherwise **1.0x**. `skipRotation` skips huge-IB days. Extension levels are plotted (±0.5x, ±1.0x). |
| **R5 – close location / hold-vs-scalp** | Once **±0.5x** prints, hold for a close beyond the IB (84% long / 82% short; 89% once ±1.0x prints). If extension never prints by the afternoon → **scalp**, closes back inside ~59%. | `ext05Hit` tracks the first extension. `scalpNoExt`: if the afternoon (`pmHour`) arrives with **no extension printed**, flatten ("PM scalp"). If it printed, the trade is held to target or the bell. |

## The 10:30 checklist (the table on the chart)

The on-chart table reproduces the playbook's morning checklist as live state:

- **IB range %** and **size** (small / mid / large / huge-rotation)
- **which formed first** (high vs low)
- **where the first hour closed** (top 25% / middle / bottom 25%)
- **IB candle color**
- **clock** (before/after 12:00)
- **bias** (LONG 1A / SHORT 1B / none) and current **position**

## Key inputs

- **Entry mode** — *Anticipation (Rule 1)*: enter inside the IB at 10:30 on the
  trigger (the playbook's headline edge). *Breakout (Rule 2/3)*: wait for the
  actual break of the favored level, valid only before noon.
- **Close-in-range quartile** — the 25% top/bottom band for R1 (default 0.25).
- **IB size thresholds** — small `0.47%`, large `0.70%`, huge `0.90%` of price.
- **Clock filter hour** / **Afternoon scalp hour** — R3 noon cutoff (12:00) and
  R5 scalp time (14:00).
- **Hold runners to the bell**, **Skip rotation days**, **Adaptive targets**,
  **Scalp if no extension** — toggles for R2/R4C/R4/R5 behavior.

## Notes & honest caveats (from the playbook)

- Everything is specific to the measured settings: **NY session, 09:30–10:30 IB,
  wick-touch breakouts, 5-minute candles**. Change any of these and the numbers
  change — re-validate before trading.
- Several edges rest on **small samples** (some <20 trades). Treat those as
  confluence, not conviction, and don't size up on them.
- A strategy backtest is **not** the playbook's per-condition study. The .pine
  file encodes the *rules* into one tradeable system; it does not reproduce the
  edgeful API condition-by-condition hit rates. Use the Strategy Tester to see
  how the combined ruleset performs on your data/contract, and adjust.
- Want this analysis on ES/NQ? The playbook was generated from the edgeful API
  (`edgeful.com/api`); the IB behaves differently per instrument, so re-run it
  rather than assuming the YM numbers transfer.
