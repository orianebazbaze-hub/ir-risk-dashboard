"""
IR Risk Dashboard — Flask Backend
==================================
Corporate Treasury | Interest Rate Portfolio Management

Exposes a REST API that runs the full DV01 / KRD / IRRBB risk engine
and serves the results to the JavaScript frontend.

Run
---
    pip install flask flask-cors numpy scipy pandas
    python app.py
    open http://localhost:5000
"""

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq
import json

app = Flask(__name__)
CORS(app)

BP = 1e-4

# ---------------------------------------------------------------------------
# Yield Curve
# ---------------------------------------------------------------------------

class YieldCurve:
    def __init__(self, tenors, rates, label="EUR OIS"):
        self.tenors = np.asarray(tenors, dtype=float)
        self.rates  = np.asarray(rates,  dtype=float)
        self.label  = label
        self._spline = CubicSpline(self.tenors, self.rates, bc_type="natural")

    def zero_rate(self, t):
        return float(self._spline(np.asarray(t, dtype=float)))

    def discount(self, t):
        t = np.asarray(t, dtype=float)
        return np.exp(-self._spline(t) * t)

    def par_swap_rate(self, maturity, freq=2):
        dt = 1 / freq
        times = np.arange(dt, maturity + dt / 2, dt)
        annuity = float(np.sum(self.discount(times))) * dt
        return (1 - float(self.discount(maturity))) / annuity

    def shifted(self, shift_bp, tenor_y=None):
        new_rates = self.rates.copy()
        if tenor_y is None:
            new_rates += shift_bp * BP
        else:
            idx = int(np.argmin(np.abs(self.tenors - tenor_y)))
            new_rates[idx] += shift_bp * BP
        return YieldCurve(self.tenors.copy(), new_rates, self.label)

    def full_curve(self):
        ts = np.linspace(0.25, 30, 200)
        return ts.tolist(), self._spline(ts).tolist()


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------

class Bond:
    def __init__(self, face, coupon, maturity, freq=2, label="Bond"):
        self.face = face; self.coupon = coupon
        self.maturity = maturity; self.freq = freq; self.label = label

    def cash_flows(self):
        dt = 1 / self.freq
        times = np.arange(dt, self.maturity + dt / 2, dt)
        flows = np.full(len(times), self.face * self.coupon / self.freq)
        flows[-1] += self.face
        return times, flows

    def price(self, curve):
        t, f = self.cash_flows()
        return float(np.sum(f * curve.discount(t)))

    def ytm(self, curve):
        px = self.price(curve)
        t, f = self.cash_flows()
        return float(brentq(lambda y: np.sum(f * np.exp(-y * t)) - px, -0.10, 0.50))

    def mod_duration(self, curve):
        t, f = self.cash_flows()
        dfs = curve.discount(t)
        px  = float(np.sum(f * dfs))
        mac = float(np.sum(t * f * dfs)) / px
        return mac / (1 + self.ytm(curve) / self.freq)

    def convexity(self, curve):
        t, f = self.cash_flows()
        dfs = curve.discount(t)
        px  = float(np.sum(f * dfs))
        y   = self.ytm(curve)
        return float(np.sum(t * (t + 1/self.freq) * f * dfs)) / (px * (1 + y/self.freq)**2)


class IRS:
    def __init__(self, notional, fixed_rate, maturity, freq=2, is_payer=True, label="IRS"):
        self.notional = notional; self.fixed_rate = fixed_rate
        self.maturity = maturity; self.freq = freq
        self.is_payer = is_payer; self.label = label

    def npv(self, curve):
        dt = 1 / self.freq
        times = np.arange(dt, self.maturity + dt / 2, dt)
        fixed_pv = float(np.sum(self.notional * self.fixed_rate * dt * curve.discount(times)))
        float_pv = float(self.notional * (1 - curve.discount(self.maturity)))
        sign = 1 if self.is_payer else -1
        return sign * (float_pv - fixed_pv)

    def par_rate(self, curve):
        return curve.par_swap_rate(self.maturity, self.freq)


# ---------------------------------------------------------------------------
# Risk Engine
# ---------------------------------------------------------------------------

def dv01(instrument, curve, shift_bp=1.0):
    up = curve.shifted(+shift_bp)
    dn = curve.shifted(-shift_bp)
    if isinstance(instrument, Bond):
        return (instrument.price(up) - instrument.price(dn)) / 2
    return (instrument.npv(up) - instrument.npv(dn)) / 2


def key_rate_duration(instrument, curve, key_tenors, shift_bp=1.0):
    result = {}
    for name, ty in key_tenors.items():
        up = curve.shifted(+shift_bp, tenor_y=ty)
        dn = curve.shifted(-shift_bp, tenor_y=ty)
        if isinstance(instrument, Bond):
            result[name] = (instrument.price(up) - instrument.price(dn)) / 2
        else:
            result[name] = (instrument.npv(up) - instrument.npv(dn)) / 2
    return result


def eve_impact(instruments, notionals, curve, short_shift_bp, long_shift_bp):
    """EVE = sum of PV changes under a rate scenario (short <3Y, long >3Y)."""
    total = 0.0
    for inst, n in zip(instruments, notionals):
        stressed = YieldCurve(curve.tenors.copy(), curve.rates.copy())
        for i, t in enumerate(stressed.tenors):
            shift = short_shift_bp if t <= 3 else long_shift_bp
            stressed.rates[i] += shift * BP
        stressed._spline = CubicSpline(stressed.tenors, stressed.rates, bc_type="natural")
        if isinstance(inst, Bond):
            base = inst.price(curve) * n
            stress = inst.price(stressed) * n
        else:
            base = inst.npv(curve) * n
            stress = inst.npv(stressed) * n
        total += (stress - base)
    return total


# ---------------------------------------------------------------------------
# Build the default portfolio
# ---------------------------------------------------------------------------

def build_portfolio():
    tenors = np.array([0.25, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30])
    rates  = np.array([0.0390, 0.0385, 0.0360, 0.0320, 0.0300, 0.0280, 0.0270,
                       0.0265, 0.0262, 0.0258, 0.0250])
    curve = YieldCurve(tenors, rates)

    oat   = Bond(face=100, coupon=0.030, maturity=10, label="OAT 3% 10Y")
    bund  = Bond(face=100, coupon=0.025, maturity=5,  label="Bund 2.5% 5Y")
    btp   = Bond(face=100, coupon=0.040, maturity=7,  label="BTP 4% 7Y")
    irs10 = IRS(notional=100, fixed_rate=curve.par_swap_rate(10),
                maturity=10, is_payer=True, label="IRS Pay 10Y")
    irs5  = IRS(notional=100, fixed_rate=curve.par_swap_rate(5),
                maturity=5,  is_payer=True, label="IRS Pay 5Y")

    notionals = {
        "OAT 3% 10Y":   1e8,
        "Bund 2.5% 5Y": 8e7,
        "BTP 4% 7Y":    5e7,
        "IRS Pay 10Y":  9.56e7,
        "IRS Pay 5Y":   7.5e7,
    }

    instruments = {
        "OAT 3% 10Y":   oat,
        "Bund 2.5% 5Y": bund,
        "BTP 4% 7Y":    btp,
        "IRS Pay 10Y":  irs10,
        "IRS Pay 5Y":   irs5,
    }

    return curve, instruments, notionals


KEY_TENORS = {"1Y":1,"2Y":2,"3Y":3,"5Y":5,"7Y":7,"10Y":10,"15Y":15,"20Y":20,"30Y":30}

IRRBB_SCENARIOS = [
    {"name": "Parallel +200bp", "short": +200, "long": +200},
    {"name": "Parallel -200bp", "short": -200, "long": -200},
    {"name": "Steepener",       "short": -100, "long": +150},
    {"name": "Flattener",       "short": +100, "long": -150},
    {"name": "Short rate +250", "short": +250, "long":  +50},
    {"name": "Short rate -250", "short": -250, "long":  -50},
]

# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/curve")
def api_curve():
    curve, _, _ = build_portfolio()
    ts, rs = curve.full_curve()
    key_points = {k: round(curve.zero_rate(v) * 100, 4) for k, v in KEY_TENORS.items()}
    return jsonify({"tenors": ts, "rates": rs, "key_points": key_points})


@app.route("/api/portfolio")
def api_portfolio():
    curve, instruments, notionals = build_portfolio()
    rows = []
    total_dv01 = 0.0
    for name, inst in instruments.items():
        n = notionals[name]
        d = dv01(inst, curve) * n
        total_dv01 += d
        row = {
            "label":    name,
            "notional": n,
            "dv01":     round(d, 2),
        }
        if isinstance(inst, Bond):
            row["ytm"]         = round(inst.ytm(curve) * 100, 3)
            row["mod_dur"]     = round(inst.mod_duration(curve), 3)
            row["convexity"]   = round(inst.convexity(curve), 3)
            row["price"]       = round(inst.price(curve), 4)
            row["type"]        = "bond"
        else:
            row["par_rate"]    = round(inst.par_rate(curve) * 100, 3)
            row["type"]        = "irs"
        rows.append(row)

    return jsonify({"positions": rows, "total_dv01": round(total_dv01, 2)})


@app.route("/api/krd")
def api_krd():
    curve, instruments, notionals = build_portfolio()
    result = {name: {} for name in instruments}
    net = {k: 0.0 for k in KEY_TENORS}

    for name, inst in instruments.items():
        n = notionals[name]
        krd = key_rate_duration(inst, curve, KEY_TENORS)
        for k, v in krd.items():
            scaled = round(v * n, 2)
            result[name][k] = scaled
            net[k] = round(net.get(k, 0) + scaled, 2)

    return jsonify({"by_instrument": result, "net": net, "tenors": list(KEY_TENORS.keys())})


@app.route("/api/irrbb")
def api_irrbb():
    curve, instruments, notionals = build_portfolio()
    insts = list(instruments.values())
    nots  = [notionals[n] for n in instruments]
    cet1  = 2.4e9

    results = []
    for sc in IRRBB_SCENARIOS:
        eve = eve_impact(insts, nots, curve, sc["short"], sc["long"])
        pct_cet1 = (eve / cet1) * 100
        results.append({
            "name":     sc["name"],
            "short_bp": sc["short"],
            "long_bp":  sc["long"],
            "eve_eur":  round(eve / 1e6, 1),
            "pct_cet1": round(pct_cet1, 2),
            "breach":   abs(pct_cet1) > 15,
            "near":     abs(pct_cet1) > 10,
        })

    return jsonify({"scenarios": results, "cet1_eur_bn": cet1 / 1e9, "limit_pct": -15})


@app.route("/api/custom_stress")
def api_custom_stress():
    short_bp = float(request.args.get("short", 0))
    long_bp  = float(request.args.get("long",  0))
    curve, instruments, notionals = build_portfolio()
    insts = list(instruments.values())
    nots  = [notionals[n] for n in instruments]
    cet1  = 2.4e9
    eve   = eve_impact(insts, nots, curve, short_bp, long_bp)
    pct   = (eve / cet1) * 100
    return jsonify({
        "eve_eur":  round(eve / 1e6, 1),
        "pct_cet1": round(pct, 2),
        "breach":   abs(pct) > 15,
    })


@app.route("/api/hedge")
def api_hedge():
    notional  = float(request.args.get("notional", 1e8))
    maturity  = float(request.args.get("maturity", 10))
    coupon    = float(request.args.get("coupon", 0.03))

    tenors = np.array([0.25,0.5,1,2,3,5,7,10,15,20,30])
    rates  = np.array([0.039,0.0385,0.036,0.032,0.030,0.028,0.027,0.0265,0.0262,0.0258,0.025])
    curve  = YieldCurve(tenors, rates)

    bond = Bond(face=100, coupon=coupon, maturity=maturity, label="Target Bond")
    d_bond = dv01(bond, curve) * notional

    par  = curve.par_swap_rate(maturity)
    irs  = IRS(notional=1.0, fixed_rate=par, maturity=maturity, is_payer=True, label="Hedge IRS")
    d_irs_unit = dv01(irs, curve)

    hedge_notional = -d_bond / d_irs_unit if abs(d_irs_unit) > 1e-15 else 0
    hedge_ratio    = hedge_notional / notional if notional else 0

    # Effectiveness curve
    shifts = list(range(-200, 210, 25))
    unhedged, hedged_vals = [], []
    for s in shifts:
        up = curve.shifted(s)
        b_pnl = (bond.price(up) - bond.price(curve)) / 100 * notional
        i_pnl = IRS(notional=hedge_notional, fixed_rate=par, maturity=maturity, is_payer=True).npv(up) - \
                IRS(notional=hedge_notional, fixed_rate=par, maturity=maturity, is_payer=True).npv(curve)
        unhedged.append(round(b_pnl / 1e3, 1))
        hedged_vals.append(round((b_pnl + i_pnl) / 1e3, 1))

    # KRD residual after hedge
    krd_bond  = key_rate_duration(bond, curve, KEY_TENORS)
    krd_irs   = key_rate_duration(
        IRS(notional=hedge_notional/notional, fixed_rate=par, maturity=maturity, is_payer=True),
        curve, KEY_TENORS
    )
    residual  = {k: round((krd_bond[k] + krd_irs[k]) * notional, 2) for k in KEY_TENORS}

    return jsonify({
        "bond_dv01":       round(d_bond, 2),
        "mod_duration":    round(bond.mod_duration(curve), 4),
        "hedge_notional":  round(hedge_notional, 2),
        "hedge_ratio":     round(hedge_ratio, 6),
        "par_rate":        round(par * 100, 4),
        "ytm":             round(bond.ytm(curve) * 100, 4),
        "price":           round(bond.price(curve), 4),
        "shifts":          shifts,
        "unhedged":        unhedged,
        "hedged":          hedged_vals,
        "krd_residual":    residual,
    })


@app.route("/api/lcr")
def api_lcr():
    assets = [
        {"label": "Govts AAA-AA",     "book": 3200, "haircut": 0.01, "hqla": "L1",      "illiquid": False},
        {"label": "Covered bonds",    "book": 1100, "haircut": 0.07, "hqla": "L2A",     "illiquid": False},
        {"label": "Corp IG bonds",    "book":  820, "haircut": 0.15, "hqla": "L2B",     "illiquid": True},
        {"label": "Structured credit","book":  310, "haircut": 0.25, "hqla": "Non-HQLA","illiquid": True},
        {"label": "Equity positions", "book":  180, "haircut": 0.50, "hqla": "Non-HQLA","illiquid": True},
    ]
    for a in assets:
        a["repo_value"] = round(a["book"] * (1 - a["haircut"]), 1)

    outflows = [
        {"category": "Retail deposits",      "outflow": 4200, "weight": 0.05},
        {"category": "Wholesale unsecured",  "outflow": 8600, "weight": 0.25},
        {"category": "Secured funding",      "outflow": 3100, "weight": 0.15},
        {"category": "Derivatives / other",  "outflow": 1800, "weight": 1.00},
    ]
    for o in outflows:
        o["weighted"] = round(o["outflow"] * o["weight"], 1)

    total_nco  = sum(o["weighted"] for o in outflows)
    l1 = sum(a["book"] for a in assets if a["hqla"] == "L1")
    l2a= sum(a["book"] * 0.85 for a in assets if a["hqla"] == "L2A")
    l2b= sum(a["book"] * 0.75 for a in assets if a["hqla"] == "L2B")
    hqla = l1 + l2a + l2b
    lcr  = round((hqla / total_nco) * 100, 1)
    nsfr = 112.3

    return jsonify({
        "assets": assets, "outflows": outflows,
        "hqla": round(hqla, 1), "nco": round(total_nco, 1),
        "lcr": lcr, "nsfr": nsfr,
        "l1": round(l1, 1), "l2a": round(l2a, 1), "l2b": round(l2b, 1),
    })


if __name__ == "__main__":
    print("IR Risk Dashboard running at http://localhost:5000")
    app.run(debug=True, port=5000)
