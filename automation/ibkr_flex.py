"""IBKR Flex Web Service client (read-only). Two-step: SendRequest -> GetStatement.
The Flex token is READ-ONLY: it can only fetch reports, never trade or move money.
Set up a Flex Query in Client Portal (Performance & Reports > Flex Queries) including
NAV (Change in NAV / Equity Summary) and Cash Report, and a Flex Web Service token."""
import time, requests
import xml.etree.ElementTree as ET

BASE = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
UA = {"User-Agent": "WealthSync/1.0 (Python)"}

def fetch_report(token, query_id, version=3, max_wait=90):
    # 1) SendRequest -> ReferenceCode
    r = requests.get(f"{BASE}/SendRequest", params={"t": token, "q": query_id, "v": version},
                     headers=UA, timeout=60)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    if root.findtext("Status") != "Success":
        raise RuntimeError("Flex SendRequest failed: " + (root.findtext("ErrorMessage") or r.text[:200]))
    ref = root.findtext("ReferenceCode")
    # 2) GetStatement (poll)
    waited = 0
    while True:
        s = requests.get(f"{BASE}/GetStatement", params={"t": token, "q": ref, "v": version},
                         headers=UA, timeout=60)
        s.raise_for_status()
        if s.text.lstrip().startswith("<FlexQueryResponse"):
            return s.text  # the statement XML
        # not ready yet -> Status/ErrorCode 1019 = generating
        er = ET.fromstring(s.text)
        if er.findtext("ErrorCode") not in ("1019", None) and er.findtext("Status") == "Fail":
            raise RuntimeError("Flex GetStatement failed: " + (er.findtext("ErrorMessage") or s.text[:200]))
        if waited >= max_wait:
            raise TimeoutError("Flex statement not ready after %ss" % max_wait)
        time.sleep(5); waited += 5

def parse_nav_and_cash(xml_text):
    """Extract per-account (account_id, date, NAV, cash, currency). NAV comes from ChangeInNAV
    (endingValue) and the date from the parent FlexStatement (toDate). Robust to layout variants."""
    root = ET.fromstring(xml_text)
    out = []
    for st in root.iter("FlexStatement"):
        acct = st.get("accountId", "")
        date = st.get("toDate") or st.get("fromDate") or ""
        nav = None; ccy = "USD"; cash = None
        cin = st.find("ChangeInNAV")
        if cin is not None:
            nav = _f(cin.get("endingValue")); ccy = cin.get("currency") or ccy
        cr = st.find("CashReport")
        if cr is not None:
            for c in cr.findall("CashReportCurrency"):
                if c.get("currency") == "BASE_SUMMARY":
                    cash = _f(c.get("endingCash")); break
        if nav is not None:
            out.append({"account_id": acct, "date": date, "nav": nav, "cash": cash, "currency": ccy})
    if not out:  # legacy fallback
        for es in root.iter("EquitySummaryInBase"):
            a = es.attrib
            out.append({"account_id": a.get("accountId", ""), "date": a.get("reportDate", ""),
                        "nav": _f(a.get("total")), "cash": _f(a.get("cash")), "currency": a.get("currency", "BASE")})
    return out

def parse_fx(xml_text, from_ccy="EUR", to_ccy="USD"):
    """Return the from->to conversion rate (e.g. USD per 1 EUR) from the report, or None."""
    root = ET.fromstring(xml_text)
    for cr in root.iter("ConversionRate"):
        if cr.get("fromCurrency") == from_ccy and cr.get("toCurrency") == to_ccy:
            return _f(cr.get("rate"))
    return None

def _f(v):
    try: return float(v)
    except (TypeError, ValueError): return None
