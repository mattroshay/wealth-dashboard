"""Reconcile the DB with config: fill any empty session account lists from Enable Banking,
then delete orphaned Enable Banking accounts (old re-issued ids) and their data.
Run after a re-link if you suspect duplicates:  python3 reconcile.py"""
import common, db

def find_uid(a):
    if isinstance(a, str): return a
    for k in ("uid", "account_id", "id"):
        if a.get(k): return a[k]
    return None

def main():
    cfg = common.load_config(); eb = common.eb_client(cfg); con = db.connect()

    # 1) fill empty session account lists (e.g. BNP) from GET /sessions/{id}
    for s in cfg["enable_banking"]["sessions"]:
        if not s.get("accounts"):
            try:
                info = eb.get_session(s["session_id"])
                uids = [u for u in (find_uid(a) for a in info.get("accounts", [])) if u]
                s["accounts"] = uids
                print(f"{s['bank']}: session -> {len(uids)} account(s): {[u[:8] for u in uids]}")
            except Exception as e:
                print(f"{s['bank']}: could not fetch session ({e})")
    common.save_config(cfg)

    # 2) delete orphaned EB accounts not referenced by any active session
    active = set(u for s in cfg["enable_banking"]["sessions"] for u in s.get("accounts", []))
    orphans = [r["account_uid"] for r in con.execute("SELECT account_uid FROM accounts WHERE provider='EnableBanking'")
               if r["account_uid"] not in active]
    for uid in orphans:
        con.execute("DELETE FROM transactions WHERE account_uid=?", (uid,))
        con.execute("DELETE FROM balances WHERE account_uid=?", (uid,))
        con.execute("DELETE FROM accounts WHERE account_uid=?", (uid,))
        print(f"removed orphan EB account {uid[:10]}…")
    con.commit()
    print("Active EB accounts:", [u[:8] for u in active])
    print("Now run:  python3 sync.py")

if __name__ == "__main__":
    main()
