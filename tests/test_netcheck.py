import socket

from printer_setup.netcheck import check_tcp


def test_open_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    port = s.getsockname()[1]
    ok, _ = check_tcp("127.0.0.1", port)
    s.close()
    assert ok


def test_closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    ok, msg = check_tcp("127.0.0.1", port, timeout=1)
    assert not ok and msg
