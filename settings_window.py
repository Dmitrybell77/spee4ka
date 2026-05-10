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


def open_settings(apply_callback: Optional[Callable] = None):
    """Open settings window. Blocks until closed. Call from a dedicated thread."""
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    api_key, folder_id = _read_env()

    root = tk.Tk()
    root.title("Спичка — Настройки")
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

    font_label = ("Segoe UI", 10)
    font_bold  = ("Segoe UI", 10, "bold")
    pad = {"padx": 10, "pady": 4}

    row = 0

    def label(text, r, bold=False):
        tk.Label(root, text=text, font=font_bold if bold else font_label).grid(
            row=r, column=0, sticky="w", **pad)

    # ── Hotkey ──────────────────────────────────────────────────────
    label("Горячая клавиша", row)
    hotkey_var = tk.StringVar(value=cfg.get("hotkey", "right ctrl"))
    capturing  = [False]

    hotkey_btn = tk.Button(
        root, textvariable=hotkey_var, width=22, font=font_label,
        relief="groove", cursor="hand2",
    )
    hotkey_btn.grid(row=row, column=1, sticky="w", **pad)
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
    label("Режим работы", row)
    _migrate = {"auto": "online_first", "online": "online_first", "offline": "offline_first"}
    current_mode_key = _migrate.get(cfg.get("mode", "offline_first"), cfg.get("mode", "offline_first"))
    mode_var = tk.StringVar(value=MODES.get(current_mode_key, MODE_LABELS[0]))
    mode_combo = ttk.Combobox(
        root, textvariable=mode_var, values=MODE_LABELS,
        state="readonly", width=35, font=font_label,
    )
    mode_combo.grid(row=row, column=1, sticky="w", **pad)
    row += 1

    model_var = tk.StringVar(value=cfg.get("local_model", "small"))

    # ── Checkboxes ───────────────────────────────────────────────────
    ttk.Separator(root, orient="horizontal").grid(
        row=row, column=0, columnspan=2, sticky="ew", pady=4); row += 1

    polish_var    = tk.BooleanVar(value=cfg.get("polish", True))
    preload_var   = tk.BooleanVar(value=cfg.get("preload_local_at_start", True))
    autostart_var = tk.BooleanVar(value=_autostart_enabled())

    for text, var in [
        ("Полировать текст через YandexGPT",              polish_var),
        ("Загружать Whisper в RAM при старте приложения", preload_var),
        ("Автозапуск с Windows",                          autostart_var),
    ]:
        tk.Checkbutton(root, text=text, variable=var, font=font_label).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=10, pady=2)
        row += 1

    # ── Yandex credentials ───────────────────────────────────────────
    ttk.Separator(root, orient="horizontal").grid(
        row=row, column=0, columnspan=2, sticky="ew", pady=4); row += 1

    label("Яндекс API Key", row)
    api_var = tk.StringVar(value=api_key)
    api_entry = tk.Entry(root, textvariable=api_var, show="*", width=36, font=font_label)
    api_entry.grid(row=row, column=1, sticky="ew", **pad)
    row += 1

    label("Folder ID", row)
    folder_var = tk.StringVar(value=folder_id)
    tk.Entry(root, textvariable=folder_var, width=36, font=font_label).grid(
        row=row, column=1, sticky="ew", **pad)
    row += 1

    tk.Label(root, text="⚠ Смена ключа/Folder ID применяется после перезапуска",
             font=("Segoe UI", 8), fg="gray").grid(
        row=row, column=0, columnspan=2, sticky="w", padx=10, pady=0)
    row += 1

    # ── License ───────────────────────────────────────────────────────
    ttk.Separator(root, orient="horizontal").grid(
        row=row, column=0, columnspan=2, sticky="ew", pady=4); row += 1

    try:
        from license_manager import get_saved_key, _read_local, activate
        _saved_key = get_saved_key(ROOT)
        # Use local cache only — no network request so the window opens instantly
        _local_lic = _read_local(ROOT) or {}
        _lic_valid = _local_lic.get("status") == "active"
        _lic_expires = _local_lic.get("expires", "")

        label("Лицензия", row, bold=True)
        lic_status_text = "✓ Активирована" if _lic_valid else "✗ Не активирована"
        lic_status_color = "green" if _lic_valid else "red"
        tk.Label(root, text=lic_status_text, font=font_label, fg=lic_status_color).grid(
            row=row, column=1, sticky="w", **pad)
        row += 1

        if _lic_valid and _saved_key:
            label("Ключ", row)
            tk.Label(root, text=_saved_key[:9] + "****", font=("Consolas", 10)).grid(
                row=row, column=1, sticky="w", **pad)
            row += 1

            if _lic_expires:
                label("Действует до", row)
                tk.Label(root, text=_lic_expires[:10], font=font_label).grid(
                    row=row, column=1, sticky="w", **pad)
                row += 1
        else:
            label("Лицензионный ключ", row)
            lic_key_var = tk.StringVar()
            tk.Entry(root, textvariable=lic_key_var, width=24, font=("Consolas", 10)).grid(
                row=row, column=1, sticky="w", **pad)
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

            tk.Button(root, text="Активировать", command=_do_activate,
                      width=14, font=font_label).grid(
                row=row, column=0, columnspan=2, pady=4)
            row += 1

            tk.Label(root, textvariable=lic_msg_var, font=("Segoe UI", 9), fg="red").grid(
                row=row, column=0, columnspan=2, sticky="w", padx=10)
            row += 1
    except ImportError:
        pass

    # ── Buttons ──────────────────────────────────────────────────────
    ttk.Separator(root, orient="horizontal").grid(
        row=row, column=0, columnspan=2, sticky="ew", pady=4); row += 1

    def _save():
        if hotkey_var.get() == "Нажмите клавишу…":
            messagebox.showwarning("Спичка", "Горячая клавиша не выбрана.\nНажмите кнопку и выберите клавишу.")
            return

        # Resolve mode key from display label
        friendly = mode_var.get()
        new_mode = next((k for k, v in MODES.items() if v == friendly), "offline_first")

        cfg["hotkey"]              = hotkey_var.get()
        cfg["mode"]                = new_mode
        cfg["local_model"]         = model_var.get()
        cfg["local_language"]      = "ru"
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

    btn_frame = tk.Frame(root)
    btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
    tk.Button(btn_frame, text="Сохранить", command=_save,
              width=14, font=font_label).pack(side="left", padx=8)
    tk.Button(btn_frame, text="Отмена", command=root.destroy,
              width=10, font=font_label).pack(side="left", padx=8)

    root.mainloop()


if __name__ == "__main__":
    open_settings()
