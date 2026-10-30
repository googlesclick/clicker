# license_client.py — клиентская проверка лицензии
import uuid, platform, hashlib
import urllib.request
import urllib.error
import json

# ================== НАСТРОЙКА (ЗАМЕНИТЕ!) ==================
SERVER_URL = "https://clickerads.pythonanywhere.com"   # <-- адрес вашего сервера
# ==========================================================

LICENSE_FILE = "license.dat"

def get_hwid():
    """Уникальный отпечаток ПК."""
    raw = f"{uuid.getnode()}-{platform.machine()}-{platform.processor()}"
    return hashlib.sha256(raw.encode()).hexdigest()

def save_license(key):
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        f.write(key)

def load_license():
    try:
        with open(LICENSE_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def _post(path, payload):
    req = urllib.request.Request(
        f"{SERVER_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "msg": f"Ошибка сервера ({e.code})"}
    except Exception:
        return {"ok": False, "msg": "Сервер недоступен, проверьте интернет"}

def verify(key):
    """Активация ключа (первый запуск привязывает к ПК)."""
    return _post("/activate", {"key": key, "hwid": get_hwid()})

def recheck(key):
    """Быстрая проверка во время работы."""
    return _post("/check", {"key": key, "hwid": get_hwid()})