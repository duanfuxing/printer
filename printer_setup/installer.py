"""安装流程编排：校验 -> 网络检测 -> 平台安装。"""
import time

from . import config, netcheck
from .models import Options, SetupError
from .resources import is_mac, is_windows
from .validate import normalize, validate


def run(opts: Options, log, step=None, confirm=None) -> None:
    """
    log(str)        输出日志
    step(str)       步骤标题
    confirm(str)    网络检测失败时询问是否继续，返回 bool；为 None 时直接失败
    """
    step = step or (lambda s: log("== " + s))
    errors = validate(opts)
    if errors:
        raise SetupError("\n".join(errors))
    opts = normalize(opts)

    log("%s v%s  %s" % (config.APP_TITLE, config.VERSION, time.strftime("%Y-%m-%d %H:%M:%S")))
    log("模式：%s；名称：%s；地址：%s:%s" % (
        "修复" if opts.mode == config.MODE_REPAIR else "新连接", opts.name, opts.ip, opts.port))

    step("网络检测")
    if not netcheck.run_checks(opts.ip, opts.port, log):
        msg = ("无法连接打印机 %s:%s。\n请确认电脑已连接公司网络（有线或 Wi-Fi）。\n\n是否仍然继续安装？"
               % (opts.ip, opts.port))
        if not (confirm and confirm(msg)):
            raise SetupError("网络检测失败：无法连接 %s:%s，请检查网络后重试" % (opts.ip, opts.port))
        log("  用户选择忽略网络检测结果，继续安装")

    if is_windows():
        from . import platform_win as impl
    elif is_mac():
        from . import platform_mac as impl
    else:
        raise SetupError("暂不支持当前操作系统")

    impl.install(opts, log, step)
    step("完成")
    log("打印机「%s」已就绪。" % opts.name)
