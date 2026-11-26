"""程序入口：带参数时走命令行模式，否则打开图形界面。"""
import sys


def _main():
    argv = [a for a in sys.argv[1:] if not a.startswith("-psn_")]
    if argv:
        from printer_setup.cli import main

        sys.exit(main(argv))
    from printer_setup.gui import main

    main()


if __name__ == "__main__":
    _main()
