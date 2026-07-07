"""Minimal Enable Banking API client (AIS / account information).
Auth = RS256 JWT signed with your application's private key (.pem). Docs: https://enablebanking.com/docs/api/
Free 'Restricted Production' tier lets you link your OWN accounts."""
import time, datetime, requests, jwt  # PyJWT

BASE = "https://api.enablebanking.com"

class EnableBanking:
    def __init__(self, app_id, private_key_pem):
        self.app_id = app_id
        self.key = private_key_pem  # PEM string

    def _jwt(self):
        now = int(time.time())
        payload = {"iss": "enablebanking.com", "aud": "api.enablebanking.com",
                   "iat": now, "exp": now + 3600}
        return jwt.encode(payload, self.key, algorithm="RS256",
                          headers={"kid": self.app_id})

    def _headers(self):
        return {"Authorization": "Bearer " + self._jwt(), "Content-Type": "application/json"}

    def _get(self, path, params=None):
        r = requests.get(BASE + path, headers=self._headers(), params=params, timeout=60)
        r.raise_for_status()
        return r.json()

    def _post(self, path, body):
        r = requests.post(BASE + path, headers=self._headers(), json=body, timeout=60)
        r.raise_for_status()
        return r.json()

    # --- discovery ---
    def application(self):
        return self._get("/application")

    def aspsps(self, country="FR"):
        return self._get("/aspsps", params={"country": country}).get("aspsps", [])

    # --- authorization (run once per bank, then again ~every 180 days) ---
    def start_authorization(self, aspsp_name, redirect_url, state, country="FR",
                            psu_type="personal", valid_days=180):
        valid_until = (datetime.datetime.now(datetime.timezone.utc)
                       + datetime.timedelta(days=valid_days)).replace(microsecond=0).isoformat()
        body = {"access": {"valid_until": valid_until},
                "aspsp": {"name": aspsp_name, "country": country},
                "state": state, "redirect_url": redirect_url, "psu_type": psu_type}
        return self._post("/auth", body)  # -> {"url": "...", "authorization_id": "..."}

    def create_session(self, code):
        return self._post("/sessions", {"code": code})  # -> {session_id, accounts:[uid...], ...}

    def get_session(self, session_id):
        return self._get("/sessions/" + session_id)

    # --- data ---
    def account_details(self, account_uid):
        return self._get(f"/accounts/{account_uid}/details")

    def balances(self, account_uid):
        return self._get(f"/accounts/{account_uid}/balances").get("balances", [])

    def transactions(self, account_uid, date_from, date_to=None):
        """Yields all transactions between date_from and date_to (YYYY-MM-DD).
        Enable Banking caps each response at 100 and its continuation_key is unreliable,
        so we page by date windows and recursively split any window that hits the cap."""
        start = datetime.date.fromisoformat(date_from[:10])
        end = datetime.date.fromisoformat((date_to or datetime.date.today().isoformat())[:10])
        yield from self._tx_window(account_uid, start, end)

    def _tx_window(self, uid, start, end, depth=0):
        params = {"date_from": start.isoformat(), "date_to": end.isoformat()}
        data = self._get(f"/accounts/{uid}/transactions", params=params)
        txs = data.get("transactions", [])
        if len(txs) >= 100 and (end - start).days > 1 and depth < 14:
            # window truncated -> split in half and recurse (captures everything)
            half = (end - start).days // 2
            mid = start + datetime.timedelta(days=half)
            yield from self._tx_window(uid, start, mid, depth + 1)
            yield from self._tx_window(uid, mid + datetime.timedelta(days=1), end, depth + 1)
        else:
            for t in txs:
                yield t
