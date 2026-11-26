from printer_setup import config
from printer_setup.models import Options
from printer_setup.validate import normalize, validate


def test_defaults_valid():
    assert validate(Options()) == []


def test_default_values():
    o = Options()
    assert (o.name, o.ip, o.port) == ("前台打印机", "172.16.5.251", 9100)


def test_bad_inputs():
    errs = validate(Options(name=" ", ip="172.16.5", port="abc", mode="x"))
    assert len(errs) == 4


def test_port_range():
    assert validate(Options(port=0))
    assert validate(Options(port=65536))
    assert not validate(Options(port="9100"))


def test_name_chars():
    assert validate(Options(name="a,b"))
    assert validate(Options(name="a\\b"))


def test_normalize():
    o = normalize(Options(name=" 前台 ", ip=" 10.0.0.1 ", port="9100", mode=config.MODE_REPAIR))
    assert o.name == "前台" and o.ip == "10.0.0.1" and o.port == 9100
