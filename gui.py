# gui.py — Google Ads Clicker PRO v2 (Multithread)
import subprocess, sys, os, threading, queue, random, time
import tkinter as tk
from tkinter import scrolledtext, filedialog
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# ============================================================
#  НАСТРОЙКИ
# ============================================================

MAX_THREADS_DEFAULT = 20

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
]

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = window.chrome || { runtime: {} };
Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru', 'en-US']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
"""

# ============================================================
#  ПУЛ ПРОКСИ
# ============================================================

class ProxyPool:
    def __init__(self, proxies):
        self._list = list(proxies)
        self._lock = threading.Lock()
        self._idx = 0

    def next(self):
        with self._lock:
            if not self._list:
                return None
            proxy = self._list[self._idx % len(self._list)]
            self._idx += 1
            return proxy

# ============================================================
#  ПОДКЛЮЧЕНИЕ К БРАУЗЕРУ / АНТИДЕТЕКТУ
# ============================================================

def connect_antidetect(p, cdp_port=None):
    if cdp_port:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}", timeout=30000)
        return browser, False
    for channel in ("chrome", "msedge", "firefox"):
        try:
            browser = p.chromium.launch(channel=channel, headless=False)
            return browser, True
        except Exception:
            continue
    browser = p.chromium.launch(headless=False)
    return browser, True

# ============================================================
#  ГЛАВНОЕ ПРИЛОЖЕНИЕ
# ============================================================

class ClickerApp:
    def __init__(self, root):
        self.root = root
        root.title("Google Ads Clicker PRO v2")
        root.geometry("750x640")

        frm = tk.Frame(root)
        frm.pack(fill="x", padx=10, pady=5)

        tk.Label(frm, text="Домен конкурента:").grid(row=0, column=0, sticky="w")
        self.domain = tk.Entry(frm, width=42)
        self.domain.grid(row=0, column=1, columnspan=2, sticky="we", pady=2)

        tk.Label(frm, text="Всего кликов:").grid(row=1, column=0, sticky="w")
        self.total_clicks = tk.Spinbox(frm, from_=1, to=100000, width=8)
        self.total_clicks.delete(0, "end"); self.total_clicks.insert(0, "500")
        self.total_clicks.grid(row=1, column=1, sticky="w", pady=2)

        tk.Label(frm, text="Потоков:").grid(row=1, column=2, sticky="w", padx=(15, 0))
        self.threads_spin = tk.Spinbox(frm, from_=1, to=50, width=5)
        self.threads_spin.delete(0, "end"); self.threads_spin.insert(0, str(MAX_THREADS_DEFAULT))
        self.threads_spin.grid(row=1, column=2, sticky="e", pady=2)

        tk.Label(frm, text="Пауза между кликами, сек (от-до):").grid(row=2, column=0, sticky="w")
        self.pause_from = tk.Spinbox(frm, from_=5, to=600, width=5)
        self.pause_from.delete(0, "end"); self.pause_from.insert(0, "20")
        self.pause_from.grid(row=2, column=1, sticky="w", pady=2)
        self.pause_to = tk.Spinbox(frm, from_=10, to=3600, width=5)
        self.pause_to.delete(0, "end"); self.pause_to.insert(0, "60")
        self.pause_to.grid(row=2, column=1, padx=(60, 0), sticky="w", pady=2)

        tk.Label(frm, text="CDP-порт антидетекта (пусто = свой браузер):").grid(row=3, column=0, sticky="w")
        self.cdp_entry = tk.Entry(frm, width=12)
        self.cdp_entry.grid(row=3, column=1, sticky="w", pady=2)

        btns = tk.Frame(frm); btns.grid(row=4, column=0, columnspan=3, sticky="we", pady=4)
        tk.Button(btns, text="Ключи (keys.txt)", command=self.load_keys).pack(side="left", padx=(0, 5))
        tk.Button(btns, text="Прокси (proxies.txt)", command=self.load_proxies).pack(side="left")
        self.lbl_proxy = tk.Label(btns, text="прокси: 0", fg="gray")
        self.lbl_proxy.pack(side="left", padx=10)

        self.start_btn = tk.Button(root, text="▶ ЗАПУСТИТЬ", bg="#4CAF50", fg="white",
                                   command=self.start, font=("Arial", 11, "bold"))
        self.start_btn.pack(fill="x", padx=10, pady=5)

        self.progress = tk.Label(root, text="Кликов: 0 / —", anchor="w", font=("Arial", 10, "bold"))
        self.progress.pack(fill="x", padx=12)

        tk.Label(root, text="Лог:").pack(anchor="w", padx=10)
        self.log_box = scrolledtext.ScrolledText(root, height=16)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.q = queue.Queue()
        self.keys, self.proxy_lines = [], []
        self.running = False
        self.done_count = 0
        self.lock = threading.Lock()

    # ---------------- утилиты ----------------
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
                self.proxy_lines = [l.strip() for l in f if l.strip()]
            self.lbl_proxy.config(text=f"прокси: {len(self.proxy_lines)}")

    def _inc_done(self):
        with self.lock:
            self.done_count += 1
            self.q.put(f"__PROGRESS__{self.done_count}")

    def _total_done(self):
        with self.lock:
            return self.done_count

    # ---------------- запуск ----------------
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
        self.done_count = 0
        self.start_btn.config(text="■ ОСТАНОВИТЬ", bg="#f44336")

        total = int(self.total_clicks.get())
        n_threads = int(self.threads_spin.get())
        pf, pt = int(self.pause_from.get()), int(self.pause_to.get())
        cdp = self.cdp_entry.get().strip()

        args = (domain, total, n_threads, pf, pt, cdp)
        threading.Thread(target=self.master_worker, args=args, daemon=True).start()

    # ---------------- многопоточный цикл ----------------
    def master_worker(self, domain, total, n_threads, pause_from, pause_to, cdp_port):
        pool = ProxyPool(self.proxy_lines)
        key_cycle = {"i": 0}
        key_lock = threading.Lock()

        def next_key():
            with key_lock:
                k = self.keys[key_cycle["i"] % len(self.keys)]
                key_cycle["i"] += 1
                return k

        def thread_job(thread_num):
            try:
                with sync_playwright() as p:
                    browser, owned = connect_antidetect(p, cdp_port or None)
                    try:
                        while self.running and self._total_done() < total:
                            proxy = pool.next()
                            kw = {}
                            if proxy and not cdp_port:
                                kw["proxy"] = {"server": f"http://{proxy}"}

                            page = None
                            ctx = None
                            try:
                                if cdp_port:
                                    contexts = browser.contexts
                                    ctx = contexts[0] if contexts else browser.new_context()
                                    page = ctx.new_page()
                                else:
                                    ctx = browser.new_context(
                                        user_agent=random.choice(UA_POOL),
                                        locale="ru-RU",
                                        timezone_id=random.choice(
                                            ["Europe/Moscow", "Europe/Kaliningrad", "Europe/Samara"]),
                                        viewport={"width": random.choice([1366, 1536, 1920]),
                                                  "height": random.choice([768, 864, 1080])},
                                    )
                                    ctx.add_init_script(STEALTH_JS)
                                    page = ctx.new_page()

                                keyword = next_key()

                                page.goto(
                                    f"https://www.google.com/search?q={keyword.replace(' ', '+')}&hl=ru",
                                    wait_until="domcontentloaded", timeout=45000)
                                time.sleep(random.uniform(3, 6))

                                ads = page.locator(f"a[href*='{domain}']")
                                if ads.count() > 0:
                                    time.sleep(random.uniform(2, 5))
                                    ads.first.click()
                                    page.wait_for_load_state("domcontentloaded")
                                    for _ in range(random.randint(3, 6)):
                                        page.mouse.wheel(0, random.randint(150, 400))
                                        time.sleep(random.uniform(0.5, 1.5))
                                    time.sleep(random.uniform(15, 40))
                                    self._inc_done()
                                    self.log(f"✓ {self._total_done()} склик успешно отправлен")
                            except Exception as e:
                                self.log(f"✗ Ошибка: {e}")
                            finally:
                                try:
                                    if page: page.close()
                                except Exception: pass
                                try:
                                    if ctx and not cdp_port: ctx.close()
                                except Exception: pass

                            pause = random.uniform(pause_from, pause_to)
                            for _ in range(int(pause)):
                                if not self.running:
                                    break
                                time.sleep(1)
                    finally:
                        if owned:
                            browser.close()
            except Exception as e:
                self.log(f"✗ Критическая ошибка потока: {e}")
