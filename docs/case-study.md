# Case study: automating a household's finances in France

*Portfolio write-up — pair with the [live demo dashboard](../demo/dashboard.html) (100% synthetic data) and the [GitHub repo](https://github.com/mattroshay/wealth-dashboard).*

## The problem

Managing money across two French banks and a US brokerage meant logging into three portals, exporting spreadsheets, and hand-categorising transactions — and French tax reporting (plus US FBAR filing) needs numbers no bank shows you, like each account's *maximum* balance during the year. Off-the-shelf aggregators either don't cover French banks well, charge monthly fees, or ship your transaction history to their cloud.

## The solution

A local-first pipeline that runs unattended on a Mac mini:

1. **Bank data via PSD2.** Enable Banking provides the regulated open-banking rails; a small JWT-authenticated client pulls transactions and balances daily. Bank consents expire every 180 days by EU law, so re-linking is a single command.
2. **Brokerage via IBKR Flex Queries** — token-based XML reports, no credentials stored.
3. **One SQLite file** as the source of truth. Balance sightings are stored as per-day min/max/close, which makes tax questions ("highest balance in 2025", "balance on 31 Dec") trivial queries instead of archaeology.
4. **A rule engine for French merchant labels.** Raw labels like `CARTE 12/03 E.LECLERC BORDEAUX 33` are normalised to merchants and mapped to ~20 categories; credits are classified into income vs. internal transfers vs. refunds so the numbers aren't polluted by money moving between own accounts. Household-specific patterns are config, not code.
5. **A single-file HTML dashboard** — data injected as JSON into a template at build time. No server, no build step, no dependencies; it opens instantly from Finder and works offline.
6. **launchd scheduling + weekly digest** — a Monday-morning HTML digest of the week's spending by category.

## Design decisions

**Local-first over SaaS.** Financial data never leaves the machine except for the regulated API calls to the banks themselves. That also made the privacy story for open-sourcing simple: secrets and data are files that were gitignored from day one; the repo is code plus a synthetic-data generator.

**SQLite over anything fancier.** One file, queryable forever, trivially backed up. The schema (accounts / transactions / balance-snapshots / sync-log) has survived every feature added since.

**Rules over ML for categorisation.** French bank labels are formulaic enough that ~60 rules hit high accuracy, run in microseconds, and are auditable — important when the output feeds tax reporting. The interface (`classify(label, amount)`) is deliberately narrow so an LLM categoriser can slot in later for the "Other" tail.

**Idempotent syncs.** Every transaction upserts on the provider's stable ID, so re-running a sync (or re-importing an overlapping bank export) can never double-count.

## Results

- Daily automatic sync of 4 accounts across 3 institutions; zero manual entry since launch.
- Year-end tax prep (max/closing balances per account, FBAR) went from an afternoon of statement-digging to running one script.
- ~1,100 lines of Python, no external services, no recurring cost.

## Stack

Python (stdlib + `requests`, `PyJWT`, `cryptography`, `pandas`), SQLite, Enable Banking PSD2 API, IBKR Flex, vanilla JS/HTML dashboard, macOS launchd.
