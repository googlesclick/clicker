# gui.py — Google Ads Clicker PRO
# Лицензирование + работа через браузер, установленный на ПК
import subprocess, sys, os, threading, queue, random, time
import tkinter as tk
from tkinter import scrolledtext, filedialog
import urllib.request

# ============================================================
#  ПОИСК / УСТАНОВКА БРАУЗЕРА
# ============================================================

def find_browser():
    """Ищет установленный браузер. Возвращает (channel, имя)."""
    candidates = [
        ("chrome",  "Google Chrome"),
        ("msedge",  "Microsoft Edge"),
        ("firefox", "Mozilla Firefox"),
    ]
    try:
        from playwright.sync_api import sync_playwright
        for channel, name in candidates:
            try:
                with sync_playwright() as p:
                    p.chromium.launch(channel=channel, headless=True).close()
                return channel, name
            except Exception:
                continue
    except Exception:
        pass
    return None, None


def install_chrome():
    """Тихая установка Chrome с официального сайта Google."""
    if not sys.platform.startswith("win"):
        return None, None
    try:
        installer_url = "https://dl.google.com/chrome/install/latest/chrome_installer.exe"
        installer_path = os.path.join(os.environ.get("TEMP", "."), "chrome_installer.exe")
        urllib.request.urlretrieve(installer_url, installer_path)
        subprocess.run(["powershell", "-Command",
                        f"Start-Process '{installer_path}' -ArgumentList '/silent','/install' -Wait"],
                       check=True)
        return "chrome", "Google Chrome"
    except Exception:
        return None, None


BROWSER_CHANNEL, BROWSER_NAME = find_browser()

if BROWSER_CHANNEL is None:
    BROWSER_CHANNEL, BROWSER_NAME = install_chrome()

from playwright.sync_api import sync_playwright

# ============================================================
#  КОНСТАНТЫ
# ============================================================

UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Version/17.5 Mobile Safari/604.1",
]
STEALTH = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"

# ============================================================
#  ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ============================================================

class ClickerApp:
    def __init__(self, root):
        self.root = root
        root.title("Google Ads Clicker PRO")
        root.geometry("650x540")

        frm = tk.Frame(root)
        frm.pack(fill="x", padx=10, pady=5)

        tk.Label(frm, text="Домен конкурента:").grid(row=0, column=0, sticky="w")
        self.domain = tk.Entry(frm, width=45)
        self.domain.grid(row=0, column=1, pady=2)

        tk.Label(frm, text="Кол-во кликов:").grid(row=1, column=0, sticky="w")
        self.clicks = tk.Spinbox(frm, from_=1, to=1000, width=8)
        self.clicks.delete(0, "end")
        self.clicks.insert(0, "20")
        self.clicks.grid(row=1, column=1, sticky="w", pady=2)

        tk.Button(frm, text="Ключи (keys.txt)...", command=self.load_keys).grid(row=2, column=0, pady=4)
        tk.Button(frm, text="Прокси (proxies.txt)...", command=self.load_proxies).grid(row=2, column=1, sticky="w")

        self.start_btn = tk.Button(root, text="▶ ЗАПУСТИТЬ", bg="#4CAF50", fg="white",
                                   command=self.start, font=("Arial", 11, "bold"))
        self.start_btn.pack(fill="x", padx=10, pady=5)

        tk.Label(root, text="Лог:").pack(anchor="w", padx=10)
        self.log_box = scrolledtext.ScrolledText(root, height=18)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=5)

        self.q = queue.Queue()
        self.keys, self.proxies = [], []
        self.running = False

        # Информация о браузере
        if BROWSER_NAME:
            self.log(f"🌐 Браузер: {BROWSER_NAME}")
        else:
            self.log("⚠ Браузер не найден — будет использован встроенный Chromium")

        self.periodic_check()

    # ---------------- Лицензия ----------------
    def periodic_check(self):
        from license_client import recheck, load_license
        key = load_license()
        if key:
            result = recheck(key)
            if not result.get("ok"):
                self.log("⛔ Лицензия недействительна или истекла. Остановка.")
                self.running = False
            else:
                self.log(f"🔑 Лицензия активна. Осталось: {result.get('expires_in_hours')} ч.")
        self.root.after(3600000, self.periodic_check)  # раз в час

    # ---------------- Утилиты ----------------
    def log(self, msg):
        self.q.put(str(msg))

    def load_keys(self):
        path = filedialog.askopenfilename(filetypes=[("TXT", "*.txt")])
        if path:
            with open(path, encoding="utf-8") as f:
                self.keys = [l.strip() for l in f if l.strip()]
            self.log(f"Загружено ключей: {len(self.keys)}")

    def load_proxies(self):
        path = filedialog.askopenfilename(filetypes=[("TXT", "*.txt")])
        if path:
            with open(path, encoding="utf-8") as f:
                self.proxies = [l.strip() for l in f if l.strip()]
            self.log(f"Загружено прокси: {len(self.proxies)}")

    # ---------------- Запуск / остановка ----------------
    def start(self):
        if self.running:
            self.running = False
            self.start_btn.config(text="▶ ЗАПУСТИТЬ", bg="#4CAF50")
            return

        domain = self.domain.get().strip()
        if not domain or not self.keys:
            self.log("⚠ Укажите домен и загрузите файл ключей!")
            return

        self.running = True
        self.start_btn.config(text="■ ОСТАНОВИТЬ", bg="#f44336")

        total = int(self.clicks.get())
        thread = threading.Thread(target=self.worker, args=(domain, total), daemon=True)
        thread.start()

    # ---------------- Рабочий цикл ----------------
    def worker(self, domain, total):
        done = 0
        try:
            with sync_playwright() as p:
                while done < total and self.running:
                    proxy = random.choice(self.proxies) if self.proxies else None
                    kwargs = {"headless": False}
                    if BROWSER_CHANNEL:
                        kwargs["channel"] = BROWSER_CHANNEL
                    if proxy:
                        kwargs["proxy"] = {"server": f"http://{proxy}"}
                        self.log(f"Прокси: {proxy.split('@')[-1]}")

                    try:
                        browser = p.chromium.launch(**kwargs)
                        ctx = browser.new_context(
                            user_agent=random.choice(UA_LIST),
                            locale="ru-RU",
                            viewport={
                                "width": random.choice([1366, 1536, 1920]),
                                "height": random.choice([768, 864, 1080]),
                            },
                        )
                        ctx.add_init_script(STEALTH)
                        page = ctx.new_page()

                        key = random.choice(self.keys)
                        self.log(f"[{done+1}/{total}] Ключ: «{key}»")

                        page.goto(
                            f"https://www.google.com/search?q={key.replace(' ', '+')}&hl=ru",
                            wait_until="domcontentloaded", timeout=45000,
                        )
                        time.sleep(random.uniform(3, 6))

                        ads = page.locator(f"a[href*='{domain}']")
                        if ads.count() == 0:
                            self.log("  Объявление не найдено в выдаче")
                        else:
                            time.sleep(random.uniform(2, 5))
                            ads.first.click()
                            page.wait_for_load_state("domcontentloaded")
                            # имитация живого пользователя
                            for _ in range(random.randint(3, 6)):
                                page.mouse.wheel(0, random.randint(150, 400))
                                time.sleep(random.uniform(0.5, 1.5))
                            time.sleep(random.uniform(15, 50))
                            done += 1
                            self.log(f"  ✓ Клик выполнен ({done}/{total})")

                        browser.close()
                    except Exception as e:
                        self.log(f"  ✗ Ошибка: {e}")
                        try:
                            browser.close()
                        except Exception:
                            pass

                    # пауза между кликами (20–60 сек)
                    for _ in range(random.randint(20, 60)):
                        if not self.running:
                            break
                        time.sleep(1)
        except Exception as e:
            self.log(f"✗ Критическая ошибка: {e}")

        self.log(f"— Готово. Кликов выполнено: {done} —")
        self.running = False
        self.start_btn.config(text="▶ ЗАПУСТИТЬ", bg="#4CAF50")


# ============================================================
#  ТОЧКА ВХОДА: сначала активация, потом главное окно
# ============================================================

if __name__ == "__main__":
    from activation_window import show_activation

    def launch_main_app():
        root = tk.Tk()
        app = ClickerApp(root)

        def poll_queue():
            while not app.q.empty():
                app.log_box.insert("end", app.q.get() + "\n")
                app.log_box.see("end")
            root.after(300, poll_queue)

        poll_queue()
        root.mainloop()

    show_activation(launch_main_app)
