# 打印机连接助手

一键连接公司前台打印机（TOSHIBA e-STUDIO2021AC），支持 Windows 和 macOS。

> 如有疑问，请联系太逗技术部

## 下载

在 [Releases](../../releases) 页面下载对应版本：

| 系统 | 文件 |
|---|---|
| Windows 10/11（64 位，含 ARM 电脑） | `PrinterSetup-windows-x64.exe` |
| Mac（M1/M2/M3/M4 芯片） | `PrinterSetup-macos-arm64.zip` |
| Mac（Intel 芯片） | `PrinterSetup-macos-x64.zip` |

> 不确定 Mac 是哪种芯片：点左上角  → 关于本机，查看“芯片”或“处理器”。

## 使用

1. 连接公司网络后打开程序（参数一般保持默认即可）：
   - 名称：`前台打印机`
   - IP：`172.16.5.251`
   - 端口：`9100`
2. 选择模式：
   - **新连接**：安装驱动并添加打印机
   - **修复**：删除本机所有指向该 IP 的旧打印机、清空打印队列并重启打印服务，然后重新安装
3. 按需勾选：设为默认打印机 / 安装后打印测试页 / 默认双面打印
4. 点击 **开始**。程序会自动检测网络和端口（结果显示在日志中），然后进行安装。

### 首次打开提示“无法验证”/“未知发布者”

安装包未做代码签名，属于正常提示：

- **Windows**：出现“Windows 已保护你的电脑”时，点 **更多信息 → 仍要运行**，然后在管理员权限窗口点 **是**。
- **Mac**：解压后右键点击 `PrinterSetup.app` → **打开** → **打开**。
  如果提示“已损坏”，在终端执行：`xattr -dr com.apple.quarantine ~/Downloads/PrinterSetup.app`

安装失败时，日志位于系统临时目录下的 `PrinterSetup.log`，请连同截图发给太逗技术部。

## 实现说明

| | Windows | macOS |
|---|---|---|
| 驱动 | `driver/windows.zip`（东芝通用驱动 L2601，essetup.exe 静默安装）；ARM 电脑改用系统内置 Microsoft PCL6 Class Driver | `driver/mac.zip`（`TOSHIBA_ColorMFP_S2` PPD） |
| 连接 | 标准 TCP/IP 端口 RAW `IP_<ip>_<port>` | `socket://<ip>:<port>` |
| 权限 | 启动时 UAC 提权 | 安装时弹出系统密码框 |

驱动包随程序一起打包，无需联网下载。

## 开发

```bash
pip install -r requirements-dev.txt
python main.py                 # 图形界面
python main.py --cli --help    # 命令行模式（自动化/批量部署）
python -m pytest               # 单元测试
pyinstaller PrinterSetup.spec --noconfirm   # 打包
```

GitHub Actions 会在每次推送时，分别在 Windows x64、macOS arm64 和 macOS x64 上运行单元测试并打包，然后用一台“假打印机”（`tests/fake_printer.py`）做端到端测试：真实安装驱动、添加打印机，执行新连接和修复两种模式，并确认测试页数据已发送到端口。推送 `v*` 标签时会自动发布 Release。
