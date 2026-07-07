"""Quick health check of the pipeline data. Usage: python3 status.py"""
import db

def main():
    con = db.connect()
    print("=== Accounts ===")
    for r in con.execute("""SELECT a.name,a.provider,COUNT(t.id) n,MIN(t.booking_date) mn,MAX(t.booking_date) mx
                            FROM accounts a LEFT JOIN transactions t ON t.account_uid=a.account_uid
                            GROUP BY a.account_uid ORDER BY a.provider,a.name"""):
        print(f"  {r['name']:<26} {r['provider']:<13} {r['n'] or 0:>5} tx   {r['mn'] or '-'} -> {r['mx'] or '-'}")
    print("\n=== Spend by category (all time) ===")
    rows = list(con.execute("SELECT category,SUM(-amount) s,COUNT(*) n FROM transactions WHERE kind='s' GROUP BY category ORDER BY s DESC"))
    tot = sum(r["s"] for r in rows) or 1
    for r in rows:
        print(f"  {r['category']:<26} EUR {r['s']:>11,.0f}  ({100*r['s']/tot:4.0f}%)  {r['n']:>4}")
    print(f"  {'TOTAL':<26} EUR {tot:>11,.0f}")
    inc = con.execute("SELECT SUM(amount) s,COUNT(*) n FROM transactions WHERE kind='i'").fetchone()
    print(f"\nTracked income: EUR {inc['s'] or 0:,.0f}  ({inc['n'] or 0} rows)")
    print("\n=== Latest balance per account ===")
    for r in con.execute("""SELECT a.name,b.snapshot_date,b.bal_close,b.currency FROM balances b
        JOIN accounts a ON a.account_uid=b.account_uid
        WHERE b.snapshot_date=(SELECT MAX(snapshot_date) FROM balances b2 WHERE b2.account_uid=b.account_uid)
        ORDER BY a.name"""):
        print(f"  {r['name']:<26} {r['snapshot_date']}  {r['bal_close']:>12,.2f} {r['currency']}")

if __name__ == "__main__":
    main()
