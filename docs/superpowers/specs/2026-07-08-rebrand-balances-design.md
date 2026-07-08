# Design: Wealth Management Dashboard rebrand + per-account balances view

Date: 2026-07-08 · Status: approved by Matt (approach A)

## Context

The dashboard is branded "Household Spending" (page title, sidebar logo, output
filename `Household-Spending-Dashboard.html`), and "household" also appears
across README, case study, SETUP and code comments. Matt wants the word gone
and the app branded **Wealth Management Dashboard**.

The Net worth page today is one total KPI plus a single flat table mixing bank
accounts, IBKR, manual assets and liabilities, sorted by EUR value. It sits
under the global period-filter chips even though balances always show the
latest snapshot — the page looks filterable but isn't. Matt wants the total
kept as-is, with **current balances per account clearly grouped below**.

## Goals

1. Rebrand every user-visible and doc surface to "Wealth Management Dashboard";
   remove the word "household" everywhere.
2. Redesign the Net worth page: total + group subtotals on top, grouped
   current-balance panels below, with an explicit "not affected by the period
   filter" cue.
3. Ship to the public repo as a stacked PR **and** apply the same code changes
   to the live pipeline.

## Non-goals

- No balance-history charts (possible later; the DB already stores daily
  min/max/close per account).
- No new nav item — everything stays on the Net worth page (approach A).
- No schema or sync changes; this is build-time + rendering work only.

## Rebrand scope (file by file)

| File | Change |
|---|---|
| `automation/dashboard_shell.html` | `<title>` → "Wealth Management Dashboard"; sidebar brand `bt`/`bs` → "Wealth Management" / "Dashboard"; Net worth `SUBS` line → "Total net worth and current balances by account" |
| `automation/build_dashboard.py` | `OUT_HTML` → `../Wealth-Management-Dashboard.html` |
| `README.md` | build comment path; "European households" pitch → "built for Europe"-style phrasing; "eurozone households" → "eurozone users"; "French household" demo → phrased without the word; "Household-specific patterns" → "Your own patterns (e.g. transfers between family members)" |
| `docs/case-study.md` | title → "Case study: automating personal finances with open banking"; "Household-specific patterns" reworded |
| `automation/SETUP.md` | diagram + Finder-open path → new filename |
| `automation/categorize.py` | comment: "Add your own patterns (e.g. family members' names…)" |
| `automation/sample_data.py` | docstring: "plausible French personal-finance data" |
| `demo/dashboard.html` | regenerated from the updated shell |

Filename consequences (Matt's side, documented in the PR description): re-point
any Finder shortcut; the old `Household-Spending-Dashboard.html` in the live
folder is not deleted automatically.

## Balances view (approach A)

**Data (`build_dashboard.py`)** — each entry in the `balances` payload gains a
`group` field:

- provider `IBKR` → `Investments`
- account `kind == "bank"` → `Bank accounts`
- `assets.json` assets → `Other assets`
- `assets.json` liabilities → `Liabilities`

**UI (`dashboard_shell.html`, `renderNetWorth`)**

- KPI row: Net worth total (unchanged) + one subtotal tile per non-empty group.
- Below: a "Current balances" card per group — header with group name and
  subtotal; one row per account: Account · As of · Balance (native currency) ·
  In EUR. Sorted by EUR desc within each group. Liabilities styled negative.
- Explicit note: "Current balances as of the last sync — the period filter
  above does not apply here." Existing FX-missing note behaviour kept.
- Grouping happens at build time (Python), keeping the shell dumb — the
  established pattern: intelligence at build time, HTML renders handed JSON.

## Delivery

- Branch `feat/rebrand-balances`, stacked on `feat/generalize-europe`
  (PR #1); draft PR with base `feat/generalize-europe` — GitHub retargets to
  `main` when #1 merges. Merge order stays: PR #1 → flip public → this PR →
  portfolio PR #16.
- Live pipeline: apply identical edits to
  `Projects/Wealth Management/automation/` **code files only** (never data),
  run `build_dashboard.py` there to render the real dashboard.
- Screenshots: sidebar brand changes, so regenerate `docs/screenshot.png` and
  the portfolio image; portfolio PR #16 EN+FR copy drops
  "households / foyers européens".

## Verification

1. Regenerate synthetic demo (`sample_data.py` + `build_dashboard.py`);
   grep demo output: 0 × "Household", 0 × "household".
2. Check group subtotals sum to the net-worth total tile (allowing FX-missing
   exclusions).
3. Playwright screenshot of the Net worth section (demo data) for layout check.
4. Live build renders Matt's real accounts grouped correctly (visual check by
   Matt).
5. Portfolio: `npm run build` green; locale JSON valid.
