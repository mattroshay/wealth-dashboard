"""Rule-based merchant extraction + categorisation for FR bank transactions.
Same ruleset used to build the Phase-0 dashboard. Spend categories + income classification.
Later this can be swapped for an AI categoriser; the interface stays merchant()/categorize()/classify_credit()."""
import re

def is_transfer(label):
    u = label.upper()
    return bool(re.search(r"\bVIR\b|VIREMENT", u)) or u.startswith("VIR ")

def merchant(label):
    s = label.upper()
    s = re.sub(r"^CARTE\s+\d{2}/\d{2}\s+", "", s)
    s = re.sub(r"^PAIEMENT CB ", "", s); s = re.sub(r"^PRLV ", "", s); s = re.sub(r"^PAIEMENT ", "", s)
    s = re.sub(r"^F COTISATION", "COTISATION", s); s = re.sub(r"^F COMM.*", "BANK COMMISSION", s)
    s = re.sub(r"^ECH PRET.*", "HOME MORTGAGE (ECH PRET)", s)
    s = re.sub(r"^CHQ .*", "CHEQUE", s); s = re.sub(r"^RET DAB.*", "CASH WITHDRAWAL (DAB)", s)
    s = re.sub(r" DU \d.*", "", s); s = re.sub(r"\(.*?\)", "", s); s = re.sub(r"\*.*", "", s); s = re.sub(r"- CARTE.*", "", s)
    s = re.sub(r"\s+\d{2,}.*", "", s); s = re.sub(r"\d{4,}.*", "", s); s = re.sub(r"\s+", " ", s).strip()
    return s[:30].title() if s else "Unknown"

RULES = [
 ("Loans & mortgage", ["ECH PRET","HOME MORTGAGE","ECHEANCE PRET","VOLKSWAGEN BA","PRET "]),
 ("Taxes & social", ["URSSAF","DIRECTION GEN","DGFIP","IMPOT","TRESOR","FINANCES PUB","GREENBACK","EXPAT"]),
 ("Childcare", ["PAJEMPLOI","PAJEMP","CRECHE","NOUNOU"]),
 ("Utilities", ["EDF","REGIE EAU","ENGIE","GAZ","EAU BOR","TOTALENERGIES"]),
 ("Telecom & internet", ["FREE MOBILE","ORANGE","SFR","BOUYGUES","SOSH","FREE HAUT"]),
 ("Insurance & health", ["AXA","APIVIA","SURAVENIR","MAIF","MATMUT","MUTUELLE","PHARMACIE","PHIE","PHARM","MEDECIN","DOCTEUR"," DR ","LABO","DENTAIRE","OPTIC","SELARL","CENTRE MEDICAL","ASSUR","AREAS BORDEAUX","CARDIF","BPSIS","GENERALI"]),
 ("Fuel, transport & tolls", ["SHELL","TOTAL","ESSO","GASOJE","ESCOTA","AUTOROUT","VINCI","SANEF","SUD AU","EASYPARK","EASYPA","PARKING","APRR","STATION","DYNEFF","PETROLEC","SNCF","NAVIGO","TBM","KEOLIS","INDIGO","AEROPOT","CITIBIKE","BP 3000","BLABLA","UBER"]),
 ("Groceries", ["LECLERC","E.LECL","CARREFOUR","INTERMARCHE","AUCHAN","LIDL","MONOPRIX","CASINO","GRAND FRAIS","BIOCOOP","SUPER U","FRANPRIX","PICARD","MARCHE","GDC ","VIVAL","EROSKI","SUPER CALA"]),
 ("Restaurants & dining", ["RESTAURANT","BRASSERIE","BOULANGERIE","MARIE BLACHERE","MCDO","BURGER","PIZZ","SUSHI","CHOCOL","CAFE","TRAITEUR","PAUL","LES COMMIS","LA FERME","ARTESIA","DBF ","TOQUE CUIVRE","BRIOCHE","ERIC KAYSER","PAIN SAS","FOURNIL","SUMUP","LE BISTROT","BISTRO","RVBM","KAPPUCCINO","COTE SUSHI","FRENCH COFFEE","GOUTTE DE CAFE","MONUMENT CAFE","CABANE"]),
 ("Amazon", ["AMAZON","AMZ","AMZN"]),
 ("Software & AI tools", ["OPENAI","ANTHROPIC","CLAUDE","GITHUB","NOTION","MIDJOURNEY","ADOBE","MENTORCRUISE","PADDLE","DUST","MICROSOFT","BITDEFENDER","INSTA360","CURSOR","VERCEL","HEROKU","NAMECHEAP","NAME-CHEAP","CANVA","LINKEDIN","MYVARIATION"]),
 ("Streaming & media", ["NETFLIX","SPOTIFY","DISNEY","YOUTUBE","APPLE","ICLOUD","CANAL","DEEZER","PRIME VIDEO","AUDIBLE","BOXINE"]),
 ("Education", ["CODECADEMY","UDEMY","COURSERA","CPF","SKILLSHARE","DATACAMP"]),
 ("Shopping & retail", ["FNAC","DARTY","DECATHLON","ZARA","UNIQLO","H&M","IKEA","LEROY","ZALANDO","SHEIN","VINTED","YETI","ON SPORTSWEAR","NIKE","ADIDAS","INTERFLORA","CKOINTERFLORA","SEPHORA","LOCCITANE","L'OCCITANE","OCCITANE","JOTT","GRAIN DE MALICE","MAISON LASCO","TECHTRONIC","OKAIDI","MANGO","KIABI","ETAM","SEZANE","VERTBAUDET","ACTION","BRICOMARCHE","OXYBUL","KUJTEN","IMAJEANS","LOOKIERO","BENUTA","DOREL","PLUME DES","ENVIS","PPG","INTEX","PETIT BATEAU","SP TIPTOQUE"]),
 ("Travel & holidays", ["AIR FRANCE","EASYJET","RYANAIR","FLIXBUS","HOTEL","AIRBNB","IBEROSTAR","VILLA","GAROUPE","MARGA","LACANAU","BOOKING","CARS ON BO","RADISSON","INTUROTEL","EUROPCAR","CAMPING","GOLFMEDOC","TEDEY","SUNRISE","REGIONDO","BASSINS DES LUMI","FOND. CULTURE","MONCHATEAU"]),
 ("Home & garden", ["WATERAIR","PISCINE","CASTORAMA","BRICO","JARDIN","TRUFFAUT","MOBILIER","MAISON AUZENE","SOSTRENE"]),
 ("Cash", ["RET DAB","CASH WITHDRAWAL","RETRAIT","DAB "]),
 ("Bank fees", ["COTISATION","EUROCOMPTE","FRAIS","COMMISSION","AGIOS","BANK COMMISSION","TENUE DE COMPTE"]),
 ("Kids, sport & culture", ["ECOLE","SCOLAIRE","CANTINE","STADE","SPORT","CLUB","ULTI","CULTURE","SKISET","VALBERG","OURS BLANC"]),
]
FIXED = {"Loans & mortgage","Taxes & social","Childcare","Utilities","Insurance & health","Telecom & internet","Bank fees"}

def categorize(label):
    u = label.upper()
    for c, kws in RULES:
        if any(k in u for k in kws):
            return c
    return "Other"

# ---- income (credits) ----
# Generic internal-transfer markers. Add your own patterns (e.g. family
# surnames appearing in transfer labels) via "categorize": {"internal": [...]} in config.json.
INTERNAL = ["DE COMPTE PERSO","DE COMPTE JOINT","DE LIVRET","VRST","PROPRE COM"]
try:
    import json as _json, os as _os
    _cfg = _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "config.json")))
    INTERNAL += [s.upper() for s in _cfg.get("categorize", {}).get("internal", [])]
    RECURRING_INCOME = [s.upper() for s in _cfg.get("categorize", {}).get("recurring_income", [])]
except Exception:
    RECURRING_INCOME = []
REFUND = ["ANN CARTE","REMBOURSEMENT","ANNULATION"]

def classify_credit(label):
    """Returns (kind, category). kind in {'income','transfer','refund'}."""
    u = label.upper()
    if any(k in u for k in RECURRING_INCOME): return ("income", "Recurring receipt")
    if any(k in u for k in INTERNAL): return ("transfer", None)
    if any(k in u for k in REFUND): return ("refund", None)
    if "CARTE " in u and not u.startswith("VIR"): return ("refund", None)
    if any(k in u for k in ["FRANCE TRAVAIL","CAF ","CAF DE"]): return ("income", "Benefits & allowances")
    if any(k in u for k in ["C.P.A.M","CPAM","MACIF","APIVIA","SIACI","INTER PARTNER"]): return ("income", "Health reimbursements")
    if any(k in u for k in ["DGFIP","URSSAF","UNION POUR LE RECOUVREMENT","FINANCES PUBLIQUES"]): return ("income", "Tax & social refunds")
    return ("income", "Professional / other income")

def classify(label, amount):
    """Unified: returns (kind, category, merchant). kind: 's' spend | 'i' income | 't' transfer (excluded)."""
    m = merchant(label)
    if amount < 0:
        if is_transfer(label):
            return ("t", None, m)
        return ("s", categorize(label), m)
    else:
        k, cat = classify_credit(label)
        if k == "income":
            return ("i", cat, m)
        return ("t", None, m)  # transfers & refunds excluded from both spend and income
