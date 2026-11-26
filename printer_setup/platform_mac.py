"""macOS 实现：安装东芝 PPD 驱动包 + lpadmin 添加 socket:// 打印机。"""
import os
import re
import shlex
import subprocess
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from . import config
from .models import Options, SetupError
from .resources import clean_env, driver_file


def queue_name(ip: str, port: int) -> str:
    """CUPS 队列名只用 ASCII；用户看到的是 -D 描述（即界面里的“名称”）。"""
    return "TOSHIBA_%s_%s" % (ip.replace(".", "_"), port)


def _c_env():
    return clean_env(LANG="C", LC_ALL="C")


def parse_lpstat_v(output: str) -> dict:
    """解析 `lpstat -v`（LANG=C）输出：{队列名: 设备URI}。"""
    result = {}
    for line in output.splitlines():
        m = re.match(r"^device for (.+?): (.+)$", line.strip())
        if m:
            result[m.group(1)] = m.group(2).strip()
    return result


def uri_host(uri: str):
    try:
        return urlsplit(uri).hostname
    except ValueError:
        return None


def find_queues_for(ip: str, queue: str, devices: dict) -> list:
    return sorted(q for q, uri in devices.items() if q == queue or uri_host(uri) == ip)


def list_devices() -> dict:
    r = subprocess.run(["lpstat", "-v"], capture_output=True, text=True, env=_c_env())
    return parse_lpstat_v(r.stdout)


def build_root_script(opts: Options, queue: str, remove_queues: list,
                      dmg_gz: str, workdir: str, install_driver: bool) -> str:
    q = shlex.quote
    duplex = "DuplexNoTumble" if opts.duplex else "None"
    lines = [
        "#!/bin/bash",
        "set -u",
        "export LANG=C LC_ALL=C",
        "fail() { echo \"ERROR: $*\"; exit 1; }",
        "WORK=%s" % q(workdir),
        "PPD=%s" % q(config.MAC_PPD_PATH),
    ]
    if opts.mode == config.MODE_REPAIR:
        lines.append('echo "@@STEP 清理旧打印机"')
        for rq in remove_queues:
            lines += [
                "cancel -a %s >/dev/null 2>&1" % q(rq),
                "lpadmin -x %s && echo %s" % (q(rq), q("  删除打印机：" + rq)),
            ]
        if not remove_queues:
            lines.append("echo %s" % q("  没有发现指向 %s 的旧打印机" % opts.ip))
        lines += [
            'echo "@@STEP 重启打印服务"',
            "launchctl kickstart -k system/org.cups.cupsd >/dev/null 2>&1 || true",
            "sleep 2",
            "echo %s" % q("  打印服务已重启"),
        ]
    if install_driver:
        lines += [
            'echo "@@STEP 安装驱动"',
            "MNT=\"$WORK/mnt\"; mkdir -p \"$MNT\"",
            "gunzip -c %s > \"$WORK/driver.dmg\" || fail %s" % (q(dmg_gz), q("解压驱动失败")),
            "hdiutil attach -nobrowse -readonly -mountpoint \"$MNT\" \"$WORK/driver.dmg\" >/dev/null || fail %s" % q("挂载驱动镜像失败"),
            "installer -pkg \"$MNT\"/%s -target / ; RC=$?" % q(config.MAC_PKG_NAME),
            "hdiutil detach \"$MNT\" -force >/dev/null 2>&1",
            "[ $RC -eq 0 ] || fail %s" % q("驱动安装失败（installer 返回 $RC）"),
            "echo %s" % q("  驱动安装成功"),
        ]
    lines += [
        '[ -f "$PPD" ] || fail %s' % q("找不到驱动文件 " + config.MAC_PPD_PATH),
        'echo "@@STEP 添加打印机"',
        "lpadmin -p %s -E -v %s -P \"$PPD\" -D %s -L '' -o printer-is-shared=false -o Duplex=%s || fail %s" % (
            q(queue), q("socket://%s:%s" % (opts.ip, opts.port)), q(opts.name), duplex, q("添加打印机失败")),
        "cupsenable %s; cupsaccept %s" % (q(queue), q(queue)),
        "echo %s" % q("  已添加打印机：%s（socket://%s:%s）" % (opts.name, opts.ip, opts.port)),
        "echo %s" % q("  默认打印方式：" + ("双面（长边装订）" if opts.duplex else "单面")),
        "exit 0",
    ]
    return "\n".join(lines) + "\n"


def _applescript_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _emit(line: str, log, step):
    line = line.rstrip("\n")
    if not line:
        return
    if line.startswith("@@STEP "):
        step(line[7:])
    else:
        log(line)


def run_privileged(script_path: str, log, step) -> None:
    """以 root 运行脚本：已是 root 直接执行，否则弹出系统管理员密码框。"""
    if os.geteuid() == 0:
        p = subprocess.Popen(["/bin/bash", script_path], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, env=_c_env())
        for line in p.stdout:
            _emit(line, log, step)
        rc = p.wait()
        err = ""
    else:
        log_path = script_path + ".log"
        open(log_path, "w").close()
        inner = "/bin/bash %s > %s 2>&1" % (shlex.quote(script_path), shlex.quote(log_path))
        osa = 'do shell script %s with administrator privileges with prompt %s' % (
            _applescript_str(inner), _applescript_str("打印机连接助手需要管理员权限来安装驱动和添加打印机"))
        stop = threading.Event()

        def tail():
            pos = 0
            buf = ""
            while True:
                done = stop.is_set()
                with open(log_path, encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    _emit(line, log, step)
                if done:
                    if buf:
                        _emit(buf, log, step)
                    return
                time.sleep(0.3)

        t = threading.Thread(target=tail, daemon=True)
        t.start()
        r = subprocess.run(["osascript", "-e", osa], capture_output=True, text=True)
        stop.set()
        t.join()
        rc, err = r.returncode, r.stderr.strip()
        if rc != 0 and ("-128" in err or "User canceled" in err or "用户已取消" in err):
            raise SetupError("已取消管理员授权")
    if rc != 0:
        raise SetupError("安装脚本执行失败（返回码 %s）%s" % (rc, err))


def set_default(queue: str, log) -> None:
    # 关闭“默认打印机 = 上次使用的打印机”，否则系统会覆盖默认设置
    subprocess.run(["defaults", "write", "org.cups.PrintingPrefs", "UseLastPrinter", "-bool", "false"],
                   capture_output=True)
    r = subprocess.run(["lpoptions", "-d", queue], capture_output=True, text=True, env=_c_env())
    if r.returncode != 0:
        log("  警告：设置默认打印机失败：" + (r.stderr or r.stdout).strip())
    else:
        log("  已设为默认打印机")


def print_test_page(opts: Options, queue: str, log) -> None:
    content = (
        "打印机测试页 / Printer Test Page\n\n"
        "名称：%s\n型号：%s\n地址：%s:%s\n时间：%s\n\n%s\n"
        % (opts.name, config.PRINTER_MODEL, opts.ip, opts.port,
           time.strftime("%Y-%m-%d %H:%M:%S"), config.CONTACT)
    )
    fd, path = tempfile.mkstemp(prefix="printer_test_", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    r = subprocess.run(["lp", "-d", queue, "-t", "测试页", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise SetupError("打印测试页失败：" + (r.stderr or r.stdout).strip())
    log("  测试页已发送：" + r.stdout.strip())


def install(opts: Options, log, step) -> None:
    queue = queue_name(opts.ip, opts.port)
    workdir = tempfile.mkdtemp(prefix="printer_setup_")
    os.chmod(workdir, 0o755)

    remove_queues = []
    if opts.mode == config.MODE_REPAIR:
        remove_queues = find_queues_for(opts.ip, queue, list_devices())

    install_driver = opts.mode == config.MODE_REPAIR or not Path(config.MAC_PPD_PATH).exists()
    step("检查驱动")
    dmg_gz = ""
    if install_driver:
        zip_path = driver_file(config.MAC_DRIVER_ZIP)
        if not zip_path.exists():
            raise SetupError("找不到驱动包：%s" % zip_path)
        log("  正在解压驱动包 ...")
        with zipfile.ZipFile(zip_path) as zf:
            dmg_gz = zf.extract(config.MAC_DMG_MEMBER, workdir)
    else:
        log("  驱动已安装：" + config.MAC_PPD_PATH)

    script = os.path.join(workdir, "setup.sh")
    with open(script, "w", encoding="utf-8") as f:
        f.write(build_root_script(opts, queue, remove_queues, dmg_gz, workdir, install_driver))
    log("  需要管理员权限，请在弹出的窗口中输入电脑密码")
    run_privileged(script, log, step)

    if opts.set_default:
        step("设为默认打印机")
        set_default(queue, log)

    if opts.test_page:
        step("打印测试页")
        print_test_page(opts, queue, log)
