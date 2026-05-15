"""Settings window for Spee4ka (tkinter, Russian UI)."""
import json
import os
import sys
from pathlib import Path as _Path

# Embedded Python: add DLLs dir so _tkinter.pyd can find tcl86t.dll / tk86t.dll
_py_dir = _Path(sys.executable).parent
_dlls_dir = _py_dir / "DLLs"
if _dlls_dir.is_dir():
    os.add_dll_directory(str(_dlls_dir))
# Set TCL/TK library paths for embedded Python
for _tcl_ver in ("tcl8.6", "tcl9.0"):
    _p = _py_dir / _tcl_ver
    if _p.is_dir():
        os.environ.setdefault("TCL_LIBRARY", str(_p))
        break
for _tk_ver in ("tk8.6", "tk9.0"):
    _p = _py_dir / _tk_ver
    if _p.is_dir():
        os.environ.setdefault("TK_LIBRARY", str(_p))
        break

import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).parent

_STARTUP_SHORTCUT = (
    Path(os.environ.get("APPDATA", ""))
    / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Spee4ka.lnk"
)

# ── Palette (in sync with activation_window.py and the landing page) ──
BG       = "#f6f6fa"
CARD     = "#ffffff"
TEXT     = "#1f2937"
MUTED    = "#6b7280"
ACCENT   = "#4338ca"
ACCENT_H = "#3730a3"
DANGER   = "#dc2626"
SUCCESS  = "#16a34a"
BORDER   = "#e5e7eb"

MODES = {
    "offline_first": "Офлайн-first (Whisper → Яндекс при сбое)",
    "online_first":  "Онлайн-first (Яндекс → Whisper при сбое)",
}
MODE_KEYS   = list(MODES.keys())
MODE_LABELS = list(MODES.values())

_HOTKEY_MAP = {
    "control_r": "right ctrl",
    "control_l": "left ctrl",
    "alt_r":     "right alt",
    "alt_l":     "left alt",
    "shift_r":   "right shift",
    "shift_l":   "left shift",
    "super_l":   "windows",
    "super_r":   "windows",
}


def _tk_key_to_hotkey(keysym: str) -> str:
    return _HOTKEY_MAP.get(keysym.lower(), keysym.lower())


def _autostart_enabled() -> bool:
    return _STARTUP_SHORTCUT.exists()


def _set_autostart(enabled: bool):
    if enabled:
        import subprocess
        exe_dir = _Path(sys.executable).parent if getattr(sys, 'frozen', False) else ROOT.parent
        target = str(exe_dir / "Spee4ka.exe")
        if not _Path(target).exists():
            target = str(ROOT / "Spee4ka.exe")
        shortcut = str(_STARTUP_SHORTCUT)
        ps_cmd = (
            f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{shortcut}');"
            f"$s.TargetPath = '{target}';"
            f"$s.WorkingDirectory = '{_Path(target).parent}';"
            f"$s.Description = 'Спичка';"
            f"$s.Save()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True, timeout=15, creationflags=0x08000000,
        )
        if not _STARTUP_SHORTCUT.exists():
            raise RuntimeError("Ярлык не создан")
    else:
        _STARTUP_SHORTCUT.unlink(missing_ok=True)


def _read_env() -> tuple[str, str]:
    api_key = folder_id = ""
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("YANDEX_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
            elif line.startswith("YANDEX_FOLDER_ID="):
                folder_id = line.split("=", 1)[1].strip()
    try:
        from crypto_utils import decrypt_value
        api_key = decrypt_value(api_key) if api_key else api_key
        folder_id = decrypt_value(folder_id) if folder_id else folder_id
    except ImportError:
        pass
    return api_key, folder_id


def _write_env(api_key: str, folder_id: str):
    env_path = ROOT / ".env"
    lines: list[str] = []
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("YANDEX_API_KEY=") and not line.startswith("YANDEX_FOLDER_ID="):
                lines.append(line)
    try:
        from crypto_utils import encrypt_value
        if api_key:
            api_key = encrypt_value(api_key)
        if folder_id:
            folder_id = encrypt_value(folder_id)
    except ImportError:
        pass
    lines.append(f"YANDEX_API_KEY={api_key}")
    lines.append(f"YANDEX_FOLDER_ID={folder_id}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _hover(btn, normal, hover):
    btn.bind("<Enter>", lambda _e: btn.config(bg=hover))
    btn.bind("<Leave>", lambda _e: btn.config(bg=normal))


def _accent_button(parent, text, command, width=14):
    b = tk.Button(
        parent, text=text, command=command,
        bg=ACCENT, fg="white", activebackground=ACCENT_H, activeforeground="white",
        font=("Segoe UI", 10, "bold"), relief="flat", bd=0, cursor="hand2",
        width=width, padx=10, pady=7,
    )
    _hover(b, ACCENT, ACCENT_H)
    return b


def _ghost_button(parent, text, command, width=10):
    b = tk.Button(
        parent, text=text, command=command,
        bg=CARD, fg=TEXT, activebackground="#eef0f5", activeforeground=TEXT,
        font=("Segoe UI", 10), relief="flat", bd=1,
        highlightbackground=BORDER, highlightthickness=1, cursor="hand2",
        width=width, padx=10, pady=7,
    )
    _hover(b, CARD, "#eef0f5")
    return b


def _styled_entry(parent, textvariable, show=None, width=32, font=("Segoe UI", 10)):
    e = tk.Entry(
        parent, textvariable=textvariable, show=show or "",
        width=width, font=font,
        relief="flat", bd=0, bg="#f3f4f6", fg=TEXT,
        highlightbackground=BORDER, highlightthickness=1,
        insertbackground=TEXT,
    )
    # Ctrl+V на русской раскладке: keysym становится 'м', стандартный bind не срабатывает.
    # Биндим по keycode (V = 86 на Windows вне зависимости от раскладки).
    def _paste(event=None):
        try:
            text = e.clipboard_get()
        except Exception:
            return "break"
        if text:
            try:
                e.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            e.insert("insert", text)
        return "break"
    e.bind("<Control-v>", _paste)
    e.bind("<Control-V>", _paste)
    def _on_ctrl_key(event):
        if event.keycode == 86:
            return _paste(event)
    e.bind("<Control-KeyPress>", _on_ctrl_key)
    return e


def open_settings(apply_callback: Optional[Callable] = None):
    """Open settings window. Blocks until closed. Call from a dedicated thread."""
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    api_key, folder_id = _read_env()

    root = tk.Tk()
    root.title("Спичка — Настройки")
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

    # ttk styling for the combobox (the only ttk widget here)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "Modern.TCombobox",
        fieldbackground="#f3f4f6", background="#f3f4f6", foreground=TEXT,
        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
        arrowcolor=TEXT, padding=6,
    )

    # ── Outer card ──────────────────────────────────────────────────
    card = tk.Frame(root, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
    card.pack(padx=18, pady=18, ipadx=20, ipady=18)

    # Header
    tk.Label(card, text="🎤  Спичка", font=("Segoe UI", 18, "bold"),
             bg=CARD, fg=TEXT).grid(row=0, column=0, columnspan=2, sticky="w")
    tk.Label(card, text="Настройки", font=("Segoe UI", 10),
             bg=CARD, fg=MUTED).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

    def _section(title, r):
        tk.Label(card, text=title, font=("Segoe UI", 9, "bold"),
                 bg=CARD, fg=MUTED).grid(row=r, column=0, columnspan=2,
                                          sticky="w", pady=(8, 4))

    def _label(text, r, bold=False):
        tk.Label(card, text=text, font=("Segoe UI", 10, "bold" if bold else "normal"),
                 bg=CARD, fg=TEXT).grid(row=r, column=0, sticky="w", padx=(0, 14), pady=4)

    row = 2

    # ── Hotkey ──────────────────────────────────────────────────────
    _section("Управление", row); row += 1
    _label("Горячая клавиша", row)
    hotkey_var = tk.StringVar(value=cfg.get("hotkey", "right ctrl"))
    capturing  = [False]

    hotkey_btn = tk.Button(
        card, textvariable=hotkey_var, width=22, font=("Segoe UI", 10),
        bg="#f3f4f6", fg=TEXT, activebackground="#eef0f5",
        relief="flat", bd=1,
        highlightbackground=BORDER, highlightthickness=1, cursor="hand2",
        padx=8, pady=6,
    )
    _hover(hotkey_btn, "#f3f4f6", "#eef0f5")
    hotkey_btn.grid(row=row, column=1, sticky="w", pady=4)
    row += 1

    def _start_capture():
        if capturing[0]:
            return
        capturing[0] = True
        hotkey_var.set("Нажмите клавишу…")
        root.bind("<KeyPress>", _on_key)
        root.focus_set()

    def _on_key(e):
        root.unbind("<KeyPress>")
        capturing[0] = False
        hotkey_var.set(_tk_key_to_hotkey(e.keysym))

    hotkey_btn.config(command=_start_capture)

    # ── Mode ─────────────────────────────────────────────────────────
    _label("Режим работы", row)
    _migrate = {"auto": "online_first", "online": "online_first", "offline": "offline_first"}
    current_mode_key = _migrate.get(cfg.get("mode", "offline_first"), cfg.get("mode", "offline_first"))
    mode_var = tk.StringVar(value=MODES.get(current_mode_key, MODE_LABELS[0]))
    mode_combo = ttk.Combobox(
        card, textvariable=mode_var, values=MODE_LABELS,
        state="readonly", width=34, font=("Segoe UI", 10),
        style="Modern.TCombobox",
    )
    mode_combo.grid(row=row, column=1, sticky="w", pady=4)
    row += 1

    model_var = tk.StringVar(value=cfg.get("local_model", "small"))

    # ── Options ───────────────────────────────────────────────────────
    _section("Опции", row); row += 1

    polish_var    = tk.BooleanVar(value=cfg.get("polish", True))
    preload_var   = tk.BooleanVar(value=cfg.get("preload_local_at_start", True))
    autostart_var = tk.BooleanVar(value=_autostart_enabled())

    for text, var in [
        ("Полировать текст через YandexGPT",              polish_var),
        ("Загружать Whisper в RAM при старте приложения", preload_var),
        ("Автозапуск с Windows",                          autostart_var),
    ]:
        tk.Checkbutton(
            card, text=text, variable=var,
            font=("Segoe UI", 10), bg=CARD, fg=TEXT, activebackground=CARD,
            selectcolor=CARD, highlightthickness=0, bd=0,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=3)
        row += 1

    # ── Yandex credentials ───────────────────────────────────────────
    _section("Яндекс API", row); row += 1

    _label("API Key", row)
    api_var = tk.StringVar(value=api_key)
    api_entry = _styled_entry(card, api_var, show="*", width=34)
    api_entry.grid(row=row, column=1, sticky="ew", ipady=6, pady=4)
    row += 1

    _label("Folder ID", row)
    folder_var = tk.StringVar(value=folder_id)
    _styled_entry(card, folder_var, width=34).grid(
        row=row, column=1, sticky="ew", ipady=6, pady=4)
    row += 1

    tk.Label(
        card,
        text="⚠ Смена ключа/Folder ID применяется после перезапуска",
        font=("Segoe UI", 8), bg=CARD, fg=MUTED,
    ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))
    row += 1

    # ── License ───────────────────────────────────────────────────────
    try:
        from license_manager import get_saved_key, _read_local, activate
        _saved_key = get_saved_key(ROOT)
        # Use local cache only — no network request so the window opens instantly
        _local_lic = _read_local(ROOT) or {}
        _lic_valid = _local_lic.get("status") == "active"
        _lic_expires = _local_lic.get("expires", "")

        _section("Лицензия", row); row += 1
        lic_status_text  = "✓ Активирована" if _lic_valid else "✗ Не активирована"
        lic_status_color = SUCCESS if _lic_valid else DANGER
        tk.Label(card, text=lic_status_text, font=("Segoe UI", 10, "bold"),
                 bg=CARD, fg=lic_status_color).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        if _lic_valid and _saved_key:
            _label("Ключ", row)
            # Reveal only the last group of the key (e.g. "SP4K-****-****-****-AB12")
            _key_tail = _saved_key.rsplit("-", 1)[-1] if "-" in _saved_key else _saved_key[-4:]
            _masked = f"SP4K-****-****-****-{_key_tail}"
            tk.Label(card, text=_masked, font=("Consolas", 10),
                     bg=CARD, fg=TEXT).grid(row=row, column=1, sticky="w", pady=4)
            row += 1

            if _lic_expires:
                _label("Действует до", row)
                tk.Label(card, text=_lic_expires[:10], font=("Segoe UI", 10),
                         bg=CARD, fg=TEXT).grid(row=row, column=1, sticky="w", pady=4)
                row += 1
        else:
            _label("Лицензионный ключ", row)
            lic_key_var = tk.StringVar()
            _styled_entry(card, lic_key_var, width=24, font=("Consolas", 10)).grid(
                row=row, column=1, sticky="w", ipady=6, pady=4)
            row += 1

            lic_msg_var = tk.StringVar(value="")

            def _do_activate():
                key = lic_key_var.get().strip().upper()
                if not key:
                    lic_msg_var.set("Введите ключ")
                    return
                res = activate(key, ROOT)
                if res.get("ok"):
                    messagebox.showinfo("Спичка", "Лицензия активирована!")
                    root.destroy()
                else:
                    lic_msg_var.set(res.get("error", "Ошибка"))

            _accent_button(card, "Активировать", _do_activate, width=14).grid(
                row=row, column=0, columnspan=2, pady=8, sticky="w")
            row += 1

            tk.Label(card, textvariable=lic_msg_var, font=("Segoe UI", 9),
                     bg=CARD, fg=DANGER).grid(
                row=row, column=0, columnspan=2, sticky="w")
            row += 1
    except ImportError:
        pass

    # ── Buttons ──────────────────────────────────────────────────────
    def _save():
        if hotkey_var.get() == "Нажмите клавишу…":
            messagebox.showwarning("Спичка", "Горячая клавиша не выбрана.\nНажмите кнопку и выберите клавишу.")
            return

        # Resolve mode key from display label
        friendly = mode_var.get()
        new_mode = next((k for k, v in MODES.items() if v == friendly), "offline_first")

        cfg["hotkey"]                 = hotkey_var.get()
        cfg["mode"]                   = new_mode
        cfg["local_model"]            = model_var.get()
        cfg["local_language"]         = "ru"
        cfg["polish"]                 = polish_var.get()
        cfg["preload_local_at_start"] = preload_var.get()

        try:
            (ROOT / "config.json").write_text(
                json.dumps(cfg, ensure_ascii=False, indent=4), encoding="utf-8")
            _write_env(api_var.get().strip(), folder_var.get().strip())
        except Exception as ex:
            messagebox.showerror("Спичка", f"Не удалось сохранить настройки:\n{ex}")
            return

        try:
            _set_autostart(autostart_var.get())
        except Exception as ex:
            messagebox.showwarning("Спичка", f"Автозапуск: {ex}")

        if apply_callback:
            apply_callback(cfg)

        root.destroy()

    btn_frame = tk.Frame(card, bg=CARD)
    btn_frame.grid(row=row, column=0, columnspan=2, pady=(16, 0), sticky="e")
    _accent_button(btn_frame, "Сохранить", _save, width=14).pack(side="right")
    _ghost_button(btn_frame, "Отмена", root.destroy, width=10).pack(side="right", padx=(0, 8))

    root.bind("<Escape>", lambda e: root.destroy())

    # Centre on screen
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 3}")

    root.mainloop()


if __name__ == "__main__":
    open_settings()
