# Wealth pipeline — setup & operating guide

Everything runs locally on your machine (this guide is written for macOS; on Linux, swap the launchd
steps for cron or a systemd timer). Secrets (Enable Banking key, IBKR token) never leave the machine.
Each day the pipeline pulls transactions + balances → stores them in a local SQLite database
(`wealth.db`) → rebuilds the dashboard. History accumulates forever for tax and net worth.

```
Enable Banking (PSD2) ─┐
IBKR Flex ─────────────┤→ sync.py → wealth.db → build_dashboard.py → ../Household-Spending-Dashboard.html
Bank .xls export (auto) ─────┘                 │
                                         ├─ reconstruct_balances → historical daily balances
                                         └─ tax_report.py → max balance / year-end per account
weekly:  digest.py → ../weekly-digest.html + macOS notification
```

Prerequisite: Python 3. All commands run **inside this `automation/` folder** unless noted.

---

## A. One-time setup

### 0. Install
```bash
cd "automation"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p ~/.wealth
cp config.example.json config.json
chmod 600 config.json
```

### 1. Enable Banking app (~5 min)
1. **https://enablebanking.com/sign-in/** → enter email → magic link (no password).
2. **Applications → Register application**:
   - **Name:** anything.
   - **Redirect URLs:** add `https://localhost:8765/callback` (this is the local listener the linker uses).
   - **Private key:** "Generate in the browser" + tick "export private key".
   - Privacy/Terms URLs are mandatory — any valid `https://` URL works (e.g. `https://enablebanking.com/privacy-policy/`).
3. Move + lock the downloaded key:
   ```bash
   mv ~/Downloads/*.pem ~/.wealth/eb_private.pem && chmod 600 ~/.wealth/eb_private.pem
   ```
4. Copy the **Application ID** into `config.json → enable_banking.app_id`.
5. The app shows **Inactive** — that's normal; it activates when you link your own accounts. **Do not** click
   "Request activation" (that's for accessing other people's accounts).

### 2. IBKR Flex (read-only) (~5 min)
IBKR Client Portal → **Performance & Reports → Flex Queries**:
1. Create an **Activity Flex Query** including **Change in NAV** + **Cash Report** (+ Open Positions if wanted). Note the **Query ID**.
2. **Flex Web Service → Enable** → generate a **token** (read-only: reports only, cannot trade/move money).
3. Put both into `config.json → ibkr.flex_token` / `flex_query_id`.

### 3. Link your bank
```bash
python3 link_banks.py --list                 # confirm your bank's exact name is in config.banks
python3 link_banks.py --bank "YourBank"     # opens the consent; approve on your phone
```
The linker runs a local HTTPS listener and catches the redirect automatically. Accept the self-signed
localhost cert warning ("Advanced → Proceed to localhost"). **Chrome works most reliably.**

> **Banks without a working PSD2 feed:** a few banks return empty or broken consents (BNP Paribas
> particulier accounts, at the time of writing). For those, skip live linking: export transactions from the
> bank's website occasionally and drop the `export_*.xls` into your **Downloads** folder (or this folder) —
> `sync.py` auto-imports the newest one. The shipped importer (`import_bnp.py`) parses BNP's export format
> and is a small template to copy for your bank's format.

### 4. First run + net worth
```bash
python3 sync.py                 # pulls ~2 years, builds the dashboard
cp assets.example.json assets.json     # then edit: home values, mortgage balances, savings, car loan
python3 build_dashboard.py      # net worth now includes property equity
```
Some regulated savings accounts (e.g. French Livret A) aren't exposed via PSD2 — add them (and
property/mortgages) in `assets.json`.

### 5. Schedule the daily sync (7am)
Paths in `com.wealth.sync.plist` are already filled in.
```bash
cp com.wealth.sync.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.wealth.sync.plist
launchctl kickstart -p gui/$(id -u)/com.wealth.sync      # test now
tail -n 20 sync.log
```
Runs every morning at 07:00 (catches up on wake). If a background run can't read `~/Documents`, grant
**Full Disk Access** to `…/automation/.venv/bin/python3` in System Settings → Privacy & Security.

### 6. Schedule the weekly digest (Saturdays 8am)
```bash
cp com.wealth.digest.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.wealth.digest.plist
launchctl kickstart -p gui/$(id -u)/com.wealth.digest    # test now
open ../weekly-digest.html
```
Produces `weekly-digest.html` (7-day spend vs prior week, top categories, biggest purchases, new
subscriptions, spikes, duplicate charges, net worth) + a macOS notification.

---

## B. Everyday use

- **Open the dashboard (no terminal):** in Finder, right-click `Household-Spending-Dashboard.html` →
  **Make Alias** → drag the alias to your Desktop/Dock. Or bookmark it in Chrome. It's a plain file —
  **no venv or terminal needed to view it.** It refreshes itself after each daily sync.
- **Ask questions of your data:** the numbers live in `wealth.db`; ask Claude "max balance on the Joint in 2025",
  "groceries in Q1", etc.
- **Tax / FBAR:** `python3 tax_report.py 2025` → per-account max-in-year + year-end closing + CSV
  (native currency; convert to USD at the year-end Treasury rate). History is auto-reconstructed each sync.

## C. Maintenance
- **~Every 180 days** each bank consent expires (EU law): `python3 link_banks.py --bank "YourBank"`.
  A `tx_error` in `sync.log` is your cue. (Re-linking auto-cleans the old re-issued account ids.)
- **Manual-import banks:** drop a fresh `export_*.xls` in Downloads whenever you want them refreshed.
- **Duplicates after a re-link:** `python3 reconcile.py` removes orphaned old account ids.
- **Categories:** edit the `RULES` list in `categorize.py`, then `python3 sync.py` re-labels.
- **Health check:** `python3 status.py` (accounts, tx counts, category split, balances).
- **Security refresh (optional, every few months):** `pip install -U -r requirements.txt`. No auto-updater —
  stable pinned deps are safer for a banking pipeline.

## Security
- `~/.wealth/eb_private.pem` and `config.json` hold secrets — both `chmod 600`, both stay local.
- IBKR Flex token is read-only; nothing here can move money or trade.
- Back up `wealth.db` with your normal backups — it's your full history.

## Files
| File | Role |
|---|---|
| `config.json` | app id, key path, banks, sessions, IBKR token (secret) |
| `assets.json` | manual assets/liabilities (property, mortgages, savings) for net worth |
| `link_banks.py` | link / re-consent a bank (loopback listener) |
| `reconcile.py` | fix duplicates / recover session accounts after a re-link |
| `sync.py` | daily: EB + IBKR + manual `.xls` imports + reconstruct + rebuild |
| `import_bnp.py` | `.xls` importer for banks without PSD2 (BNP format; template for others) |
| `eb_client.py` / `ibkr_flex.py` | API clients |
| `categorize.py` | merchant + category rules |
| `db.py` | SQLite schema + helpers (`wealth.db`) |
| `reconstruct_balances.py` | rebuild historical daily balances from transactions |
| `build_dashboard.py` | DB → dashboard HTML |
| `tax_report.py` | max-balance / year-end reports |
| `status.py` | quick health check |
| `digest.py` | weekly digest HTML + notification |
| `com.wealth.sync.plist` / `com.wealth.digest.plist` | macOS schedules (daily / weekly) |
