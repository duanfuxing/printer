import ipaddress

from . import config
from .models import Options

_BAD_NAME_CHARS = set('\\,!/"')


def validate(opts: Options) -> list:
    errors = []
    name = (opts.name or "").strip()
    if not name:
        errors.append("名称不能为空")
    elif len(name) > 64:
        errors.append("名称不能超过 64 个字符")
    elif any(c in _BAD_NAME_CHARS for c in name):
        errors.append('名称不能包含以下字符：\\ , ! / "')

    try:
        ipaddress.IPv4Address((opts.ip or "").strip())
    except ValueError:
        errors.append("IP 地址格式不正确，例如：172.16.5.251")

    try:
        port = int(opts.port)
        if not 1 <= port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("端口必须是 1-65535 之间的数字")

    if opts.mode not in (config.MODE_NEW, config.MODE_REPAIR):
        errors.append("未知的模式：%s" % opts.mode)
    return errors


def normalize(opts: Options) -> Options:
    return Options(
        name=opts.name.strip(),
        ip=opts.ip.strip(),
        port=int(opts.port),
        mode=opts.mode,
        set_default=bool(opts.set_default),
        test_page=bool(opts.test_page),
        duplex=bool(opts.duplex),
    )
