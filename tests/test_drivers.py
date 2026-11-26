import zipfile

from printer_setup import config
from printer_setup.resources import driver_file


def test_windows_driver_zip():
    with zipfile.ZipFile(driver_file(config.WIN_DRIVER_ZIP)) as zf:
        names = zf.namelist()
    assert config.WIN_SETUP_EXE in names and config.WIN_SETUP_CFG in names


def test_mac_driver_zip():
    with zipfile.ZipFile(driver_file(config.MAC_DRIVER_ZIP)) as zf:
        assert config.MAC_DMG_MEMBER in zf.namelist()
