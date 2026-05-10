"""Spee4ka launcher — finds embedded Python and starts main.py silently."""
import subprocess
import sys
import os
from pathlib import Path

here = Path(sys.executable).parent  # install dir: %LOCALAPPDATA%\Spee4ka\

# Installed layout: here/python/pythonw.exe + here/app/main.py
# Dev layout (project root): here/.venv/Scripts/pythonw.exe + here/main.py
if (here / "python" / "pythonw.exe").exists():
    python = here / "python" / "pythonw.exe"
    script = here / "app" / "main.py"
    cwd    = here / "app"
elif (here / ".venv" / "Scripts" / "pythonw.exe").exists():
    python = here / ".venv" / "Scripts" / "pythonw.exe"
    script = here / "main.py"
    cwd    = here
else:
    import tkinter, tkinter.messagebox
    tkinter.Tk().withdraw()
    tkinter.messagebox.showerror("Спичка", "Python не найден.\nПереустановите приложение.")
    sys.exit(1)

if not script.exists():
    import tkinter, tkinter.messagebox
    tkinter.Tk().withdraw()
    tkinter.messagebox.showerror("Спичка", "Файл main.py не найден.\nПереустановите приложение.")
    sys.exit(1)

env = os.environ.copy()
for _k in ["TCL_LIBRARY", "TK_LIBRARY", "TCL8_6_DLL", "TK8_6_DLL", "_MEIPASS2"]:
    env.pop(_k, None)

subprocess.Popen(
    [str(python), str(script)],
    cwd=str(cwd),
    env=env,
    creationflags=0x08000000,  # CREATE_NO_WINDOW
)
