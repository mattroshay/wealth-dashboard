"""Seed wealth.db with SYNTHETIC data so the whole pipeline can be demoed
without linking a real bank. Generates ~18 months of plausible French household
transactions (fake amounts, real-looking merchant labels), daily-ish balance
snapshots, and an IBKR-style brokerage account.

Usage:
    python3 sample_data.py          # (re)creates wealth.db with demo data
    python3 build_dashboard.py      # then build the dashboard from it

Everything here is random and fictional. Deterministic via --seed (default 42).
"""
import argparse, datetime as dt, os, random

import db, categorize

ACCOUNTS = [
    ("demo-joint",  "EnableBanking", "COMPTE JOINT M ET MME DEMO", "FR7600000000000000000001", "EUR", "bank"),
    ("demo-perso",  "EnableBanking", "COMPTE PERSO M DEMO",        "FR7600000000000000000002", "EUR", "bank"),
    ("demo-bnp",    "EnableBanking", "BNP COMPTE CHEQUES",         "FR7600000000000000000003", "EUR", "bank"),
    ("demo-ibkr",   "IBKR",          "Interactive Brokers",        None,                        "USD", "brokerage"),
]

# (label template, category hint, min€, max€, monthly frequency)
SPEND = [
    ("ECH PRET 00012345 HABITAT",            1350, 1350, 1),     # mortgage
    ("PRLV EDF CLIENTS PARTICULIERS",          85,  160, 1),
    ("PRLV FREE MOBILE",                       16,   20, 2),
    ("PRLV FREE HAUT DEBIT",                   30,   35, 1),
    ("PRLV AXA ASSURANCES IARD",               60,   75, 1),
    ("PRLV PAJEMPLOI URSSAF",                 450,  650, 1),
    ("CARTE {d} E.LECLERC BORDEAUX",           45,  180, 5),
    ("CARTE {d} CARREFOUR MARKET",             15,   90, 4),
    ("CARTE {d} GRAND FRAIS",                  25,   70, 2),
    ("CARTE {d} BOULANGERIE DU MARCHE",         3,   14, 6),
    ("CARTE {d} RESTAURANT LE BISTROT",        30,   95, 2),
    ("CARTE {d} COTE SUSHI BORDEAUX",          25,   55, 1),
    ("CARTE {d} AMAZON EU SARL",               12,  120, 3),
    ("CARTE {d} NETFLIX.COM",                  14,   14, 1),
    ("CARTE {d} SPOTIFY AB",                   11,   11, 1),
    ("CARTE {d} ANTHROPIC CLAUDE.AI",          22,   22, 1),
    ("CARTE {d} GITHUB INC",                   10,   10, 1),
    ("CARTE {d} SHELL BORDEAUX",               55,   85, 2),
    ("CARTE {d} VINCI AUTOROUTES",              8,   35, 2),
    ("CARTE {d} SNCF CONNECT",                 25,  140, 1),
    ("CARTE {d} DECATHLON",                    20,  110, 1),
    ("CARTE {d} IKEA BORDEAUX",                30,  250, 0.5),
    ("CARTE {d} PHARMACIE CENTRALE",            8,   45, 2),
    ("CARTE {d} FNAC DARTY",                   20,  180, 0.7),
    ("RET DAB 60 EUR",                         60,   60, 1),
    ("F COTISATION EUROCOMPTE",                 9,    9, 1),
    ("CARTE {d} AIRBNB PAYMENTS",             250,  900, 0.15),
    ("CARTE {d} EASYJET",                      90,  400, 0.15),
    ("CARTE {d} ECOLE DE MUSIQUE CANTINE",     35,   90, 1),
]

INCOME = [
    ("VIREMENT DE ACME CONSEIL SAS SALAIRE",  3400, 3400, 1),
    ("VIREMENT DE CAF DE LA GIRONDE",          180,  180, 1),
    ("VIR C.P.A.M. DE LA GIRONDE",              15,   80, 1.5),
    ("VIREMENT DE DGFIP REMBOURSEMENT",        120,  600, 0.1),
]


def month_iter(months):
    today = dt.date.today().replace(day=1)
    for i in range(months, -1, -1):
        y, m = divmod((today.year * 12 + today.month - 1) - i, 12)
        yield y, m + 1


def gen(months=18, seed=42):
    rng = random.Random(seed)
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    con = db.connect()
    for a in ACCOUNTS:
        db.upsert_account(con, *a)

    bank_uids = [a[0] for a in ACCOUNTS if a[5] == "bank"]
    n = 0
    for y, m in month_iter(months):
        days = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.date(y, m, 1)).days
        for tpl, lo, hi, freq in SPEND + INCOME:
            is_income = (tpl, lo, hi, freq) in INCOME
            k = freq if freq >= 1 else (1 if rng.random() < freq else 0)
            for _ in range(int(k) if freq >= 1 else k):
                day = rng.randint(1, days)
                date = f"{y:04d}-{m:02d}-{day:02d}"
                if date > dt.date.today().isoformat():
                    continue
                label = tpl.format(d=f"{day:02d}/{m:02d}")
                amount = round(rng.uniform(lo, hi), 2) * (1 if is_income else -1)
                kind, cat, merch = categorize.classify(label, amount)
                uid = rng.choice(bank_uids)
                n += 1
                db.upsert_transaction(con, {
                    "id": f"demo-{n:06d}", "account_uid": uid,
                    "booking_date": date, "value_date": date,
                    "amount": amount, "currency": "EUR", "label": label,
                    "merchant": merch, "category": cat, "kind": kind,
                    "raw": {"demo": True}})

    # balance snapshots: gentle upward drift + noise
    base = {"demo-joint": 4200.0, "demo-perso": 2600.0, "demo-bnp": 1800.0, "demo-ibkr": 38000.0}
    start = dt.date.today() - dt.timedelta(days=months * 30)
    d = start
    while d <= dt.date.today():
        for uid, b in base.items():
            drift = (d - start).days * (2.2 if uid == "demo-ibkr" else 0.35)
            noise = rng.uniform(-400, 400) if uid != "demo-ibkr" else rng.uniform(-1500, 1500)
            cur = "USD" if uid == "demo-ibkr" else "EUR"
            src = "IBKR" if uid == "demo-ibkr" else "EnableBanking"
            db.record_balance(con, uid, d.isoformat(), cur, round(b + drift + noise, 2), src)
        d += dt.timedelta(days=3)

    db.set_meta(con, "eur_usd", "1.08")
    con.commit()
    print(f"Seeded {n} synthetic transactions across {len(ACCOUNTS)} accounts -> {db.DB_PATH}")
    print("Now run: python3 build_dashboard.py")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=18)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    gen(a.months, a.seed)
