"""SQLite store for the wealth pipeline: accounts, transactions, and daily balance snapshots.
Everything lives in one local file (wealth.db) so history accumulates forever and is queryable
for taxes (max balance in a year, year-end closing balance) and net worth over time."""
import sqlite3, json, os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wealth.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts(
  account_uid TEXT PRIMARY KEY,   -- provider account id (EB uid, or IBKR account id)
  provider    TEXT,               -- 'EnableBanking' | 'IBKR'
  name        TEXT,
  iban        TEXT,
  currency    TEXT,
  kind        TEXT                 -- 'bank' | 'brokerage'
);
CREATE TABLE IF NOT EXISTS transactions(
  id           TEXT PRIMARY KEY,   -- stable id from provider (dedupes re-syncs)
  account_uid  TEXT,
  booking_date TEXT,               -- YYYY-MM-DD
  value_date   TEXT,
  amount       REAL,               -- signed, in account currency
  currency     TEXT,
  label        TEXT,
  merchant     TEXT,
  category     TEXT,
  kind         TEXT,               -- 's' spend | 'i' income | 't' internal transfer
  raw          TEXT                -- original provider JSON
);
CREATE INDEX IF NOT EXISTS ix_tx_date ON transactions(booking_date);
CREATE INDEX IF NOT EXISTS ix_tx_acct ON transactions(account_uid);
-- one row per account per day per source; keeps min/max/close seen that day
CREATE TABLE IF NOT EXISTS balances(
  account_uid  TEXT,
  snapshot_date TEXT,             -- YYYY-MM-DD
  currency     TEXT,
  bal_min      REAL,
  bal_max      REAL,
  bal_close    REAL,              -- most recent value seen that day
  source       TEXT,              -- 'EnableBanking' | 'IBKR'
  PRIMARY KEY(account_uid, snapshot_date, source)
);
CREATE TABLE IF NOT EXISTS sync_log(
  ts TEXT, provider TEXT, status TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""

def set_meta(con, key, value):
    con.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)))

def get_meta(con, key, default=None):
    r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con

def upsert_account(con, account_uid, provider, name, iban, currency, kind):
    con.execute("""INSERT INTO accounts(account_uid,provider,name,iban,currency,kind)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(account_uid) DO UPDATE SET provider=excluded.provider,name=excluded.name,
          iban=excluded.iban,currency=excluded.currency,kind=excluded.kind""",
        (account_uid, provider, name, iban, currency, kind))

def upsert_transaction(con, t):
    """t: dict with id, account_uid, booking_date, value_date, amount, currency, label,
    merchant, category, kind, raw(dict)."""
    con.execute("""INSERT INTO transactions
        (id,account_uid,booking_date,value_date,amount,currency,label,merchant,category,kind,raw)
        VALUES(:id,:account_uid,:booking_date,:value_date,:amount,:currency,:label,:merchant,:category,:kind,:raw)
        ON CONFLICT(id) DO UPDATE SET
          category=excluded.category, merchant=excluded.merchant, kind=excluded.kind""",
        {**t, "raw": json.dumps(t.get("raw", {}), ensure_ascii=False)})

def record_balance(con, account_uid, snapshot_date, currency, value, source):
    """Records a balance sighting; keeps min/max/close for the day (FBAR max + year-end close)."""
    if value is None or value != value:   # ignore None/NaN sightings (sqlite stores NaN as NULL)
        return
    row = con.execute("""SELECT bal_min,bal_max FROM balances
        WHERE account_uid=? AND snapshot_date=? AND source=?""",
        (account_uid, snapshot_date, source)).fetchone()
    if row is None:
        con.execute("""INSERT INTO balances(account_uid,snapshot_date,currency,bal_min,bal_max,bal_close,source)
            VALUES(?,?,?,?,?,?,?)""",
            (account_uid, snapshot_date, currency, value, value, value, source))
    else:
        # stored NULLs (legacy NaN writes) count as "no prior sighting" so the row heals
        lo = value if row["bal_min"] is None else min(row["bal_min"], value)
        hi = value if row["bal_max"] is None else max(row["bal_max"], value)
        con.execute("""UPDATE balances SET bal_min=?, bal_max=?, bal_close=?, currency=?
            WHERE account_uid=? AND snapshot_date=? AND source=?""",
            (lo, hi, value, currency, account_uid, snapshot_date, source))

def log(con, provider, status, detail=""):
    import datetime
    con.execute("INSERT INTO sync_log(ts,provider,status,detail) VALUES(?,?,?,?)",
                (datetime.datetime.now().isoformat(timespec="seconds"), provider, status, detail))

if __name__ == "__main__":
    con = connect(); con.commit()
    print("Initialised", DB_PATH)
