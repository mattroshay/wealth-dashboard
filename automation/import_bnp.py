"""Import a BNP Paribas .xls export into the same database.
(BNP's PSD2 redirect is unreliable, so BNP rides on periodic manual exports instead of live sync.)
Usage:
  python3 import_bnp.py                     # auto-find newest export_*.xls in this folder or ~/Downloads
  python3 import_bnp.py /path/to/export.xls
Re-run whenever you drop a fresh BNP export; rows dedupe by content.

This is the manual-import fallback for banks without a working PSD2 feed. It parses BNP's
export format specifically, but the whole file is a ~60-line template: to support another
bank, copy it, adjust the column names / date format, and call it from sync.py."""
import sys, os, glob, hashlib, re, datetime
import pandas as pd
import db, categorize, build_dashboard

BNP_UID = "BNP-CHQ"   # stable synthetic id for the BNP current account

def find_xls():
    if len(sys.argv) > 1:
        return sys.argv[1]
    here = os.path.dirname(os.path.abspath(__file__))
    cands = glob.glob(os.path.join(here, "export_*.xls")) + glob.glob(os.path.expanduser("~/Downloads/export_*.xls"))
    if not cands:
        raise SystemExit("No BNP export found. Pass a path: python3 import_bnp.py /path/to/export.xls")
    return max(cands, key=os.path.getmtime)

def ingest(con, path):
    """Load a BNP .xls export into the DB (dedupes by content). Returns count. No dashboard rebuild."""
    df = pd.read_excel(path, sheet_name=0, header=2).dropna(subset=["Date operation"]).copy()
    db.upsert_account(con, BNP_UID, "BNP-manual", "BNP Paribas", None, "EUR", "bank")
    n = 0
    for _, r in df.iterrows():
        try:
            d = pd.to_datetime(r["Date operation"], format="%d-%m-%Y").date().isoformat()
        except Exception:
            continue
        try:
            amt = round(float(r["Montant operation"]), 2)
        except Exception:
            continue
        label = str(r["Libelle operation"])
        kind, cat, merch = categorize.classify(label, amt)
        tid = BNP_UID + ":" + hashlib.sha1(f"{d}|{amt}|{label}".encode()).hexdigest()[:16]
        db.upsert_transaction(con, {"id": tid, "account_uid": BNP_UID, "booking_date": d, "value_date": d,
            "amount": amt, "currency": "EUR", "label": label[:140], "merchant": merch,
            "category": cat, "kind": kind, "raw": {}})
        n += 1
    # best-effort balance snapshot from the header ("... Solde au DD/MM/YYYY  <value>  EUR")
    try:
        row0 = [str(x) for x in pd.read_excel(path, sheet_name=0, header=None, nrows=1).iloc[0].tolist()]
        m = re.search(r"Solde au (\d{2}/\d{2}/\d{4})", " ".join(row0))
        vals = []
        for x in row0:
            try:
                v = float(str(x).replace(",", "."))
                if v == v: vals.append(v)   # skip NaN (empty trailing cells)
            except Exception: pass
        if m and vals:
            sd = datetime.datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat()
            db.record_balance(con, BNP_UID, sd, "EUR", vals[-1], "BNP-manual")
    except Exception:
        pass
    return n

def main():
    con = db.connect()
    path = find_xls()
    print("Importing", path)
    n = ingest(con, path)
    con.commit()
    print(f"Imported {n} BNP transactions.")
    import build_dashboard
    build_dashboard.build(con)

if __name__ == "__main__":
    main()
