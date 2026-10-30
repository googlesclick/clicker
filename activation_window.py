# activation_window.py — окно активации перед главным приложением
import tkinter as tk
from tkinter import messagebox
from license_client import verify, save_license, load_license


def show_activation(on_success):
    saved = load_license()

    win = tk.Tk()
    win.title("Активация — Google Ads Clicker")
    win.geometry("430x280")
    win.resizable(False, False)

    tk.Label(win, text="🔑 Введите лицензионный ключ",
             font=("Arial", 12, "bold")).pack(pady=15)

    entry = tk.Entry(win, width=32, justify="center", font=("Consolas", 12))
    entry.insert(0, saved)
    entry.pack(pady=10)

    status_label = tk.Label(win, text="", fg="gray")
    status_label.pack()

    tk.Label(win, text="Ключ привязывается к этому ПК при первой активации\nи работает указанный срок",
             fg="gray", font=("Arial", 8)).pack(pady=8)

    def try_activate():
        key = entry.get().strip()
        if not key:
            messagebox.showwarning("Внимание", "Введите ключ!")
            return
        status_label.config(text="Проверяем ключ...", fg="blue")
        win.update()

        result = verify(key)
        if result.get("ok"):
            save_license(key)
            hours = result.get("expires_in_hours", "?")
            messagebox.showinfo("Успех", f"Лицензия активна!\nОсталось: {hours} ч.")
            win.destroy()
            on_success()
        else:
            status_label.config(text=result.get("msg", "Ошибка активации"), fg="red")

    tk.Button(win, text="АКТИВИРОВАТЬ", bg="#4CAF50", fg="white",
              command=try_activate, font=("Arial", 11, "bold"), width=25).pack(pady=12)

    win.mainloop()