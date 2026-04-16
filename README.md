# IR Risk Dashboard <img width="715" height="566" alt="Capture d’écran 2026-04-16 à 12 35 56" src="https://github.com/user-attachments/assets/e73caefd-e56b-4867-93c8-d5eeaf3603c2" />


> **Interest Rate Portfolio Management | 
> Full-stack risk dashboard: Python risk engine (Flask REST API) + JavaScript frontend.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Flask](https://img.shields.io/badge/Flask-3.0-green) ![JavaScript](https://img.shields.io/badge/JavaScript-ES2022-yellow) ![Basel III](https://img.shields.io/badge/IRRBB-Basel%20III%20%2F%20EBA%202022-red)

---

## Disclaimer

The instruments used in this dashboard (OAT, Bund, BTP, EUR IRS) were selected solely to build an illustrative portfolio representative of a Corporate Treasury book. Notionals, rates and market parameters are simulated and do not reflect any real position. The purpose is to demonstrate the capabilities of the risk engine: curve bootstrapping, full-revaluation DV01, KRD, IRRBB stress tests and LCR/NSFR computation.

---

## Overview

A production-style interest rate risk dashboard that combines:

- **Python backend** — full-revaluation DV01 engine, yield curve bootstrapping, IRRBB regulatory stress tests, LCR/NSFR computation
- **JavaScript frontend** — real-time interactive charts, scenario builders, hedge ratio calculator

```
┌─────────────────────────────┐       REST API        ┌──────────────────────────────────┐
│   Python Risk Engine        │ ◄──────────────────── │   JavaScript Dashboard           │
│                             │                        │                                  │
│  • YieldCurve bootstrap     │  /api/portfolio        │  • Overview (DV01, LCR, IRRBB)  │
│  • DV01 full revaluation    │  /api/krd              │  • Yield curve visualisation     │
│  • Key Rate Duration        │  /api/irrbb            │  • KRD bucket decomposition      │
│  • IRRBB stress (EBA 2022)  │  /api/lcr              │  • IRRBB regulatory stress       │
│  • LCR / NSFR computation   │  /api/hedge            │  • LCR / HQLA buffer             │
│  • Hedge ratio calculator   │  /api/custom_stress    │  • Interactive hedge calculator  │
│  • EVE / NII scenarios      │                        │  • Custom scenario builder       │
└─────────────────────────────┘                        └──────────────────────────────────┘
```

---



## Dashboard Sections

### Overview
Real-time portfolio summary: total DV01, LCR ratio, NSFR, worst-case IRRBB EVE impact. Full position table with HQLA classification.

### Yield Curve
EUR OIS cubic-spline bootstrapped zero curve from 3M to 30Y. Key rate points table.

### KRD Buckets
Key Rate Duration decomposition by tenor bucket (1Y → 30Y), broken down by instrument. Shows where curve risk is concentrated.

### IRRBB Stress Tests
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

### LCR / NSFR
- HQLA buffer composition (L1 / L2A / L2B) with donut chart
- 30-day weighted net cash outflows
- Asset detail: book value, haircuts, repoable value, HQLA tier, illiquid net flag
- LCR ratio bar with 100% minimum threshold

### Hedge Ratio Calculator
Interactive: adjust bond notional, maturity, coupon → computes DV01, IRS hedge notional, hedge ratio. Shows hedge effectiveness curve (±200bp) and residual KRD post-hedge.

### Custom Scenario Builder
Free-form short/long end rate shock with live EVE and CET1 impact, breach detection, and stressed curve overlay.

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/curve` | GET | EUR OIS zero curve + key rate points |
| `/api/portfolio` | GET | All positions with DV01, duration, convexity |
| `/api/krd` | GET | KRD by instrument and tenor bucket |
| `/api/irrbb` | GET | 6 IRRBB scenarios — EVE, % CET1, breach status |
| `/api/lcr` | GET | LCR/NSFR, HQLA, outflows, asset detail |
| `/api/hedge` | GET | Hedge ratio; params: `notional`, `maturity`, `coupon` |
| `/api/custom_stress` | GET | Custom scenario EVE; params: `short`, `long` (bp) |

---

## Repository Structure

```
ir_risk_dashboard/
│
├── app.py               # Flask backend — risk engine + REST API
├── requirements.txt     # Python dependencies
├── templates/
│   └── index.html       # Single-page JS dashboard
└── README.md
```

Related modules in this repository:
- `../dv01_hedge_ratio/` — standalone DV01 / KRD / hedge ratio engine
- `../swaptions/` — swaption pricing, vol surface calibration *(coming)*
- `../collateral_management/` — haircut engine, HQLA optimiser *(coming)*

---

## Regulatory References

- **BCBS 368** — Interest Rate Risk in the Banking Book (IRRBB), April 2016
- **EBA/GL/2022/14** — Guidelines on IRRBB and CSRBB, October 2022
- **Basel III LCR** — CRR2 Article 412 / Delegated Regulation (EU) 2015/61
- **NSFR** — CRR2 Article 428a–428ao

---

## Author
ob
