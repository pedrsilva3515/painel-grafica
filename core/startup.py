import sys
import winreg
from pathlib import Path

APP_NAME = "PainelGrafica"
_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

# When running as a frozen exe (PyInstaller), use the exe path; otherwise
# build a command that re-launches the script via the current interpreter.
def _app_command() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve())
    script = str(Path(__file__).parent.parent / "main.py")
    return f'"{sys.executable}" "{script}"'


def is_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def enable_startup() -> None:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _app_command())


def disable_startup() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        pass


def toggle_startup() -> bool:
    """Toggle startup registration. Returns the new state (True = enabled)."""
    if is_startup_enabled():
        disable_startup()
        return False
    enable_startup()
    return True
