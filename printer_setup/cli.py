"""命令行模式（用于自动化测试 / 批量部署）。"""
import argparse
import sys
import traceback
import zipfile

from . import config
from .models import Options, SetupError
from .resources import driver_file, is_mac, is_windows


def build_parser():
    p = argparse.ArgumentParser(prog="PrinterSetup", description=config.APP_TITLE)
    p.add_argument("--cli", action="store_true", help="不显示界面，直接执行")
    p.add_argument("--self-test", action="store_true", help="检查内置驱动是否完整后退出")
    p.add_argument("--name", default=config.DEFAULT_NAME)
    p.add_argument("--ip", default=config.DEFAULT_IP)
    p.add_argument("--port", type=int, default=config.DEFAULT_PORT)
    p.add_argument("--mode", choices=[config.MODE_NEW, config.MODE_REPAIR], default=config.MODE_NEW)
    p.add_argument("--default", dest="set_default", action="store_true", default=True)
    p.add_argument("--no-default", dest="set_default", action="store_false")
    p.add_argument("--test-page", action="store_true")
    p.add_argument("--duplex", action="store_true")
    p.add_argument("--yes", action="store_true", help="网络检测失败时仍继续")
    p.add_argument("--log-file", help="日志同时写入该文件")
    return p


def self_test(log) -> int:
    if is_windows():
        name, members = config.WIN_DRIVER_ZIP, [config.WIN_SETUP_EXE, config.WIN_SETUP_CFG]
    elif is_mac():
        name, members = config.MAC_DRIVER_ZIP, [config.MAC_DMG_MEMBER]
    else:
        log("unsupported platform")
        return 1
    path = driver_file(name)
    if not path.exists():
        log("SELF-TEST FAIL: missing %s" % path)
        return 1
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        bad = zf.testzip()
    missing = [m for m in members if m not in names]
    if missing or bad:
        log("SELF-TEST FAIL: missing=%s bad=%s" % (missing, bad))
        return 1
    import tkinter  # noqa: F401  确认 Tk 已打包

    log("SELF-TEST OK: %s" % path)
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    fh = open(args.log_file, "a", encoding="utf-8") if args.log_file else None

    def log(msg):
        line = str(msg)
        try:
            print(line, flush=True)
        except Exception:
            pass
        if fh:
            fh.write(line + "\n")
            fh.flush()

    try:
        if args.self_test:
            return self_test(log)
        from . import installer

        opts = Options(name=args.name, ip=args.ip, port=args.port, mode=args.mode,
                       set_default=args.set_default, test_page=args.test_page, duplex=args.duplex)
        installer.run(opts, log, confirm=(lambda _m: True) if args.yes else None)
        log("RESULT: OK")
        return 0
    except SetupError as e:
        log("RESULT: FAIL - %s" % e)
        log(config.CONTACT)
        return 2
    except Exception:
        log(traceback.format_exc())
        log("RESULT: FAIL")
        return 3
    finally:
        if fh:
            fh.close()


if __name__ == "__main__":
    sys.exit(main())
