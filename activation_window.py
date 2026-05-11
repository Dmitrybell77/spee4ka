"""Activation dialog — runs as a standalone subprocess."""
import os
import sys
from pathlib import Path

# Must set TCL/TK paths BEFORE importing tkinter (embedded Python doesn't auto-discover)
_py_dir = Path(sys.executable).parent
_dlls_dir = _py_dir / "DLLs"
if _dlls_dir.is_dir():
    os.add_dll_directory(str(_dlls_dir))
for _d in [_py_dir / "tcl8.6", _py_dir / "tcl9.0"]:
    if _d.is_dir():
        os.environ.setdefault("TCL_LIBRARY", str(_d))
        break
for _d in [_py_dir / "tk8.6", _py_dir / "tk9.0"]:
    if _d.is_dir():
        os.environ.setdefault("TK_LIBRARY", str(_d))
        break

import tkinter as tk
from tkinter import ttk

ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── Palette (kept in sync with settings_window.py and the landing page) ──
BG       = "#f6f6fa"
CARD     = "#ffffff"
TEXT     = "#1f2937"
MUTED    = "#6b7280"
ACCENT   = "#4338ca"
ACCENT_H = "#3730a3"
DANGER   = "#dc2626"
SUCCESS  = "#16a34a"
BORDER   = "#e5e7eb"


def _hover(btn, normal, hover):
    btn.bind("<Enter>", lambda _e: btn.config(bg=hover))
    btn.bind("<Leave>", lambda _e: btn.config(bg=normal))


def _accent_button(parent, text, command, width=18):
    b = tk.Button(
        parent, text=text, command=command,
        bg=ACCENT, fg="white", activebackground=ACCENT_H, activeforeground="white",
        font=("Segoe UI", 10, "bold"), relief="flat", bd=0, cursor="hand2",
        width=width, padx=12, pady=8,
    )
    _hover(b, ACCENT, ACCENT_H)
    return b


def _ghost_button(parent, text, command, width=10):
    b = tk.Button(
        parent, text=text, command=command,
        bg=CARD, fg=TEXT, activebackground="#eef0f5", activeforeground=TEXT,
        font=("Segoe UI", 10), relief="flat", bd=1,
        highlightbackground=BORDER, highlightthickness=1, cursor="hand2",
        width=width, padx=12, pady=8,
    )
    _hover(b, CARD, "#eef0f5")
    return b


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
    root.configure(bg=BG)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    try:
        _ico = ROOT.parent / "spee4ka.ico"
        if not _ico.exists():
            _ico = ROOT / "spee4ka.ico"
        if _ico.exists():
            root.iconbitmap(str(_ico))
    except Exception:
        pass

    # Outer card with subtle inset border
    card = tk.Frame(root, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
    card.pack(padx=18, pady=18, ipadx=24, ipady=20)

    tk.Label(card, text="🎤  Спичка", font=("Segoe UI", 18, "bold"),
             bg=CARD, fg=TEXT).pack(anchor="w")
    tk.Label(card, text="Активация лицензии",
             font=("Segoe UI", 10), bg=CARD, fg=MUTED).pack(anchor="w", pady=(0, 14))

    tk.Label(
        card,
        text="Введите лицензионный ключ:",
        font=("Segoe UI", 10), bg=CARD, fg=TEXT, justify="left",
    ).pack(anchor="w")
    tk.Label(
        card,
        text="Формат: SP4K-XXXX-XXXX-XXXX-XXXX",
        font=("Segoe UI", 9), bg=CARD, fg=MUTED, justify="left",
    ).pack(anchor="w", pady=(0, 6))

    key_var = tk.StringVar()
    entry_frame = tk.Frame(card, bg=CARD)
    entry_frame.pack(fill="x", pady=(0, 8))
    key_entry = tk.Entry(
        entry_frame, textvariable=key_var, width=26,
        font=("Consolas", 12), justify="center",
        relief="flat", bd=0, bg="#f3f4f6", fg=TEXT,
        highlightbackground=BORDER, highlightthickness=1,
        insertbackground=TEXT,
    )
    key_entry.pack(side="left", ipady=8, fill="x", expand=True)

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
    # На русской раскладке keysym = "м", Tkinter не принимает кириллицу в bind-строках.
    # Биндим на любой Ctrl+клавишу и сверяем keycode (V = 86 на Windows на любой раскладке).
    def _on_ctrl_key(event):
        if event.keycode == 86:
            return _paste(event)
    key_entry.bind("<Control-KeyPress>", _on_ctrl_key)
    paste_btn = tk.Button(
        entry_frame, text="📋", command=_paste,
        bg=CARD, fg=TEXT, activebackground="#eef0f5",
        font=("Segoe UI", 11), relief="flat", bd=1,
        highlightbackground=BORDER, highlightthickness=1, cursor="hand2",
        width=2,
    )
    paste_btn.pack(side="left", padx=(6, 0), ipady=5)
    _hover(paste_btn, CARD, "#eef0f5")

    root.update()
    key_entry.focus_force()

    status_var = tk.StringVar(value="")
    status_label = tk.Label(card, textvariable=status_var, font=("Segoe UI", 9),
                            bg=CARD, fg=DANGER, wraplength=320, justify="left")
    status_label.pack(anchor="w", pady=(4, 0))

    def _set_status(text, color=DANGER):
        status_var.set(text)
        status_label.config(fg=color)
        root.update()

    def _activate():
        key = key_var.get().strip().upper()
        if not key:
            _set_status("Введите ключ")
            return
        _set_status("Проверяю…", MUTED)
        res = activate(key, ROOT)
        if res.get("ok"):
            _set_status("✓ Активировано!", SUCCESS)
            root.after(1500, lambda: (root.destroy(), sys.exit(0)))
        else:
            error = res.get("error", "Ошибка активации")
            _set_status({
                "no_connection":   "Нет соединения с сервером лицензий",
                "key_not_found":   "Ключ не найден",
                "already_used":    "Ключ уже используется на другом ПК",
                "expired":         "Срок лицензии истёк",
                "too_many_requests": "Слишком много попыток. Подождите минуту.",
            }.get(error, error))

    btn_frame = tk.Frame(card, bg=CARD)
    btn_frame.pack(fill="x", pady=(16, 0))
    _accent_button(btn_frame, "Активировать", _activate, width=18).pack(side="right")
    _ghost_button(btn_frame, "Отмена", root.destroy, width=10).pack(side="right", padx=(0, 8))

    root.bind("<Return>", lambda e: _activate())
    root.bind("<Escape>", lambda e: root.destroy())

    # Centre on screen
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 3}")

    root.mainloop()
    sys.exit(1)


if __name__ == "__main__":
    main()
