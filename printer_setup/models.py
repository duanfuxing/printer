from dataclasses import dataclass

from . import config


@dataclass
class Options:
    name: str = config.DEFAULT_NAME
    ip: str = config.DEFAULT_IP
    port: int = config.DEFAULT_PORT
    mode: str = config.MODE_NEW
    set_default: bool = True
    test_page: bool = False
    duplex: bool = False


class SetupError(Exception):
    """安装过程中的可预期错误，message 直接展示给用户。"""
