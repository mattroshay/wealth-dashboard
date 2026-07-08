# Wealth Management Dashboard Rebrand + Grouped Balances Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebrand the app from "Household Spending" to "Wealth Management Dashboard" (removing the word "household" everywhere) and redesign the Net worth page to show the total on top and grouped current balances per account below.

**Architecture:** All intelligence stays at build time: `build_dashboard.py` tags each balance with a `group` in the JSON payload; `dashboard_shell.html` only renders what it's handed. Docs and comments are text edits. Repo work ships on branch `feat/rebrand-balances` (stacked on `feat/generalize-europe`, PR #1); the same code edits are then applied to the live pipeline.

**Tech Stack:** Python 3 (stdlib + sqlite3), vanilla JS/HTML single-file dashboard, git/gh, Playwright MCP for screenshots.

## Global Constraints

- Exact brand strings: page title `Wealth Management Dashboard`; sidebar brand `<div class="bt">Wealth Management</div><div class="bs">Dashboard</div>`; output filename `Wealth-Management-Dashboard.html`.
- Exact group names: `Bank accounts`, `Investments`, `Other assets`, `Liabilities` (this order).
- The word "household" (any case) must not appear anywhere in the repo after Task 4 (spec/plan docs under `docs/superpowers/` quoting the old name are exempt).
- Working directory for Tasks 1–5: `/Users/mattroshay/Documents/Claude/Projects/Wealth Management/wealth-dashboard/.claude/worktrees/rebrand-balances` (branch `feat/rebrand-balances`). Run all commands from there.
- LIVE pipeline (`/Users/mattroshay/Documents/Claude/Projects/Wealth Management/automation/`) holds real financial data: Task 6 may edit **code files only**, never `config.json`, `wealth.db`, `assets.json`, logs, or generated dashboards. Nothing from that folder is ever committed or published.
- Never push to main/master; never force-push. Repo is PRIVATE until Matt flips it.
- No test framework exists in this repo — each task's "test" is a runnable check command with its expected output. Run the check before implementing (expect FAIL) and after (expect PASS).
- Generated artifacts in `automation/` (`wealth.db`, `transactions.json`, `../Wealth-Management-Dashboard.html`) are build side-effects: never commit them; delete them at the end of any task that created them. Use `command cp -f` / `command rm -f` / `command mv -f` (the shell has an interactive `cp` alias that blocks on overwrite prompts).
- The macOS shell globs `=` sequences: don't use `===` separators in echo strings.

---

### Task 1: Rebrand all text surfaces

**Files:**
- Modify: `automation/dashboard_shell.html:5` (title), `:139` (brand), `:484` (SUBS net-worth line)
- Modify: `automation/build_dashboard.py:9` (OUT_HTML)
- Modify: `README.md:3,16,29,56,57`
- Modify: `docs/case-study.md:1,16`
- Modify: `automation/SETUP.md:10,103`
- Modify: `automation/categorize.py:52`
- Modify: `automation/sample_data.py:2`

**Interfaces:**
- Produces: output filename `../Wealth-Management-Dashboard.html` (Tasks 2–4 and 6 clean up / verify this exact name).

- [ ] **Step 1: Run the check to see it fail**

```bash
grep -rni "household" --include="*.md" --include="*.py" --include="*.html" . | grep -v "^./demo/dashboard.html" | grep -v "^./docs/superpowers/"
```
Expected: FAIL — ~16 matching lines print (README, case-study, SETUP, shell, build script, comments).

- [ ] **Step 2: Apply the edits** (exact old → new; use the Edit tool with these strings)

`automation/dashboard_shell.html`:
- `<title>Household Spending — Interactive</title>` → `<title>Wealth Management Dashboard</title>`
- `<div class="bt">Household</div><div class="bs">Spending</div>` → `<div class="bt">Wealth Management</div><div class="bs">Dashboard</div>`
- `'sec-networth':'Latest balances across banks + Interactive Brokers'` → `'sec-networth':'Total net worth and current balances by account'`

`automation/build_dashboard.py`:
- `OUT_HTML = os.path.join(HERE, "..", "Household-Spending-Dashboard.html")` → `OUT_HTML = os.path.join(HERE, "..", "Wealth-Management-Dashboard.html")`

`README.md`:
- `Self-hosted personal-finance automation for European households.` → `Self-hosted personal-finance automation built for Europe.`
- `python3 build_dashboard.py    # renders ../Household-Spending-Dashboard.html` → `python3 build_dashboard.py    # renders ../Wealth-Management-Dashboard.html`
- `Household-specific patterns (e.g. internal transfers between family members) live in` → `Your own patterns (e.g. internal transfers between family members) live in`
- `EUR, so eurozone households work out of the box;` → `EUR, so eurozone users work out of the box;`
- `the synthetic dataset simulates a French household so the categoriser` → `the synthetic dataset simulates typical French accounts so the categoriser`

`docs/case-study.md`:
- `# Case study: automating a household's finances with open banking` → `# Case study: automating personal finances with open banking`
- `Household-specific patterns are config, not code.` → `User-specific patterns are config, not code.`

`automation/SETUP.md`:
- `../Household-Spending-Dashboard.html` → `../Wealth-Management-Dashboard.html` (diagram line 10)
- `` right-click `Household-Spending-Dashboard.html` `` → `` right-click `Wealth-Management-Dashboard.html` `` (line 103)

`automation/categorize.py`:
- `# Generic internal-transfer markers. Add your own household patterns (e.g. family` → `# Generic internal-transfer markers. Add your own patterns (e.g. family`

`automation/sample_data.py`:
- `Generates ~18 months of plausible French household` → `Generates ~18 months of plausible French personal-finance`

- [ ] **Step 3: Run the check to see it pass**

Same grep as Step 1. Expected: PASS — zero lines (exit code 1 from grep).

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "Rebrand to Wealth Management Dashboard, remove 'household' wording"
```

---

### Task 2: Tag each balance with a group in build_dashboard.py

**Files:**
- Modify: `automation/build_dashboard.py:38-61` (balances loop + manual assets/liabilities)

**Interfaces:**
- Produces: every entry in the JSON `balances` array has `"group"` ∈ {`Bank accounts`, `Investments`, `Other assets`, `Liabilities`}. Task 3's JS relies on the exact key `group` and these exact four names.

- [ ] **Step 1: Write the failing check**

```bash
cd automation && python3 sample_data.py && python3 build_dashboard.py && python3 - <<'EOF'
import json
d = json.load(open("transactions.json"))
bals = d["balances"]
assert bals, "no balances in demo payload"
assert all("group" in b for b in bals), "missing group key"
gs = {b["group"] for b in bals}
allowed = {"Bank accounts", "Investments", "Other assets", "Liabilities"}
assert gs <= allowed, gs
assert any(b["group"] == "Investments" for b in bals), "IBKR not tagged Investments"
print("OK - groups:", sorted(gs))
EOF
```
Expected: FAIL with `AssertionError: missing group key`.

- [ ] **Step 2: Implement**

In the balances query loop, replace:
```python
        nm = "Interactive Brokers" if r["provider"] == "IBKR" else acct_label(r["name"], None)
        cur = r["currency"] if r["currency"] and r["currency"] != "XXX" else "EUR"
        balances.append({"name": nm, "cur": cur,
                         "val": round(r["bal_close"], 2), "date": r["snapshot_date"]})
```
with:
```python
        ibkr = r["provider"] == "IBKR"
        nm = "Interactive Brokers" if ibkr else acct_label(r["name"], None)
        cur = r["currency"] if r["currency"] and r["currency"] != "XXX" else "EUR"
        balances.append({"name": nm, "cur": cur,
                         "group": "Investments" if ibkr else "Bank accounts",
                         "val": round(r["bal_close"], 2), "date": r["snapshot_date"]})
```

In the manual assets/liabilities block, add the group keys:
```python
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
```

- [ ] **Step 3: Re-run the Step 1 check**

Expected: PASS — `OK - groups: ['Bank accounts', 'Investments']` (demo has no assets.json, so only two groups — correct).

- [ ] **Step 4: Clean up generated artifacts and commit**

```bash
cd automation && command rm -f wealth.db transactions.json "../Wealth-Management-Dashboard.html" && cd .. \
  && git add automation/build_dashboard.py && git commit -m "Tag balances with account group at build time"
```

---

### Task 3: Grouped balances UI in the Net worth section

**Files:**
- Modify: `automation/dashboard_shell.html:216-222` (section markup) and the `renderNetWorth` function (~line 418)

**Interfaces:**
- Consumes: `DATA.balances[]` entries with `group` (Task 2), plus existing helpers `eur()` and CSS classes `.card`, `.kpi`, `.chip`, `.muted`, `.num`, `.delta.up`, `.note`.
- Produces: container ids `nwkpis`, `nwnote`, `nwgroups` (Task 4's visual check looks for these).

- [ ] **Step 1: Write the failing check**

```bash
grep -c 'id="nwgroups"' automation/dashboard_shell.html
```
Expected: FAIL — `0`.

- [ ] **Step 2: Replace the section markup**

Old:
```html
    <section class="section" id="sec-networth" data-screen-label="Net worth">
      <div class="grid kpis" id="nwkpis"></div>
      <div class="card"><h3>Balances by account <small>— latest snapshot, incl. Interactive Brokers</small></h3>
        <table><thead><tr><th>Account</th><th>As of</th><th class="num">Balance</th><th class="num">In EUR</th></tr></thead><tbody id="nwbody"></tbody></table>
        <div class="note" id="nwnote"></div>
      </div>
    </section>
```
New:
```html
    <section class="section" id="sec-networth" data-screen-label="Net worth">
      <div class="grid kpis" id="nwkpis"></div>
      <div class="note" id="nwnote" style="margin-bottom:12px"></div>
      <div id="nwgroups" style="display:grid;gap:14px"></div>
    </section>
```

- [ ] **Step 3: Replace the whole `renderNetWorth` function**

Old function starts `function renderNetWorth(){` and ends at its closing `}` (it references `nwbody`). New:
```js
    function renderNetWorth(){
      const wrap=document.getElementById('nwgroups'); if(!wrap)return;
      const fx=(DATA.fx&&DATA.fx.eur_usd)||null; const bals=DATA.balances||[];
      const toEur=b=>(b.cur==='EUR')?b.val:(fx?b.val/fx:null);
      let total=0,missing=false;
      const rows=bals.map(b=>{const e=toEur(b); if(e==null)missing=true; else total+=e; return Object.assign({eur:e},b);});
      const ORDER=['Bank accounts','Investments','Other assets','Liabilities'];
      const groups=ORDER.map(g=>({g,rows:rows.filter(r=>(r.group||'Bank accounts')===g).sort((a,b)=>(b.eur||0)-(a.eur||0))})).filter(x=>x.rows.length);
      const sub=x=>x.rows.reduce((s,r)=>s+(r.eur||0),0);
      const k=document.getElementById('nwkpis');
      if(k)k.innerHTML=[
        `<div class="card kpi"><div class="lab">Net worth (est., EUR)</div><div class="val">${eur(total)}</div><div class="note" style="background:none;padding:0;margin-top:4px">${bals.length} account${bals.length!==1?'s':''}${fx?` · USD→EUR @ ${(1/fx).toFixed(4)}`:''}</div></div>`,
        ...groups.map(x=>`<div class="card kpi"><div class="lab">${x.g}</div><div class="val">${eur(sub(x))}</div><div class="note" style="background:none;padding:0;margin-top:4px">${x.rows.length} account${x.rows.length!==1?'s':''}</div></div>`)
      ].join('');
      wrap.innerHTML=groups.length?groups.map(x=>`<div class="card"><h3>${x.g} <small>— ${eur(sub(x))}</small></h3>
        <table><thead><tr><th>Account</th><th>As of</th><th class="num">Balance</th><th class="num">In EUR</th></tr></thead><tbody>${
          x.rows.map(r=>`<tr><td>${r.name}${r.manual?' <span class="chip">manual</span>':''}</td><td class="muted">${r.date}</td><td class="num">${r.val.toLocaleString('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:2})} ${r.cur}</td><td class="num ${r.eur!=null&&r.eur<0?'delta up':''}">${r.eur!=null?eur(r.eur):'—'}</td></tr>`).join('')
        }</tbody></table></div>`).join(''):'<div class="card"><div class="muted">No balances yet — run a sync.</div></div>';
      const note=document.getElementById('nwnote');
      if(note)note.innerHTML='Current balances as of the last sync — the period filter above does not apply here. '+(missing?'Some non-EUR balances not converted (no FX rate yet). ':'')+'A net-worth trend builds as history accumulates.';
    }
```

- [ ] **Step 4: Run checks**

```bash
grep -c 'id="nwgroups"' automation/dashboard_shell.html   # expect 1
grep -c 'nwbody' automation/dashboard_shell.html          # expect 0
```
Expected: PASS — `1` then `0` (grep exits 1 on the second; that's the pass condition).

- [ ] **Step 5: Commit**

```bash
git add automation/dashboard_shell.html && git commit -m "Net worth page: group subtotal tiles + per-group current-balance panels"
```

---

### Task 4: Regenerate demo, visual check, retake screenshots

**Files:**
- Modify: `demo/dashboard.html` (regenerated)
- Modify: `docs/screenshot.png` (retaken — sidebar brand changed)

**Interfaces:**
- Consumes: Tasks 1–3 complete. Playwright MCP tools; screenshots save relative to the session cwd (find with `mdfind` if missing).
- Produces: the committed demo + screenshot; also leave the 1440×1000 Overview PNG on disk for Task 7 (portfolio image).

- [ ] **Step 1: Regenerate the demo**

```bash
cd automation && python3 sample_data.py && python3 build_dashboard.py \
  && command cp -f "../Wealth-Management-Dashboard.html" ../demo/dashboard.html \
  && command rm -f wealth.db transactions.json "../Wealth-Management-Dashboard.html" && cd ..
```

- [ ] **Step 2: Check the demo content**

```bash
grep -ci "household" demo/dashboard.html; grep -c "Wealth Management" demo/dashboard.html; grep -c '"group"' demo/dashboard.html
```
Expected: `0` (grep exits 1), then ≥1, then ≥1.

- [ ] **Step 3: Visual check + screenshots (Playwright MCP)**

1. `cd demo && python3 -m http.server 8199` in background (file:// is blocked).
2. Navigate to `http://localhost:8199/dashboard.html`, resize to 1440×1000.
3. Click the "Net worth" nav item; screenshot; verify: KPI tiles (Net worth + Bank accounts + Investments), the Bank accounts + Investments tile values summing to the Net worth tile (±1€ rounding), two group panels below with account rows, and the "period filter does not apply" note. Fix and re-run if the layout is broken.
4. Navigate back to Overview; take the hero screenshot; save/move it to `docs/screenshot.png` (screenshot lands relative to server cwd — `mdfind -name` it if not found). Also copy it to `/Users/mattroshay/.claude/jobs/96dde9fc/tmp/wealth-dashboard-overview.png` for Task 7.
5. Kill the http.server.

- [ ] **Step 4: Commit**

```bash
git add demo/dashboard.html docs/screenshot.png && git commit -m "Regenerate demo and screenshot with new brand and balances view"
```

---

### Task 5: Push and open the draft PR

**Files:** none (git/gh only)

- [ ] **Step 1: Push**

```bash
git push -u origin feat/rebrand-balances
```

- [ ] **Step 2: Open draft PR stacked on PR #1**

```bash
gh pr create --draft --base feat/generalize-europe --title "Rebrand to Wealth Management Dashboard + grouped balances view" --body "$(cat <<'EOF'
Rebrands the app (title, sidebar, output filename `Wealth-Management-Dashboard.html`) and removes the word "household" everywhere. Redesigns the Net worth page: total + per-group subtotal tiles on top, grouped current-balance panels (Bank accounts / Investments / Other assets / Liabilities) below, with an explicit note that the period filter doesn't apply to balances.

Stacked on #1 — merge that first (GitHub will retarget this PR to main).

Note for local setups: the output filename changed, so re-point any Finder shortcut; the old `Household-Spending-Dashboard.html` is not deleted automatically.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Verify**

```bash
gh pr view --json state,isDraft,baseRefName
```
Expected: `OPEN`, `true`, `feat/generalize-europe`.

---

### Task 6: Apply the same code changes to the LIVE pipeline

**Files:**
- Modify: `/Users/mattroshay/Documents/Claude/Projects/Wealth Management/automation/build_dashboard.py`
- Modify: `/Users/mattroshay/Documents/Claude/Projects/Wealth Management/automation/dashboard_shell.html`
- (Optional, comment-only: `categorize.py`, `sample_data.py` — skip if they differ from the repo versions beyond the comment.)

**Interfaces:**
- Consumes: the finished repo versions from Tasks 1–3.
- CONSTRAINT: code files only. Never touch `config.json`, `wealth.db`, `assets.json`, logs, or generated dashboards in this folder. No git operations here.

- [ ] **Step 1: Diff live files against the pre-change repo versions**

```bash
cd "/Users/mattroshay/Documents/Claude/Projects/Wealth Management/wealth-dashboard/.claude/worktrees/rebrand-balances"
git show feat/generalize-europe:automation/build_dashboard.py | diff - "/Users/mattroshay/Documents/Claude/Projects/Wealth Management/automation/build_dashboard.py"
git show feat/generalize-europe:automation/dashboard_shell.html | diff - "/Users/mattroshay/Documents/Claude/Projects/Wealth Management/automation/dashboard_shell.html"
```
- If a diff is **empty**: the live file matches the sanitized repo baseline → safe to copy the new version over it (`command cp -f automation/<file> "/Users/mattroshay/Documents/Claude/Projects/Wealth Management/automation/<file>"`).
- If a diff is **non-empty**: do NOT copy. Apply the same Edit-tool changes from Tasks 1–3 to the live file by hand, preserving its local differences.

- [ ] **Step 2: Rebuild the live dashboard**

```bash
cd "/Users/mattroshay/Documents/Claude/Projects/Wealth Management/automation" && python3 build_dashboard.py
```
Expected: `Dashboard rebuilt: <N> transactions -> .../Wealth-Management-Dashboard.html`.

- [ ] **Step 3: Verify (without opening real data in chat)**

```bash
ls -la "/Users/mattroshay/Documents/Claude/Projects/Wealth Management/Wealth-Management-Dashboard.html" \
  && grep -c '"group"' "/Users/mattroshay/Documents/Claude/Projects/Wealth Management/Wealth-Management-Dashboard.html"
```
Expected: file exists (fresh timestamp), group count ≥ 1. Leave `Household-Spending-Dashboard.html` in place — tell Matt it's now stale and he can delete it + re-point any Finder shortcut.

---

### Task 7: Portfolio PR #16 — copy + image

**Files:**
- Modify: `/Users/mattroshay/code/roshaym/Freelance Developer Portfolio-2/.claude/worktrees/wealth-entry/src/locales/en.json` (wealthDashboard.description)
- Modify: `.../wealth-entry/src/locales/fr.json` (same key)
- Modify: `.../wealth-entry/public/images/projects/wealth-dashboard.png` (replace with Task 4's Overview PNG)

**Interfaces:**
- Consumes: Task 4's 1440×1000 Overview screenshot (new sidebar brand visible).
- Branch `feat/wealth-dashboard-entry` already exists with open PR #16 — just commit and push.

- [ ] **Step 1: Edit the copy**

`en.json`: `Local-first personal-finance automation for European households.` → `Local-first personal-finance automation built for Europe.`
`fr.json`: `Automatisation locale des finances pour les foyers européens.` → `Automatisation locale des finances personnelles, conçue pour l'Europe.`

- [ ] **Step 2: Replace the image**

```bash
command cp -f /Users/mattroshay/.claude/jobs/96dde9fc/tmp/wealth-dashboard-overview.png "/Users/mattroshay/code/roshaym/Freelance Developer Portfolio-2/.claude/worktrees/wealth-entry/public/images/projects/wealth-dashboard.png"
```

- [ ] **Step 3: Verify build + JSON**

```bash
cd "/Users/mattroshay/code/roshaym/Freelance Developer Portfolio-2/.claude/worktrees/wealth-entry" \
  && python3 -c "import json;json.load(open('src/locales/en.json'));json.load(open('src/locales/fr.json'));print('json OK')" \
  && npm run build
```
Expected: `json OK`, build succeeds.

- [ ] **Step 4: Commit and push**

```bash
git add src/locales/en.json src/locales/fr.json public/images/projects/wealth-dashboard.png \
  && git commit -m "Wealth Dashboard card: rebranded screenshot, drop 'households' wording" && git push
```

---

### Task 8: Memory + final report

- [ ] Update `/Users/mattroshay/.claude/projects/-Users-mattroshay-Documents-Claude/memory/wealth-dashboard-published.md`: add a bullet — rebrand + balances PR (number from Task 5) stacked on PR #1, new merge order **PR #1 → rebrand PR → flip public → portfolio PR #16**, live pipeline updated (old `Household-Spending-Dashboard.html` stale, Finder shortcut note).
- [ ] Final chat report: what shipped, PR link, live-dashboard note (new filename + stale old file), reminders for Matt.
