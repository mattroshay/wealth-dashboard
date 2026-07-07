"""Reconstruct historical daily closing balances by walking each bank account's transactions
backward from its current balance. This makes tax_report.py meaningful for PAST years
(e.g. 2025 FBAR) immediately, instead of waiting for daily snapshots to accumulate.

Method: current balance = balance after all transactions. End-of-day balance for date D
= current - (sum of transaction amounts on days after D). We record one 'reconstructed'
snapshot per day that had activity; tax_report carries the last value forward to year-end.

Run after a sync:  python3 reconstruct_balances.py
Re-runnable anytime (idempotent)."""
import db

def reconstruct(con, verbose=False):
    for a in con.execute("SELECT account_uid,name FROM accounts WHERE kind='bank'").fetchall():
        uid, name = a["account_uid"], a["name"]
        cb = con.execute("""SELECT bal_close,currency FROM balances
            WHERE account_uid=? AND source!='reconstructed'
            ORDER BY snapshot_date DESC LIMIT 1""", (uid,)).fetchone()
        if not cb or cb["bal_close"] is None:
            if verbose: print(f"  skip {name}: no current balance snapshot yet")
            continue
        cur, ccy = cb["bal_close"], (cb["currency"] or "EUR")
        daily = {}
        for t in con.execute("SELECT booking_date d, amount FROM transactions WHERE account_uid=?", (uid,)):
            daily[t["d"]] = daily.get(t["d"], 0) + t["amount"]
        if not daily:
            if verbose: print(f"  skip {name}: no transactions")
            continue
        running, n = cur, 0
        for d in sorted(daily, reverse=True):          # newest -> oldest
            db.record_balance(con, uid, d, ccy, round(running, 2), "reconstructed")
            running -= daily[d]                          # step back to prior day's close
            n += 1
        con.commit()
        if verbose: print(f"  {name}: reconstructed {n} daily balances back to {min(daily)}")
    con.commit()

def main():
    con = db.connect()
    reconstruct(con, verbose=True)
    con.close()
    print("Done. Try:  python3 tax_report.py 2025")

if __name__ == "__main__":
    main()
