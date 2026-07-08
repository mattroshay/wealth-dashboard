"""Read wealth.db and (re)generate transactions.json + the dashboard HTML from dashboard_shell.html.
Called at the end of sync.py; can also be run standalone: python3 build_dashboard.py"""
import json, os
import db, categorize

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(HERE, "dashboard_shell.html")
# dashboard is written one level up, next to your other files
OUT_HTML = os.path.join(HERE, "..", "Wealth-Management-Dashboard.html")
OUT_JSON = os.path.join(HERE, "transactions.json")

def acct_label(name, iban):
    n = (name or "").upper()
    if "JOINT" in n: return "Joint account"
    if "PERSO" in n: return "Personal account"
    if "LIVRET" in n: return "Savings"
    if "COURANT" in n or "CHEQUES" in n: return "Current account"
    if "BNP" in n: return "BNP"
    return (name or "Account").title()[:24]

def build(con=None):
    con = con or db.connect()
    # map account_uid -> friendly label (only bank accounts carry spend/income tx)
    labels = {r["account_uid"]: acct_label(r["name"], r["iban"])
              for r in con.execute("SELECT account_uid,name,iban FROM accounts")}
    tx = []
    for r in con.execute("""SELECT account_uid,booking_date,amount,category,merchant,label,kind
                            FROM transactions WHERE kind IN ('s','i') ORDER BY booking_date"""):
        tx.append({"d": r["booking_date"], "acct": labels.get(r["account_uid"], "Account"),
                   "amt": round(r["amount"], 2), "cat": r["category"] or "Other",
                   "m": r["merchant"] or "Unknown", "label": (r["label"] or "")[:60], "k": r["kind"]})
    spend_cats = sorted({t["cat"] for t in tx if t["k"] == "s"})
    inc_cats = sorted({t["cat"] for t in tx if t["k"] == "i"})
    # --- latest balance per account (for the Net Worth panel) ---
    fx = db.get_meta(con, "eur_usd")
    fx = float(fx) if fx else None
    balances = []
    for r in con.execute("""SELECT a.name,a.provider,b.bal_close,b.currency,b.snapshot_date
        FROM balances b JOIN accounts a ON a.account_uid=b.account_uid
        WHERE b.source!='reconstructed'
          AND b.snapshot_date=(SELECT MAX(snapshot_date) FROM balances b2
              WHERE b2.account_uid=b.account_uid AND b2.source!='reconstructed')"""):
        if r["bal_close"] is None:
            continue
        ibkr = r["provider"] == "IBKR"
        nm = "Interactive Brokers" if ibkr else acct_label(r["name"], None)
        cur = r["currency"] if r["currency"] and r["currency"] != "XXX" else "EUR"
        balances.append({"name": nm, "cur": cur,
                         "group": "Investments" if ibkr else "Bank accounts",
                         "val": round(r["bal_close"], 2), "date": r["snapshot_date"]})
    # manual assets & liabilities (property, mortgage, off-platform savings) from assets.json
    ap = os.path.join(HERE, "assets.json")
    if os.path.exists(ap):
        try:
            man = json.load(open(ap, encoding="utf-8"))
            for a in man.get("assets", []):
                v = float(a.get("value") or 0)
                if v: balances.append({"name": a.get("name", "Asset"), "cur": a.get("currency", "EUR"),
                                       "group": "Other assets",
                                       "val": round(v, 2), "date": a.get("as_of", "manual"), "manual": True})
            for l in man.get("liabilities", []):
                v = float(l.get("value") or 0)
                if v: balances.append({"name": l.get("name", "Liability"), "cur": l.get("currency", "EUR"),
                                       "group": "Liabilities",
                                       "val": -round(abs(v), 2), "date": l.get("as_of", "manual"), "manual": True, "liab": True})
        except Exception:
            pass
    bank_labels = {acct_label(r["name"], None) for r in con.execute("SELECT name FROM accounts WHERE kind='bank'")}
    data = {"tx": tx, "accounts": sorted(set(t["acct"] for t in tx) | bank_labels),
            "categories": spend_cats, "incomeCategories": inc_cats,
            "fixed": sorted(categorize.FIXED),
            "balances": balances, "fx": {"eur_usd": fx}}
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    shell = open(SHELL, encoding="utf-8").read()
    html = shell.replace("/*DATA*/{}", json.dumps(data, ensure_ascii=False))
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard rebuilt: {len(tx)} transactions -> {os.path.abspath(OUT_HTML)}")

if __name__ == "__main__":
    build()
