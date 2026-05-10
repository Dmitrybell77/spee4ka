"""Activation dialog — runs as a standalone subprocess."""
import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
sys.path.insert(0, str(ROOT))


def main():
    try:
        from license_manager import activate
    except ImportError:
        tk.Tk().withdraw()
        import tkinter.messagebox
        tkinter.messagebox.showerror("Спичка", "Модуль лицензирования не найден.")
        sys.exit(1)

    root = tk.Tk()
    root.title("Спичка — Активация")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    font_label = ("Segoe UI", 10)
    pad = {"padx": 20, "pady": 6}

    tk.Label(root, text="Спичка", font=("Segoe UI", 14, "bold")).pack(**pad)
    tk.Label(
        root,
        text="Введите лицензионный ключ для активации.\nФормат: SP4K-XXXX-XXXX-XXXX-XXXX",
        font=font_label, justify="center",
    ).pack(**pad)

    key_var = tk.StringVar()
    entry_frame = tk.Frame(root)
    entry_frame.pack(padx=20, pady=8)
    key_entry = tk.Entry(entry_frame, textvariable=key_var, width=26,
                         font=("Consolas", 11), justify="center")
    key_entry.pack(side="left")

    def _paste(event=None):
        try:
            text = root.clipboard_get()
        except Exception:
            text = ""
        if text.strip():
            key_var.set(text.strip())
            key_entry.icursor(tk.END)
        return "break"

    key_entry.bind("<Control-v>", _paste)
    key_entry.bind("<Control-V>", _paste)
    tk.Button(entry_frame, text="📋", command=_paste,
              font=("Segoe UI", 10), width=2).pack(side="left", padx=(4, 0))

    root.update()
    key_entry.focus_force()

    status_var = tk.StringVar(value="")
    status_label = tk.Label(root, textvariable=status_var, font=("Segoe UI", 9), fg="red")
    status_label.pack(padx=20)

    def _set_status(text, color="red"):
        status_var.set(text)
        status_label.config(fg=color)
        root.update()

    def _activate():
        key = key_var.get().strip().upper()
        if not key:
            _set_status("Введите ключ")
            return
        _set_status("Проверяю...", "gray")
        res = activate(key, ROOT)
        if res.get("ok"):
            _set_status("✓ Активировано!", "green")
            root.after(1500, lambda: (root.destroy(), sys.exit(0)))
        else:
            error = res.get("error", "Ошибка активации")
            _set_status({
                "no_connection": "Нет соединения с сервером",
                "key_not_found": "Ключ не найден",
                "already_used": "Ключ уже используется на другом ПК",
                "expired": "Лицензия истекла",
            }.get(error, error))

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Активировать", command=_activate,
              width=14, font=font_label).pack(side="left", padx=8)
    tk.Button(btn_frame, text="Отмена", command=root.destroy,
              width=10, font=font_label).pack(side="left", padx=8)

    root.bind("<Return>", lambda e: _activate())
    root.mainloop()
    sys.exit(1)


if __name__ == "__main__":
    main()
