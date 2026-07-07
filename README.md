# Wealth Dashboard

Self-hosted personal-finance automation for French households. Syncs bank accounts (PSD2 via [Enable Banking](https://enablebanking.com)) and Interactive Brokers into a local SQLite database, categorises transactions with a rule engine tuned for French merchant labels, and renders a zero-dependency single-file HTML dashboard: spending, income, net worth, and a weekly email-style digest.

**No cloud, no third-party aggregator storing your data.** Everything runs locally on a schedule (macOS launchd); the only external calls are to your bank's PSD2 API and IBKR Flex.

## Demo

Open [`demo/dashboard.html`](demo/dashboard.html) — built entirely from synthetic data. Generate your own:

```bash
cd automation
python3 sample_data.py        # seeds wealth.db with ~900 fake French transactions
python3 build_dashboard.py    # renders ../Household-Spending-Dashboard.html
```

## Architecture

```
Enable Banking (PSD2) ─┐
IBKR Flex Query ───────┼─▶ sync.py ─▶ wealth.db (SQLite) ─▶ build_dashboard.py ─▶ dashboard.html
BNP .xls export ───────┘                    │
                                            └─▶ digest.py ─▶ weekly-digest.html
```

- **`sync.py`** — daily sync: pulls transactions + balances from all providers, dedupes on provider IDs, auto-imports bank `.xls` exports dropped in Downloads.
- **`categorize.py`** — rule-based merchant extraction & categorisation for French bank labels (`CARTE 12/03 E.LECLERC…` → *Groceries*). Household-specific patterns (e.g. internal transfers between family members) live in `config.json`, not in code.
- **`db.py`** — one-file SQLite store. Balance snapshots keep min/max/close per day, so year-max and year-end balances for tax reporting (FBAR, IFI) fall out of a query.
- **`build_dashboard.py`** — injects the data as JSON into `dashboard_shell.html`; the output is a single self-contained HTML file, no server needed.
- **`digest.py`** — weekly spending digest.
- **`tax_report.py`**, **`reconcile.py`**, **`reconstruct_balances.py`** — year-end tax figures, sanity checks, and balance back-filling from transaction history.

## Setup

See [`automation/SETUP.md`](automation/SETUP.md). Short version:

```bash
cd automation
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp config.example.json config.json     # add Enable Banking app id + IBKR Flex token
python3 link_banks.py                  # OAuth-style bank consent flow
python3 sync.py                        # first sync pulls up to 2 years of history
```

Scheduling: edit the paths in `com.wealth.sync.plist` / `com.wealth.digest.plist` and load them with `launchctl`.

## Privacy

`config.json` (API credentials, bank session IDs), `wealth.db`, `assets.json`, logs, and generated dashboards are all gitignored. The repo contains code and synthetic demo data only.

## License

MIT
