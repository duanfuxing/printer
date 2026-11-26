import os
import sys
from pathlib import Path


def base_dir() -> Path:
    """PyInstaller 打包后为解压目录，源码运行时为项目根目录。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


def driver_file(name: str) -> Path:
    return base_dir() / "driver" / name


def log_file_path() -> Path:
    import tempfile

    return Path(tempfile.gettempdir()) / "PrinterSetup.log"


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_mac() -> bool:
    return sys.platform == "darwin"


def no_window_flags() -> int:
    if is_windows():
        return 0x08000000  # CREATE_NO_WINDOW
    return 0


def clean_env(**extra) -> dict:
    env = dict(os.environ)
    env.update({k: str(v) for k, v in extra.items()})
    return env
