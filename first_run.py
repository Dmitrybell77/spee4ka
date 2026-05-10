"""
First-run Whisper model downloader.
Call check_and_download_model() before starting the main app.
Shows a tkinter progress window if the model needs to be downloaded.
"""
import threading
import tkinter as tk
from tkinter import ttk
from pathlib import Path


MODEL_NAME = "small"
MODEL_REPO = "Systran/faster-whisper-small"
MODEL_DIR_NAME = f"models--Systran--faster-whisper-{MODEL_NAME}"


_MIN_MODEL_BIN_BYTES = 50 * 1024 * 1024  # 50 MB — partial downloads are < this


def _model_exists(models_dir: Path) -> bool:
    snap = models_dir / MODEL_DIR_NAME / "snapshots"
    if not snap.exists():
        return False
    for s in snap.iterdir():
        if not s.is_dir():
            continue
        mb = s / "model.bin"
        if mb.exists() and mb.stat().st_size >= _MIN_MODEL_BIN_BYTES:
            return True
    return False


def _download_with_progress(models_dir: Path, progress_cb, status_cb):
    """Download model, calling progress_cb(0..100) and status_cb(str)."""
    import os
    import requests
    from huggingface_hub import hf_hub_download, snapshot_download
    from huggingface_hub import logging as hf_logging
    hf_logging.set_verbosity_error()

    # Disable XET (content-addressed store) so files land directly in cache_dir
    os.environ["HF_HUB_DISABLE_XET"] = "1"

    status_cb("Подключение к HuggingFace...")
    try:
        # Download small metadata files first
        snapshot_download(
            MODEL_REPO,
            cache_dir=str(models_dir),
            ignore_patterns=["model.bin"],
            local_files_only=False,
        )

        # Download model.bin with progress (it's ~460 MB)
        status_cb("Скачивается model.bin (~460 МБ)...")
        snap_dir = _find_snapshot_dir(models_dir)
        if snap_dir is None:
            raise RuntimeError("Не удалось создать директорию модели")

        # Get direct download URL
        from huggingface_hub import hf_hub_url
        url = hf_hub_url(MODEL_REPO, "model.bin")
        dest = snap_dir / "model.bin"

        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        progress_cb(int(min(downloaded * 100 / total_size, 99)))

        progress_cb(100)
        status_cb("Готово!")
    except Exception as e:
        status_cb(f"Ошибка: {e}")
        raise


def _find_snapshot_dir(models_dir: Path):
    """Return the snapshot hash directory, creating structure if needed."""
    snap_root = models_dir / MODEL_DIR_NAME / "snapshots"
    snap_root.mkdir(parents=True, exist_ok=True)
    dirs = [d for d in snap_root.iterdir() if d.is_dir()]
    if dirs:
        return dirs[0]
    # Fetch the commit hash from HF and create the directory
    try:
        import requests
        r = requests.get(
            f"https://huggingface.co/api/models/{MODEL_REPO}/revision/main",
            timeout=10,
        )
        r.raise_for_status()
        sha = r.json().get("sha", "main")
        d = snap_root / sha
        d.mkdir(exist_ok=True)
        return d
    except Exception:
        d = snap_root / "main"
        d.mkdir(exist_ok=True)
        return d


def check_and_download_model(models_dir: Path) -> bool:
    """
    If model already exists, return True immediately.
    Otherwise show a tkinter download window (blocking, runs in main thread).
    Returns True if model is ready, False if download failed.
    """
    if _model_exists(models_dir):
        return True

    result = [False]
    error = [None]

    root = tk.Tk()
    root.title("Спичка — Первый запуск")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    font = ("Segoe UI", 10)
    pad = {"padx": 20, "pady": 6}

    tk.Label(root, text="Спичка", font=("Segoe UI", 14, "bold")).pack(**pad)
    tk.Label(
        root,
        text="Скачивается модель распознавания речи Whisper\n(~464 МБ, только при первом запуске)",
        font=font, justify="center"
    ).pack(**pad)

    status_var = tk.StringVar(value="Подготовка...")
    tk.Label(root, textvariable=status_var, font=("Segoe UI", 9), fg="gray").pack(padx=20)

    progress_var = tk.DoubleVar(value=0)
    bar = ttk.Progressbar(root, variable=progress_var, maximum=100, length=380)
    bar.pack(padx=20, pady=8)

    pct_var = tk.StringVar(value="0%")
    tk.Label(root, textvariable=pct_var, font=font).pack(pady=2)

    root.update()

    def _update_progress(pct):
        progress_var.set(pct)
        pct_var.set(f"{pct}%")
        root.update_idletasks()

    def _update_status(msg):
        status_var.set(msg)
        root.update_idletasks()

    def _run():
        try:
            _download_with_progress(models_dir, _update_progress, _update_status)
            result[0] = True
        except Exception as e:
            error[0] = str(e)
        finally:
            root.after(800, root.destroy)

    threading.Thread(target=_run, daemon=True).start()
    root.mainloop()

    if error[0]:
        import tkinter.messagebox as mb
        mb.showerror(
            "Спичка",
            f"Не удалось скачать модель:\n{error[0]}\n\n"
            "Проверьте интернет-соединение и запустите снова."
        )
        return False

    return result[0]
