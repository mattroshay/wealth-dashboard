"""Interactive: authorize each bank once (and again ~every 180 days when consent expires).
Captures the OAuth code automatically via a local loopback listener (no copy-paste, and it
survives banks that drop you on a homepage that strips the code).

Usage:
  python3 link_banks.py --list          # show exact ASPSP names for FR
  python3 link_banks.py                  # link every bank in config without an active session
  python3 link_banks.py --bank "BNP"     # (re)link a single bank (substring match)
"""
import sys, uuid, urllib.parse, datetime, webbrowser, http.server, socket
import db, common

def find_uid(a):
    if isinstance(a, str): return a
    for k in ("uid", "account_id", "id"):
        if a.get(k): return a[k]
    return None

def session_account_uids(eb, sess, sid):
    """Account uids of a consent. Some banks attach accounts only after session creation,
    so when the create-session response has none, re-query the session before concluding
    the consent covers zero accounts."""
    uids = [u for u in (find_uid(a) for a in sess.get("accounts") or []) if u]
    if not uids and sid:
        try:
            fresh = eb.get_session(sid)
            uids = [u for u in (find_uid(a) for a in fresh.get("accounts") or []) if u]
        except Exception:
            pass
    return uids

def ensure_cert():
    """Generate (once) a self-signed cert for localhost so the loopback listener can serve HTTPS."""
    import os
    HERE = os.path.dirname(os.path.abspath(__file__))
    cert, key = os.path.join(HERE, ".localhost_cert.pem"), os.path.join(HERE, ".localhost_key.pem")
    if os.path.exists(cert) and os.path.exists(key):
        return cert, key
    import datetime as dt, ipaddress
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nm = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    c = (x509.CertificateBuilder().subject_name(nm).issuer_name(nm)
         .public_key(k.public_key()).serial_number(x509.random_serial_number())
         .not_valid_before(dt.datetime.utcnow() - dt.timedelta(days=1))
         .not_valid_after(dt.datetime.utcnow() + dt.timedelta(days=3650))
         .add_extension(x509.SubjectAlternativeName(
             [x509.DNSName("localhost"), x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]), critical=False)
         .sign(k, hashes.SHA256()))
    with open(key, "wb") as f:
        f.write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    with open(cert, "wb") as f:
        f.write(c.public_bytes(serialization.Encoding.PEM))
    return cert, key

def capture_code(redirect_url, timeout=300):
    """One-shot local (HTTPS) server on the host/port in redirect_url; returns the OAuth code."""
    u = urllib.parse.urlparse(redirect_url)
    host, port = u.hostname or "localhost", u.port or 8765
    got = {}
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            p = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got["code"] = p.get("code", [None])[0]
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            msg = "✅ Account linked — return to your terminal, you can close this tab." if got.get("code") \
                  else "No code received — return to the terminal."
            self.wfile.write(f"<html><body style='font-family:sans-serif;background:#0f1115;color:#e7eaf0;padding:60px;text-align:center'><h2>{msg}</h2></body></html>".encode())
        def log_message(self, *a): pass
    # Bind dual-stack (::) so macOS 'localhost' (which resolves to IPv6 ::1) reaches us,
    # as well as IPv4 127.0.0.1. Fixes Safari "can't connect to localhost".
    class DualStack(http.server.HTTPServer):
        address_family = socket.AF_INET6
        def server_bind(self):
            try:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except OSError:
                pass
            http.server.HTTPServer.server_bind(self)
    try:
        srv = DualStack(("::", port), H)
    except OSError:
        srv = http.server.HTTPServer(("127.0.0.1", port), H)
    srv.timeout = timeout
    if u.scheme == "https":
        import ssl
        cert, key = ensure_cert()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    print(f"   …listening on {redirect_url} for the redirect (up to {timeout//60} min).")
    print("   NOTE: your browser will warn about the self-signed localhost cert — click "
          "'Advanced' → 'Proceed to localhost'. That's expected and safe (it's your own Mac).")
    import time as _t
    srv.timeout = 5
    deadline = _t.time() + timeout
    try:
        while _t.time() < deadline and not got.get("code"):
            srv.handle_request()   # returns after one request, or after 5s idle; loop until we get a code
    except Exception as e:
        print("   (listener error:", e, ")")
    finally:
        srv.server_close()
    return got.get("code")

def link_bank(eb, con, cfg, bank):
    redirect_url = cfg["enable_banking"]["redirect_url"]
    loopback = urllib.parse.urlparse(redirect_url).hostname in ("localhost", "127.0.0.1")
    state = uuid.uuid4().hex
    print(f"\n== Linking {bank['name']} ({bank['country']}) ==")
    res = eb.start_authorization(bank["name"], redirect_url, state, country=bank["country"])
    url = res.get("url")
    print("1) Opening your bank's authorization page in the browser…")
    print("   (if it doesn't open, paste this URL manually:)\n   " + url + "\n")
    try: webbrowser.open(url)
    except Exception: pass
    print("2) Log in and approve access on your phone (SCA).")
    if loopback:
        code = capture_code(redirect_url)
        if not code:
            pasted = input("   Listener didn't catch it. Paste the FULL localhost URL from the address bar (or the code):\n   ").strip()
            code = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query).get("code", [pasted])[0] if "code=" in pasted else pasted
    else:
        pasted = input("   Paste the FULL redirected URL (or just the code):\n   ").strip()
        code = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query).get("code", [pasted])[0] if "code=" in pasted else pasted
    if not code:
        print("   ✗ No code received (timed out or bank didn't redirect). Try re-running for this bank.")
        return
    sess = eb.create_session(code)
    sid = sess.get("session_id") or sess.get("sessionId")
    uids = session_account_uids(eb, sess, sid)
    if not uids:
        print("   ⚠️  Authorization succeeded but the bank shared ZERO accounts — nothing will sync!")
        print("      Re-run:  python3 link_banks.py --bank \"" + bank["name"] + "\"")
        print("      and make sure you SELECT/TICK your account(s) on the bank's consent page before approving.")
    for uid in uids:
        name = bank["name"]; iban = curr = None
        try:
            d = eb.account_details(uid)
            name = d.get("name") or d.get("product") or bank["name"]
            ai = d.get("account_id")
            iban = ai.get("iban") if isinstance(ai, dict) else d.get("iban")
            curr = d.get("currency")
        except Exception:
            pass
        db.upsert_account(con, uid, "EnableBanking", name, iban, curr or "EUR", "bank")
        print(f"   linked account: {name}  [{uid[:8]}…]")
    # Enable Banking issues NEW account uids on each consent, so purge this bank's previous
    # account ids (and their data) that aren't in the fresh set — prevents duplicate accounts.
    old_uids = set(u for s in cfg["enable_banking"]["sessions"] if s.get("bank") == bank["name"]
                   for u in s.get("accounts", []))
    for su in (old_uids - set(uids)):
        con.execute("DELETE FROM transactions WHERE account_uid=?", (su,))
        con.execute("DELETE FROM balances WHERE account_uid=?", (su,))
        con.execute("DELETE FROM accounts WHERE account_uid=?", (su,))
        print(f"   cleaned old account {su[:8]}… (re-issued id)")
    cfg["enable_banking"]["sessions"] = [s for s in cfg["enable_banking"]["sessions"] if s.get("bank") != bank["name"]]
    cfg["enable_banking"]["sessions"].append({"bank": bank["name"], "session_id": sid,
        "accounts": uids, "linked_at": datetime.date.today().isoformat()})
    con.commit(); common.save_config(cfg)
    print(f"   ✓ session saved ({len(uids)} account(s)).")

def main():
    cfg = common.load_config(); eb = common.eb_client(cfg); con = db.connect()
    if "--list" in sys.argv:
        print("Available FR banks (ASPSP names) — match these in config.banks:")
        for a in sorted(eb.aspsps("FR"), key=lambda x: x.get("name", "")):
            print(f"  - {a.get('name')}  ({a.get('country')})")
        return
    only = sys.argv[sys.argv.index("--bank") + 1].lower() if "--bank" in sys.argv else None
    linked = {s["bank"] for s in cfg["enable_banking"]["sessions"]}
    for bank in cfg["enable_banking"]["banks"]:
        if only and only not in bank["name"].lower():
            continue
        if not only and bank["name"] in linked:
            print(f"(skip {bank['name']} — already linked; use --bank to re-link)")
            continue
        link_bank(eb, con, cfg, bank)
    print("\nDone. Run:  python3 sync.py")

if __name__ == "__main__":
    main()
