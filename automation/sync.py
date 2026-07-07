"""Daily sync: pull transactions + balances from Enable Banking and NAV/cash from IBKR Flex,
store into wealth.db, then rebuild the dashboard. Safe to run repeatedly (dedupes by id/day).
Usage:  python3 sync.py"""
import datetime, hashlib, json, traceback
import db, common, categorize

def g(d, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return default

def amount_of(t):
    a = g(t, "transaction_amount", "transactionAmount", default={})
    val = float(g(a, "amount", default=0) or 0)
    ind = (g(t, "credit_debit_indicator", "creditDebitIndicator", default="") or "").upper()
    return -val if ind == "DBIT" else val, g(a, "currency", default="EUR")

def label_of(t):
    ri = g(t, "remittance_information", "remittanceInformation", default=[])
    if isinstance(ri, list) and ri:
        return " ".join(str(x) for x in ri)[:140]
    if isinstance(ri, str) and ri:
        return ri[:140]
    for who in ("creditor", "debtor"):
        nm = g(t, who, default={})
        if isinstance(nm, dict) and nm.get("name"):
            return nm["name"][:140]
    return (g(t, "bank_transaction_code", default="") or "TRANSACTION")

def tx_id(t, account_uid, date, amount, label):
    eid = g(t, "entry_reference", "entryReference", "transaction_id", "transactionId")
    if eid:
        return f"{account_uid}:{eid}"
    return account_uid + ":" + hashlib.sha1(f"{date}|{amount}|{label}".encode()).hexdigest()[:16]

def pick_balance(balances):
    order = ["closingBooked", "expected", "interimAvailable", "interimBooked", "openingBooked"]
    def key(b):
        bt = g(b, "balance_type", "balanceType", default="")
        return order.index(bt) if bt in order else len(order)
    for b in sorted(balances, key=key):
        amt = g(b, "balance_amount", "balanceAmount", default={})
        if g(amt, "amount") is not None:
            return float(amt["amount"]), g(amt, "currency", default="EUR")
    return None, None

def last_booking(con, account_uid):
    r = con.execute("SELECT MAX(booking_date) d FROM transactions WHERE account_uid=?", (account_uid,)).fetchone()
    return r["d"]

def sync_enable_banking(con, cfg):
    eb = common.eb_client(cfg)
    today = datetime.date.today().isoformat()
    for sess in cfg["enable_banking"].get("sessions", []):
        for uid in sess.get("accounts", []):
            # ensure the account record exists (self-heal names so the dashboard can label it)
            if not con.execute("SELECT 1 FROM accounts WHERE account_uid=?", (uid,)).fetchone():
                nm = sess.get("bank", "Account"); iban = curr = None
                try:
                    d = eb.account_details(uid)
                    nm = d.get("name") or d.get("product") or nm
                    ai = d.get("account_id"); iban = ai.get("iban") if isinstance(ai, dict) else d.get("iban")
                    curr = d.get("currency")
                except Exception:
                    pass
                db.upsert_account(con, uid, "EnableBanking", nm, iban, curr or "EUR", "bank")
            # balances -> daily snapshot
            try:
                bal, curr = pick_balance(eb.balances(uid))
                if bal is not None:
                    db.record_balance(con, uid, today, curr or "EUR", bal, "EnableBanking")
            except Exception as e:
                db.log(con, "EnableBanking", "balance_error", f"{uid[:8]}: {e}")
            # transactions since last (with overlap), or full history on first run
            lb = last_booking(con, uid)
            if lb:
                date_from = (datetime.date.fromisoformat(lb) - datetime.timedelta(days=5)).isoformat()
            else:
                date_from = (datetime.date.today() - datetime.timedelta(days=cfg.get("history_days_on_first_sync", 730))).isoformat()
            n = 0
            try:
                for t in eb.transactions(uid, date_from):
                    bdate = (g(t, "booking_date", "bookingDate", "value_date", "valueDate", default=today))[:10]
                    amt, ccy = amount_of(t)
                    lab = label_of(t)
                    kind, cat, merch = categorize.classify(lab, amt)
                    db.upsert_transaction(con, {
                        "id": tx_id(t, uid, bdate, amt, lab), "account_uid": uid,
                        "booking_date": bdate, "value_date": (g(t, "value_date", "valueDate", default=bdate))[:10],
                        "amount": amt, "currency": ccy, "label": lab, "merchant": merch,
                        "category": cat, "kind": kind, "raw": t})
                    n += 1
                db.log(con, "EnableBanking", "ok", f"{uid[:8]}: {n} tx from {date_from}")
            except Exception as e:
                db.log(con, "EnableBanking", "tx_error", f"{uid[:8]}: {e}")
        con.commit()

def sync_ibkr(con, cfg):
    ib = cfg.get("ibkr", {})
    if not ib.get("enabled") or "PASTE" in ib.get("flex_token", "PASTE"):
        return
    import ibkr_flex
    try:
        xml = ibkr_flex.fetch_report(ib["flex_token"], ib["flex_query_id"])
        rows = ibkr_flex.parse_nav_and_cash(xml)
        fx = ibkr_flex.parse_fx(xml, "EUR", "USD")   # USD per 1 EUR
        if fx:
            db.set_meta(con, "eur_usd", fx)
        for r in rows:
            acct = r["account_id"] or "IBKR"
            date = _fmt(r["date"])
            db.upsert_account(con, acct, "IBKR", "Interactive Brokers", None, r.get("currency", "USD"), "brokerage")
            if r.get("nav") is not None and date:
                db.record_balance(con, acct, date, r.get("currency", "USD"), r["nav"], "IBKR")
        db.log(con, "IBKR", "ok", f"{len(rows)} nav rows")
        con.commit()
    except Exception as e:
        db.log(con, "IBKR", "error", str(e))

def _fmt(d):
    d = (d or "").replace("-", "")
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else None

def sync_bnp_manual(con):
    """BNP has no working live PSD2 feed, so auto-ingest the newest BNP .xls export found in
    this folder or ~/Downloads. Just drop a fresh export and the daily sync picks it up."""
    import glob, os
    here = os.path.dirname(os.path.abspath(__file__))
    cands = glob.glob(os.path.join(here, "export_*.xls")) + glob.glob(os.path.expanduser("~/Downloads/export_*.xls"))
    if not cands:
        return
    path = max(cands, key=os.path.getmtime)
    try:
        import import_bnp
        n = import_bnp.ingest(con, path)
        con.commit()
        db.log(con, "BNP-manual", "ok", f"{n} tx from {os.path.basename(path)}")
    except Exception as e:
        db.log(con, "BNP-manual", "error", str(e))

def main():
    con = db.connect()
    try:
        sync_enable_banking(con, common.load_config())
        sync_ibkr(con, common.load_config())
        sync_bnp_manual(con)
        import reconstruct_balances
        reconstruct_balances.reconstruct(con)
        import build_dashboard
        build_dashboard.build(con)
        db.log(con, "pipeline", "complete", "")
    except Exception:
        db.log(con, "pipeline", "fatal", traceback.format_exc()[-500:])
        raise
    finally:
        con.commit(); con.close()
    print("Sync complete.")

if __name__ == "__main__":
    main()
