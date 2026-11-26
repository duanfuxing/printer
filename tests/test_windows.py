import shutil
import subprocess
import sys

import pytest

from printer_setup import platform_win
from printer_setup.platform_win import port_name, rewrite_cfg

CFG = "PRINTER_NAME=UNIV on MFP16002225\nPORT_NAME=MFP16002225\nDEFAULT_PRINTER=Y\nMODE=SILENT\nQUEUE=print\n"


def test_rewrite_cfg():
    out = rewrite_cfg(CFG, {"PRINTER_NAME": "TMP", "PORT_NAME": "1.2.3.4", "DEFAULT_PRINTER": "N", "NEW": "1"})
    lines = out.split("\r\n")
    assert "PRINTER_NAME=TMP" in lines
    assert "PORT_NAME=1.2.3.4" in lines
    assert "DEFAULT_PRINTER=N" in lines
    assert "QUEUE=print" in lines
    assert "NEW=1" in lines


def test_port_name():
    assert port_name("172.16.5.251", 9100) == "IP_172.16.5.251_9100"


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")
def test_powershell_script_parses(tmp_path):
    p = tmp_path / "s.ps1"
    p.write_text(platform_win.PS_SCRIPT, encoding="utf-8-sig")
    cmd = (
        "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile('%s',[ref]$null,[ref]$e) | Out-Null;"
        " if ($e.Count) { $e | ForEach-Object { $_.Message }; exit 1 }" % p
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")
def test_powershell_find_driver_runs(tmp_path):
    ps = platform_win.PowerShell(tmp_path)
    ps.run("list-drivers", check=True)
    ps.run("exists", check=True, name="__not_exists__")
