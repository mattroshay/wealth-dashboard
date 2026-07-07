"""Weekly wealth digest: last-7-days spending vs prior week, top categories, biggest purchases,
NEW recurring merchants (possible subscriptions), spending spikes, duplicate charges, and net worth.
Writes weekly-digest.html next to the dashboard and fires a macOS notification.
Run weekly (a launchd job does this Saturdays):  python3 digest.py"""
import os, json, datetime, subprocess
import db

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "weekly-digest.html")

def eur(n):
    return "€" + format(int(round(n)), ",d").replace(",", " ")

def main():
    con = db.connect()
    today = datetime.date.today()
    d7  = (today - datetime.timedelta(days=7)).isoformat()
    d14 = (today - datetime.timedelta(days=14)).isoformat()
    d35 = (today - datetime.timedelta(days=35)).isoformat()
    d90 = (today - datetime.timedelta(days=90)).isoformat()
    t = today.isoformat()

    def spend(a, b=None):
        q = "SELECT COALESCE(SUM(-amount),0) s, COUNT(*) n FROM transactions WHERE kind='s' AND booking_date>=?"
        p = [a]
        if b: q += " AND booking_date<?"; p.append(b)
        return con.execute(q, p).fetchone()

    this_wk = spend(d7); prev_wk = spend(d14, d7)
    tw, pw = this_wk["s"], prev_wk["s"]
    chg = round(100 * (tw - pw) / pw) if pw else 0

    cats = con.execute("""SELECT category, SUM(-amount) s, COUNT(*) n FROM transactions
        WHERE kind='s' AND booking_date>=? GROUP BY category ORDER BY s DESC LIMIT 8""", (d7,)).fetchall()
    big = con.execute("""SELECT booking_date, merchant, -amount a, category FROM transactions
        WHERE kind='s' AND booking_date>=? ORDER BY amount ASC LIMIT 6""", (d7,)).fetchall()

    # NEW recurring merchants: appear >=2x in last 35d but never before
    newsubs = []
    for m in con.execute("""SELECT merchant, COUNT(*) c, SUM(-amount) s FROM transactions
            WHERE kind='s' AND booking_date>=? GROUP BY merchant HAVING c>=2""", (d35,)):
        before = con.execute("SELECT COUNT(*) c FROM transactions WHERE kind='s' AND merchant=? AND booking_date<?",
                             (m["merchant"], d35)).fetchone()["c"]
        if before == 0:
            newsubs.append(m)

    # category spikes: this week > 2.5x its avg weekly spend over prior 90d
    spikes = []
    for c in cats:
        hist = con.execute("""SELECT COALESCE(SUM(-amount),0) s FROM transactions
            WHERE kind='s' AND category=? AND booking_date>=? AND booking_date<?""", (c["category"], d90, d7)).fetchone()["s"]
        avgwk = hist / (90 / 7)
        if avgwk > 15 and c["s"] > 2.5 * avgwk:
            spikes.append((c["category"], c["s"], avgwk))

    # duplicate charges (same merchant+amount) in last 14d
    dups = con.execute("""SELECT merchant, -amount a, COUNT(*) c FROM transactions
        WHERE kind='s' AND booking_date>=? GROUP BY merchant, amount HAVING c>=2 ORDER BY a DESC LIMIT 5""", (d14,)).fetchall()

    # net worth
    fx = db.get_meta(con, "eur_usd"); fx = float(fx) if fx else None
    nw = 0.0
    for r in con.execute("""SELECT bal_close,currency FROM balances b WHERE source!='reconstructed'
        AND snapshot_date=(SELECT MAX(snapshot_date) FROM balances b2 WHERE b2.account_uid=b.account_uid AND source!='reconstructed')"""):
        v = r["bal_close"]
        if v is None: continue
        if (r["currency"] or "EUR") != "EUR": v = v / fx if fx else 0
        nw += v
    ap = os.path.join(HERE, "assets.json")
    if os.path.exists(ap):
        man = json.load(open(ap))
        nw += sum(float(a.get("value") or 0) for a in man.get("assets", []))
        nw -= sum(float(l.get("value") or 0) for l in man.get("liabilities", []))

    # ---- HTML ----
    arrow = "▲" if chg >= 0 else "▼"
    col = "#e07a5f" if chg >= 0 else "#3ea776"
    def rows(items, fn): return "".join(fn(x) for x in items)
    alerts_html = ""
    for c, cur, avg in spikes:
        alerts_html += f'<div class="al up"><b>{c}</b> spiked to <b>{eur(cur)}</b> this week — {cur/avg:.1f}× your usual {eur(avg)}.</div>'
    for m in newsubs:
        alerts_html += f'<div class="al new">New recurring merchant <b>{m["merchant"]}</b> — {m["c"]} charges recently ({eur(m["s"])}), none before. Possible new subscription.</div>'
    for dp in dups:
        alerts_html += f'<div class="al dup">Possible duplicate: <b>{dp["merchant"]}</b> {eur(dp["a"])} charged {dp["c"]}× in 14 days.</div>'
    if not alerts_html:
        alerts_html = '<div class="muted">No alerts this week.</div>'

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Weekly digest</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f1115;color:#e7eaf0;max-width:720px;margin:0 auto;padding:32px 22px}}
h1{{font-size:20px;margin:0 0 2px}} .sub{{color:#9aa3b2;font-size:12.5px;margin-bottom:20px}}
.card{{background:#181b22;border:1px solid #2a2f3a;border-radius:14px;padding:16px 18px;margin-bottom:14px}}
.kpi{{font-size:26px;font-weight:680}} h3{{font-size:14px;margin:0 0 10px}}
table{{width:100%;border-collapse:collapse;font-size:13px}} td{{padding:5px 4px;border-bottom:1px solid #2a2f3a}}
.num{{text-align:right;font-variant-numeric:tabular-nums}} .muted{{color:#9aa3b2;font-size:13px}}
.al{{font-size:13px;padding:8px 10px;border-radius:8px;background:#1f232c;margin-bottom:7px;border-left:3px solid #e0a53e}}
.al.up{{border-color:#e07a5f}} .al.new{{border-color:#e0a53e}} .al.dup{{border-color:#4a90d9}} .al b{{color:#fff}}</style></head><body>
<h1>Weekly wealth digest</h1>
<div class="sub">{(today - datetime.timedelta(days=7)).strftime('%d %b')} – {today.strftime('%d %b %Y')}</div>
<div class="card"><div class="muted">Spent last 7 days</div><div class="kpi">{eur(tw)} <span style="font-size:13px;color:{col}">{arrow} {abs(chg)}% vs prior week</span></div>
<div class="muted" style="margin-top:4px">{this_wk['n']} transactions · net worth ≈ <b style="color:#e7eaf0">{eur(nw)}</b></div></div>
<div class="card"><h3>⚡ Alerts</h3>{alerts_html}</div>
<div class="card"><h3>Top categories this week</h3><table>{rows(cats, lambda c: f'<tr><td>{c["category"]}</td><td class="num">{eur(c["s"])}</td></tr>')}</table></div>
<div class="card"><h3>Biggest purchases</h3><table>{rows(big, lambda b: f'<tr><td>{b["booking_date"]}</td><td>{b["merchant"]}</td><td class="num">{eur(b["a"])}</td></tr>')}</table></div>
<div class="sub">Generated {datetime.datetime.now().strftime('%d %b %Y %H:%M')} · open the dashboard for full detail.</div>
</body></html>"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)

    # macOS notification (best effort)
    n_alerts = len(spikes) + len(newsubs) + len(dups)
    msg = f"{eur(tw)} spent ({arrow}{abs(chg)}% wk) · {len(newsubs)} new subs · {n_alerts} alerts"
    try:
        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Weekly wealth digest"'], timeout=10)
    except Exception:
        pass
    db.log(con, "digest", "ok", msg); con.commit()
    print("Digest written:", os.path.abspath(OUT)); print(" ", msg)

if __name__ == "__main__":
    main()
