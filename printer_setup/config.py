"""全局常量与默认参数。"""

VERSION = "1.0.1"
APP_TITLE = "打印机连接助手"
CONTACT = "如有疑问，请联系太逗技术部"

DEFAULT_NAME = "前台打印机"
DEFAULT_IP = "172.16.5.251"
DEFAULT_PORT = 9100

PRINTER_MODEL = "TOSHIBA e-STUDIO2021AC"

MODE_NEW = "new"
MODE_REPAIR = "repair"

# ---- 驱动包（位于 driver/ 目录，打包时内置） ----
WIN_DRIVER_ZIP = "windows.zip"
WIN_SETUP_EXE = "UNI/essetup.exe"
WIN_SETUP_CFG = "UNI/eSPDUNI.cfg"
# 驱动包内的 INF（优先使用，失败时再用 essetup.exe）
WIN_INF_DIR = "UNI/Driver/64bit"
WIN_INF_FILE = "eSf6u.inf"
WIN_DRIVER_NAME = "TOSHIBA Universal Printer 2"
# 静默安装驱动时临时创建的打印机名称（安装完成后删除）
WIN_SETUP_TMP_PRINTER = "TOSHIBA_SETUP_TMP"
# ARM 版 Windows：东芝驱动只有 x86/x64，改用系统内置的通用驱动（按顺序尝试）
WIN_ARM_CLASS_DRIVERS = ["Microsoft PCL6 Class Driver", "Microsoft PS Class Driver"]

MAC_DRIVER_ZIP = "mac.zip"
MAC_DMG_MEMBER = "CSW2601PPD01/normal/TOSHIBA_ColorMFP.dmg.gz"
MAC_PKG_NAME = "TOSHIBA ColorMFP.pkg"
# e-STUDIO2021AC 对应的 PPD
MAC_PPD_PATH = "/Library/Printers/PPDs/Contents/Resources/TOSHIBA_ColorMFP_S2.gz"
