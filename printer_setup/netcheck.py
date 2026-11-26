"""安装前的网络检测。"""
import socket
import subprocess

from .resources import is_windows, no_window_flags


def check_tcp(ip: str, port: int, timeout: float = 3.0):
    try:
        with socket.create_connection((ip, int(port)), timeout=timeout):
            return True, "端口 %s:%s 连接成功" % (ip, port)
    except socket.timeout:
        return False, "连接 %s:%s 超时" % (ip, port)
    except ConnectionRefusedError:
        return False, "连接 %s:%s 被拒绝（端口未开放）" % (ip, port)
    except OSError as e:
        return False, "无法连接 %s:%s：%s" % (ip, port, e)


def ping(ip: str, timeout_ms: int = 1500) -> bool:
    if is_windows():
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout_ms), ip]
    try:
        r = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_ms / 1000 + 3,
            creationflags=no_window_flags(),
        )
        return r.returncode == 0
    except Exception:
        return False


def run_checks(ip: str, port: int, log) -> bool:
    """返回端口是否可达。ping 仅作参考（部分网络禁 ping）。"""
    log("正在检测网络：ping %s ..." % ip)
    if ping(ip):
        log("  ping 通")
    else:
        log("  ping 不通（部分网络禁止 ping，继续检测端口）")
    log("正在检测打印端口 %s:%s ..." % (ip, port))
    ok, msg = check_tcp(ip, port)
    log("  " + msg)
    return ok
