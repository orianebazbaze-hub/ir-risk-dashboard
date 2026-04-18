

# IR Risk Dashboard

> **Interest Rate Portfolio Management | Risk Engine**  
> Real-time DV01, IRRBB stress tests, LCR/NSFR monitoring and hedge ratio calculator.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Flask](https://img.shields.io/badge/Flask-3.0-green) ![JavaScript](https://img.shields.io/badge/JavaScript-ES2022-yellow)

> **Fictitious portfolio for demonstration purposes only.** All positions (OAT, Bund, BTP, EUR IRS), notionals, rates and market parameters are simulated. Not for trading.
 <img width="715" height="566" alt="Capture d’écran 2026-04-16 à 12 35 56" src="https://github.com/user-attachments/assets/e73caefd-e56b-4867-93c8-d5eeaf3603c2" />
---

## Use Case

A **Treasury risk desk** monitors a European sovereign bond portfolio with IRS overlay, and needs to:

Track **DV01** per position and at portfolio level  
Decompose risk by **Key Rate Duration** (KRD) across tenor buckets  
Run **IRRBB regulatory stress tests** (6 EBA 2022 scenarios)  
Monitor **LCR & NSFR** liquidity ratios vs regulatory minimums  
Compute **hedge ratios** with IRS overlay  
Build **custom scenarios** with short/long end shocks  

This dashboard delivers all of that **in one interface**.

---

## Architecture

```
┌──────────────────────────────────┐
│  Flask Backend (Python 3.10+)    │
├──────────────────────────────────┤
│ • YieldCurve bootstrap           │
│ • DV01 full revaluation          │
│ • Key Rate Duration (KRD)        │
│ • IRRBB stress (EBA 2022)        │
│ • LCR / NSFR computation         │
│ • Hedge ratio calculator         │
│ • EVE / NII scenarios            │
└──────────────────────────────────┘
              ↕
         REST API (7 routes)
              ↕
┌──────────────────────────────────┐
│ JavaScript Frontend (HTML/CSS)   │
├──────────────────────────────────┤
│ • 7 interactive views            │
│ • Yield curve visualisation      │
│ • KRD bucket decomposition       │
│ • IRRBB regulatory stress        │
│ • Hedge calculator (live)        │
│ • Dark theme, responsive         │
└──────────────────────────────────┘
```

---

## Portfolio

| Instrument | Example | Notional | Type | Duration |
|---|---|---|---|---|
| **Sovereign** | OAT 3% 2034 | €100M | Asset | 8.2Y |
| **Sovereign** | Bund 2.5% 2029 | €80M | Asset | 4.5Y |
| **Sovereign** | BTP 4% 2031 | €60M | Asset | 5.8Y |
| **IRS** | EUR 5Y Receive | €150M | Hedge | −4.3Y |
| **IRS** | EUR 10Y Pay | €100M | Hedge | +7.8Y |

**Portfolio summary:** Net DV01 ≈ –€4,085K, IRRBB parallel +200bp → EVE –€763M (–31.8% CET1 BREACH)

---

## Dashboard Views

### 1. **Overview**
Real-time portfolio summary: total DV01, LCR ratio, NSFR, worst-case IRRBB EVE impact. Full position table with HQLA classification.

### 2. **Yield Curve**
EUR OIS cubic-spline bootstrapped zero curve from 3M to 30Y. Key rate points table with DV01 contribution per tenor.

### 3. **KRD Buckets**
Key Rate Duration decomposition by tenor bucket (1Y → 30Y), broken down by instrument. Shows where curve risk is concentrated.

### 4. **IRRBB Stress Tests**
All 6 EBA 2022 / BCBS 368 regulatory scenarios:

| Scenario | Short end | Long end |
|---|---|---|
| Parallel +200bp | +200bp | +200bp |
| Parallel –200bp | –200bp | –200bp |
| Steepener | –100bp | +150bp |
| Flattener | +100bp | –150bp |
| Short rate up | +250bp | +50bp |
| Short rate down | –250bp | –50bp |

EVE impact shown vs –15% CET1 limit with breach flagging. NII sensitivity (12M horizon) also displayed.

### 5. **LCR / NSFR**
- HQLA buffer composition (L1 / L2A / L2B) with donut chart
- 30-day weighted net cash outflows
- Asset detail: book value, haircuts, repoable value, HQLA tier
- LCR ratio bar with 100% minimum threshold

### 6. **Hedge Ratio Calculator**
Interactive: adjust bond notional, maturity, coupon → computes DV01, IRS hedge notional, hedge ratio. Shows hedge effectiveness curve (±200bp) and residual KRD post-hedge.

### 7. **Custom Scenario Builder**
Free-form short/long end rate shock with live EVE and CET1 impact, breach detection, and stressed curve overlay.

---

## Quickstart

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python app.py

# Open browser
# → http://localhost:5000
```

Dashboard loads with **5 demo positions** (€490M portfolio).

---

## API Reference

| Endpoint | Description |
|---|---|
| `GET /api/curve` | EUR OIS zero curve + key rate points |
| `GET /api/portfolio` | All positions with DV01, duration, convexity |
| `GET /api/krd` | KRD by instrument and tenor bucket |
| `GET /api/irrbb` | 6 IRRBB scenarios — EVE, % CET1, breach status |
| `GET /api/lcr` | LCR/NSFR, HQLA, outflows, asset detail |
| `GET /api/hedge?notional=N&maturity=M&coupon=C` | Hedge ratio computation |
| `GET /api/custom_stress?short=N&long=M` | Custom scenario EVE |

---

## Key Metrics Explained

### Risk Metrics

**DV01 (Dollar Value of 1bp)**
- P&L impact of 1bp parallel rate shift
- Formula: `DV01 = Σ (Position × Duration / 10,000)`
- Full revaluation (not just duration approximation)
- **Net portfolio DV01 ≈ –€4,085K** — 1bp shift = €4,085K loss

**Key Rate Duration (KRD)**
- Decomposes DV01 across tenor buckets (1Y, 2Y, 5Y, 10Y, 30Y)
- Shows **where** curve risk sits — not just total
- Essential for non-parallel stress (twist, butterfly)

**EVE (Economic Value of Equity)**
- Long-run sensitivity of bank equity to rate changes
- IRRBB metric: must not exceed –15% of Tier 1 capital
- **Current portfolio:** parallel +200bp → EVE –€763M (–31.8% CET1 BREACH)

**NII (Net Interest Income)**
- 12-month forward earnings sensitivity
- Stickier measure (floating vs fixed assets)
- Regulatory: no specific limit but monitored

### Liquidity Metrics

**LCR (Liquidity Coverage Ratio)**
- `LCR = HQLA / Net Cash Outflows (30d)`
- Regulatory minimum: **100%**
- HQLA tiers: L1 (sovereigns), L2A (agencies, 15% haircut), L2B (corporates, 50% haircut)

**NSFR (Net Stable Funding Ratio)**
- `NSFR = Available Stable Funding / Required Stable Funding`
- 1-year horizon, regulatory minimum: **100%**
- Captures structural funding mismatches

---

## Technical Stack

**Backend:** Python 3.10+ + Flask + NumPy + SciPy (cubic spline bootstrap)  
**Frontend:** Vanilla JavaScript + Chart.js (curves, donuts, bars)  
**Pricing:** Full revaluation for DV01, not duration approximation  
**Performance:** All calculations < 150ms  

---

## Files

```
ir_risk_dashboard/
├── app.py                  # Flask backend — risk engine + REST API
├── templates/
│   └── index.html          # Frontend (dark theme)
├── requirements.txt        # Dependencies
└── README.md              # This file
```

---

## Regulatory References

- **BCBS 368** — Interest Rate Risk in the Banking Book (IRRBB), April 2016
- **EBA/GL/2022/14** — Guidelines on IRRBB and CSRBB, October 2022
- **Basel III LCR** — CRR2 Article 412 / Delegated Regulation (EU) 2015/61
- **NSFR** — CRR2 Article 428a–428ao

---

## Limitations & Notes

**Portfolio is fictitious** — positions, rates, curves are simulated  
**Simplified IRRBB** — 6 standard scenarios only, no bank-specific shocks  
**LCR/NSFR** — 30d/1Y static analysis, no behavioural assumptions  
**No real-time market data feeds** — all rates hard-coded (for demo)  

---

## Next Steps

- **Connect to live market data** (Bloomberg, Reuters, ECB APIs)
- **Bank-specific IRRBB shocks** (historical, Monte Carlo VaR)
- **Behavioural models** for non-maturity deposits (NMD runoff)
- **Convexity adjustment** for options / callable structures

## Author
ob
