"""Windows 实现：essetup 静默安装驱动 + PowerShell 配置端口/打印机。"""
import json
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

from . import config
from .models import Options, SetupError
from .resources import clean_env, driver_file, no_window_flags

PS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$A = $env:PRINTER_SETUP_ARGS | ConvertFrom-Json
$action = $env:PRINTER_SETUP_ACTION

function Say($m) { Write-Output $m }

function Test-PortMatchesIp($port, $ip) {
    if ($null -eq $port) { return $false }
    if ($port.PrinterHostAddress -eq $ip) { return $true }
    $pattern = '(^|[^0-9])' + [regex]::Escape($ip) + '([^0-9]|$)'
    if ($port.Name -match $pattern) { return $true }
    return $false
}

function Remove-PrinterSafe($name) {
    Get-PrintJob -PrinterName $name -ErrorAction SilentlyContinue | Remove-PrintJob -ErrorAction SilentlyContinue
    Remove-Printer -Name $name
}

function Get-TargetPrinterCim($name) {
    $p = Get-CimInstance -ClassName Win32_Printer | Where-Object { $_.Name -eq $name } | Select-Object -First 1
    if (-not $p) { throw "找不到打印机：$name" }
    return $p
}

try {
    switch ($action) {
        'find-driver' {
            if ($A.tmp_printer) {
                $p = Get-Printer -Name $A.tmp_printer -ErrorAction SilentlyContinue
                if ($p) { Say ("DRIVER=" + $p.DriverName); break }
            }
            $drivers = @(Get-PrinterDriver -ErrorAction SilentlyContinue)
            $d = $drivers | Where-Object { $_.Name -like '*TOSHIBA*Universal*' } | Select-Object -First 1
            if (-not $d) { $d = $drivers | Where-Object { $_.Name -like '*TOSHIBA*' } | Select-Object -First 1 }
            if ($d) { Say ("DRIVER=" + $d.Name) }
        }
        'list-drivers' {
            Get-PrinterDriver -ErrorAction SilentlyContinue | ForEach-Object { Say ("  驱动：" + $_.Name) }
        }
        'remove-by-ip' {
            $ports = @(Get-PrinterPort -ErrorAction SilentlyContinue)
            $matchPorts = @($ports | Where-Object { Test-PortMatchesIp $_ $A.ip } | ForEach-Object { $_.Name })
            $printers = @(Get-Printer -ErrorAction SilentlyContinue | Where-Object { ($matchPorts -contains $_.PortName) -or ($_.Name -eq $A.name) })
            foreach ($p in $printers) {
                Say "删除打印机：$($p.Name)（端口 $($p.PortName)）"
                Remove-PrinterSafe $p.Name
            }
            foreach ($n in $matchPorts) {
                try { Remove-PrinterPort -Name $n -ErrorAction Stop; Say "删除端口：$n" }
                catch { Say "端口 $n 暂时无法删除：$($_.Exception.Message)" }
            }
            if ($printers.Count -eq 0 -and $matchPorts.Count -eq 0) { Say "没有发现指向 $($A.ip) 的旧打印机" }
        }
        'restart-spooler' {
            Stop-Service -Name Spooler -Force
            Remove-Item "$env:SystemRoot\System32\spool\PRINTERS\*" -Force -Recurse -ErrorAction SilentlyContinue
            Start-Service -Name Spooler
            Start-Sleep -Seconds 2
            Say "打印后台服务已重启，打印队列已清空"
        }
        'remove-printer' {
            $p = Get-Printer -Name $A.name -ErrorAction SilentlyContinue
            if ($p) {
                Remove-PrinterSafe $p.Name
                Say "已删除临时打印机：$($p.Name)"
                $inUse = @(Get-Printer -ErrorAction SilentlyContinue | Where-Object { $_.PortName -eq $p.PortName })
                if ($inUse.Count -eq 0) { Remove-PrinterPort -Name $p.PortName -ErrorAction SilentlyContinue }
            }
        }
        'add-printer' {
            $portName = $A.port_name
            $port = [int]$A.port
            $existing = Get-PrinterPort -Name $portName -ErrorAction SilentlyContinue
            if ($existing -and (($existing.PrinterHostAddress -ne $A.ip) -or ([int]$existing.PortNumber -ne $port))) {
                Get-Printer -ErrorAction SilentlyContinue | Where-Object { $_.PortName -eq $portName } | ForEach-Object { Remove-PrinterSafe $_.Name }
                Remove-PrinterPort -Name $portName
                $existing = $null
            }
            if (-not $existing) {
                Add-PrinterPort -Name $portName -PrinterHostAddress $A.ip -PortNumber $port
                Say "已创建 TCP/IP 端口：$portName（RAW $($A.ip):$port）"
            } else {
                Say "TCP/IP 端口已存在：$portName"
            }
            if (Get-Printer -Name $A.name -ErrorAction SilentlyContinue) {
                Remove-PrinterSafe $A.name
                Say "已删除同名旧打印机：$($A.name)"
            }
            Add-Printer -Name $A.name -DriverName $A.driver -PortName $portName
            Say "已添加打印机：$($A.name)（驱动 $($A.driver)）"
            try {
                if ($A.duplex) { Set-PrintConfiguration -PrinterName $A.name -DuplexingMode TwoSidedLongEdge; Say "默认打印方式：双面（长边装订）" }
                else { Set-PrintConfiguration -PrinterName $A.name -DuplexingMode OneSided; Say "默认打印方式：单面" }
            } catch { Say "设置单/双面失败（不影响打印）：$($_.Exception.Message)" }
        }
        'set-default' {
            $key = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Windows'
            try { Set-ItemProperty -Path $key -Name LegacyDefaultPrinterMode -Value 1 -Type DWord } catch {}
            $p = Get-TargetPrinterCim $A.name
            $r = Invoke-CimMethod -InputObject $p -MethodName SetDefaultPrinter
            if ($r.ReturnValue -ne 0) { throw "设置默认打印机失败，错误码 $($r.ReturnValue)" }
            Say "已设为默认打印机：$($A.name)"
        }
        'test-page' {
            $p = Get-TargetPrinterCim $A.name
            $r = Invoke-CimMethod -InputObject $p -MethodName PrintTestPage
            if ($r.ReturnValue -ne 0) { throw "打印测试页失败，错误码 $($r.ReturnValue)" }
            Say "测试页已发送"
        }
        'ensure-class-driver' {
            foreach ($n in $A.candidates) {
                if (Get-PrinterDriver -Name $n -ErrorAction SilentlyContinue) { Say ("DRIVER=" + $n); break }
                try {
                    Add-PrinterDriver -Name $n -ErrorAction Stop
                    Say ("DRIVER=" + $n); break
                } catch { Say "系统驱动 $n 不可用：$($_.Exception.Message)" }
            }
        }
        'exists' {
            if (Get-Printer -Name $A.name -ErrorAction SilentlyContinue) { Say "EXISTS=1" } else { Say "EXISTS=0" }
        }
        default { throw "未知操作：$action" }
    }
    exit 0
} catch {
    Write-Output ("ERROR: " + $_.Exception.Message)
    exit 1
}
"""


def port_name(ip: str, port: int) -> str:
    return "IP_%s_%s" % (ip, port)


def rewrite_cfg(text: str, overrides: dict) -> str:
    """覆盖 eSPDUNI.cfg 中的键值，保留其他配置，缺失的键追加到末尾。"""
    lines = text.splitlines()
    seen = set()
    out = []
    for line in lines:
        if "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in overrides:
                out.append("%s=%s" % (key, overrides[key]))
                seen.add(key)
                continue
        out.append(line)
    for key, value in overrides.items():
        if key not in seen:
            out.append("%s=%s" % (key, value))
    return "\r\n".join(out) + "\r\n"


class PowerShell:
    def __init__(self, workdir: Path):
        self.script = workdir / "printer_setup.ps1"
        # UTF-8 BOM：Windows PowerShell 5.1 才能正确识别脚本里的中文
        self.script.write_text(PS_SCRIPT, encoding="utf-8-sig")

    def run(self, action: str, log=None, check=True, timeout=300, **args):
        cmd = [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(self.script),
        ]
        env = clean_env(
            PRINTER_SETUP_ACTION=action,
            PRINTER_SETUP_ARGS=json.dumps(args, ensure_ascii=False),
        )
        r = subprocess.run(
            cmd, env=env, capture_output=True, timeout=timeout,
            creationflags=no_window_flags(),
        )
        out = r.stdout.decode("utf-8", errors="replace").strip()
        err = r.stderr.decode("utf-8", errors="replace").strip()
        lines = [l for l in out.splitlines() if l.strip()]
        if log:
            for l in lines:
                if not l.startswith(("DRIVER=", "EXISTS=")):
                    log("  " + l)
        if check and r.returncode != 0:
            msg = next((l[7:] for l in lines if l.startswith("ERROR: ")), err or out)
            raise SetupError("操作失败（%s）：%s" % (action, msg))
        return lines

    def find_driver(self, tmp_printer=None):
        lines = self.run("find-driver", check=False, tmp_printer=tmp_printer)
        for l in lines:
            if l.startswith("DRIVER="):
                return l[len("DRIVER="):].strip()
        return None


def _install_driver(ps: PowerShell, opts: Options, workdir: Path, log) -> str:
    zip_path = driver_file(config.WIN_DRIVER_ZIP)
    if not zip_path.exists():
        raise SetupError("找不到驱动包：%s" % zip_path)
    log("正在解压驱动包 ...")
    extract = workdir / "driver"
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract)
    exe = extract / config.WIN_SETUP_EXE
    cfg = extract / config.WIN_SETUP_CFG
    cfg.write_text(
        rewrite_cfg(
            cfg.read_text(encoding="ascii", errors="ignore"),
            {
                "PRINTER_NAME": config.WIN_SETUP_TMP_PRINTER,
                "PORT_NAME": opts.ip,
                "DEFAULT_PRINTER": "N",
                "MODE": "SILENT",
            },
        ),
        encoding="ascii",
        newline="",
    )
    log("正在静默安装东芝驱动，可能需要 1-3 分钟，请耐心等待 ...")
    try:
        r = subprocess.run(
            [str(exe)], cwd=str(exe.parent), timeout=900,
            capture_output=True, creationflags=no_window_flags(),
        )
        log("  驱动安装程序已结束（返回码 %s）" % r.returncode)
    except subprocess.TimeoutExpired:
        raise SetupError("驱动安装超时（15 分钟）")

    # 安装程序可能在后台继续运行，轮询等待驱动出现
    deadline = time.time() + 180
    driver = None
    while time.time() < deadline:
        driver = ps.find_driver(tmp_printer=config.WIN_SETUP_TMP_PRINTER)
        if driver:
            break
        time.sleep(3)
    if not driver:
        log("  当前系统中的驱动：")
        ps.run("list-drivers", log=log, check=False)
        raise SetupError("驱动安装后未检测到东芝驱动")
    return driver


def install(opts: Options, log, step) -> None:
    workdir = Path(tempfile.mkdtemp(prefix="printer_setup_"))
    ps = PowerShell(workdir)
    tmp = config.WIN_SETUP_TMP_PRINTER

    if opts.mode == config.MODE_REPAIR:
        step("清理旧打印机")
        ps.run("remove-by-ip", log=log, ip=opts.ip, name=opts.name)
        step("重启打印后台服务")
        ps.run("restart-spooler", log=log)
        ps.run("remove-by-ip", log=log, ip=opts.ip, name=opts.name)

    step("检查驱动")
    if is_arm64():
        log("  检测到 ARM 架构电脑，东芝驱动不支持 ARM，改用 Windows 内置驱动")
        lines = ps.run("ensure-class-driver", log=log, check=False,
                       candidates=config.WIN_ARM_CLASS_DRIVERS)
        driver = next((l[7:].strip() for l in lines if l.startswith("DRIVER=")), None)
        if not driver:
            raise SetupError("找不到可用的 Windows 内置打印驱动（%s）" % "、".join(config.WIN_ARM_CLASS_DRIVERS))
        log("  使用内置驱动：%s" % driver)
    else:
        driver = None if opts.mode == config.MODE_REPAIR else ps.find_driver()
        if driver:
            log("  已安装驱动：%s" % driver)
        else:
            step("安装驱动")
            driver = _install_driver(ps, opts, workdir, log)
            log("  驱动安装成功：%s" % driver)
        ps.run("remove-printer", log=log, check=False, name=tmp)

    step("添加打印机")
    ps.run(
        "add-printer", log=log, ip=opts.ip, port=opts.port, name=opts.name,
        port_name=port_name(opts.ip, opts.port), driver=driver, duplex=opts.duplex,
    )

    if opts.set_default:
        step("设为默认打印机")
        try:
            ps.run("set-default", log=log, name=opts.name)
        except SetupError as e:
            log("  警告：" + str(e))

    if opts.test_page:
        step("打印测试页")
        ps.run("test-page", log=log, name=opts.name)

    # 驱动安装程序可能延迟创建临时打印机，最后再清理一次
    ps.run("remove-printer", log=None, check=False, name=tmp)


def is_arm64() -> bool:
    """判断 Windows 是否为 ARM64（x64 程序在 ARM 上转译运行时也能正确识别）。"""
    import os

    if os.environ.get("PRINTER_SETUP_FORCE_ARM") == "1":  # 测试用
        return True
    try:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.windll.kernel32
        proc, native = wintypes.USHORT(), wintypes.USHORT()
        if k32.IsWow64Process2(k32.GetCurrentProcess(), ctypes.byref(proc), ctypes.byref(native)):
            return native.value == 0xAA64  # IMAGE_FILE_MACHINE_ARM64
    except Exception:
        pass
    arch = os.environ.get("PROCESSOR_ARCHITEW6432") or os.environ.get("PROCESSOR_ARCHITECTURE", "")
    return arch.upper() == "ARM64"


def is_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(argv) -> bool:
    """以管理员身份重新启动自身，成功返回 True（调用方应退出）。"""
    import ctypes
    import subprocess as sp
    import sys

    if getattr(sys, "frozen", False):
        exe, params = sys.executable, argv[1:]
    else:
        exe, params = sys.executable, argv
    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", exe, sp.list2cmdline(params), None, 1
    )
    return rc > 32

