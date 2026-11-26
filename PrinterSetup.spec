# -*- mode: python ; coding: utf-8 -*-
# 用法：pyinstaller PrinterSetup.spec --noconfirm
import sys

IS_WIN = sys.platform.startswith("win")
driver = "driver/windows.zip" if IS_WIN else "driver/mac.zip"

a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=[(driver, "driver")],
    hiddenimports=["printer_setup.platform_win", "printer_setup.platform_mac", "printer_setup.gui"],
    excludes=["pytest"],
)
pyz = PYZ(a.pure)

if IS_WIN:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="PrinterSetup",
        console=False,
        uac_admin=True,   # 启动即请求管理员权限
        upx=False,
    )
else:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="PrinterSetup",
        console=False,
        upx=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="PrinterSetup", upx=False)
    app = BUNDLE(
        coll,
        name="PrinterSetup.app",
        bundle_identifier="com.taidou.printersetup",
        info_plist={
            "CFBundleDisplayName": "打印机连接助手",
            "CFBundleName": "打印机连接助手",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
