"""US-tax / FBAR helper. For a given year, per account:
  - maximum balance during the year (FBAR 'maximum value')  [from daily bal_max snapshots]
  - year-end closing balance (as of the last snapshot on/before Dec 31)
Balances are in each account's native currency; FBAR wants USD at the Treasury year-end rate —
convert the figures below with that rate. Writes a CSV alongside the DB.
Usage:  python3 tax_report.py 2025"""
import sys, os, csv
import db

def report(year):
    con = db.connect()
    y0, y1 = f"{year}-01-01", f"{year}-12-31"
    accts = con.execute("SELECT account_uid,provider,name,currency FROM accounts ORDER BY provider,name").fetchall()
    rows = []
    for a in accts:
        uid = a["account_uid"]
        mx = con.execute("""SELECT snapshot_date, bal_max FROM balances
            WHERE account_uid=? AND snapshot_date BETWEEN ? AND ?
            ORDER BY bal_max DESC LIMIT 1""", (uid, y0, y1)).fetchone()
        close = con.execute("""SELECT snapshot_date, bal_close FROM balances
            WHERE account_uid=? AND snapshot_date<=? ORDER BY snapshot_date DESC LIMIT 1""",
            (uid, y1)).fetchone()
        if not mx and not close:
            continue
        rows.append({
            "provider": a["provider"], "account": a["name"], "currency": a["currency"],
            "max_balance": round(mx["bal_max"], 2) if mx else "",
            "max_on": mx["snapshot_date"] if mx else "",
            "closing_balance": round(close["bal_close"], 2) if close else "",
            "closing_as_of": close["snapshot_date"] if close else "",
        })
    # print
    print(f"\n=== Balance report for {year} (native currency) ===")
    print(f"{'Account':32} {'Ccy':4} {'Max in year':>14} {'(on)':>12} {'Year-end':>14} {'(as of)':>12}")
    for r in rows:
        print(f"{r['account'][:32]:32} {r['currency'] or '':4} {str(r['max_balance']):>14} "
              f"{r['max_on']:>12} {str(r['closing_balance']):>14} {r['closing_as_of']:>12}")
    if not rows:
        print("  (no balance snapshots yet — run sync.py first, and let it accumulate)")
    # csv
    out = os.path.join(os.path.dirname(db.DB_PATH), f"tax_balances_{year}.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["provider","account","currency","max_balance","max_on","closing_balance","closing_as_of"])
        w.writeheader(); w.writerows(rows)
    print(f"\nSaved {out}")
    print("Note: FBAR/Form 8938 want USD at the year-end Treasury rate — convert the figures above.")

if __name__ == "__main__":
    yr = int(sys.argv[1]) if len(sys.argv) > 1 else __import__("datetime").date.today().year - 1
    report(yr)
