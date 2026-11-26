import shutil
import subprocess

import pytest

from printer_setup import config
from printer_setup.models import Options
from printer_setup.platform_mac import (
    build_root_script, find_queues_for, parse_lpstat_v, queue_name, uri_host,
)

LPSTAT = """device for TOSHIBA_172_16_5_251_50081: socket://172.16.5.251:50081
device for Old_Front: lpd://172.16.5.251/print
device for Other: ipp://172.16.5.25/ipp/print
device for Kitchen: dnssd://Kitchen._ipp._tcp.local./?uuid=1
"""


def test_queue_name():
    assert queue_name("172.16.5.251", 50081) == "TOSHIBA_172_16_5_251_50081"


def test_parse_and_find():
    devices = parse_lpstat_v(LPSTAT)
    assert len(devices) == 4
    assert uri_host(devices["Other"]) == "172.16.5.25"
    q = find_queues_for("172.16.5.251", "TOSHIBA_172_16_5_251_50081", devices)
    assert q == ["Old_Front", "TOSHIBA_172_16_5_251_50081"]


@pytest.mark.parametrize("mode", [config.MODE_NEW, config.MODE_REPAIR])
@pytest.mark.parametrize("duplex", [False, True])
def test_script_syntax(tmp_path, mode, duplex):
    opts = Options(name="前台 打印机'x", mode=mode, duplex=duplex)
    s = build_root_script(opts, queue_name(opts.ip, opts.port), ["Old Front"], "/tmp/a b.dmg.gz",
                          str(tmp_path), install_driver=True)
    assert "socket://172.16.5.251:50081" in s
    assert ("Duplex=DuplexNoTumble" if duplex else "Duplex=None") in s
    assert ("lpadmin -x 'Old Front'" in s) == (mode == config.MODE_REPAIR)
    if shutil.which("bash"):
        p = tmp_path / "s.sh"
        p.write_text(s, encoding="utf-8")
        r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
