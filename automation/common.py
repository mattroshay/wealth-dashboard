import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise SystemExit("config.json not found. Copy config.example.json to config.json and fill it in.")
    with open(CONFIG_PATH) as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def load_private_key(cfg):
    path = os.path.expanduser(cfg["enable_banking"]["private_key_path"])
    with open(path) as f:
        return f.read()

def eb_client(cfg):
    from eb_client import EnableBanking
    return EnableBanking(cfg["enable_banking"]["app_id"], load_private_key(cfg))
