"""图形界面（tkinter）。"""
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from . import config, installer
from .models import Options, SetupError
from .resources import is_windows, log_file_path
from .validate import validate


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q = queue.Queue()
        self.busy = False
        self.log_fh = None

        root.title("%s v%s" % (config.APP_TITLE, config.VERSION))
        root.minsize(560, 600)
        pad = {"padx": 12, "pady": 6}

        header = ttk.Frame(root)
        header.pack(fill="x", **pad)
        ttk.Label(header, text=config.APP_TITLE, font=("", 18, "bold")).pack(anchor="w")
        ttk.Label(header, text="适用型号：" + config.PRINTER_MODEL, foreground="#666").pack(anchor="w")

        form = ttk.LabelFrame(root, text="打印机参数")
        form.pack(fill="x", **pad)
        self.var_name = tk.StringVar(value=config.DEFAULT_NAME)
        self.var_ip = tk.StringVar(value=config.DEFAULT_IP)
        self.var_port = tk.StringVar(value=str(config.DEFAULT_PORT))
        for row, (label, var) in enumerate(
            [("名称", self.var_name), ("IP 地址", self.var_ip), ("端口", self.var_port)]
        ):
            ttk.Label(form, text=label + "：").grid(row=row, column=0, sticky="e", padx=8, pady=4)
            ttk.Entry(form, textvariable=var, width=32).grid(row=row, column=1, sticky="we", padx=8, pady=4)
        form.columnconfigure(1, weight=1)

        mode = ttk.LabelFrame(root, text="模式")
        mode.pack(fill="x", **pad)
        self.var_mode = tk.StringVar(value=config.MODE_NEW)
        ttk.Radiobutton(mode, text="新连接：安装驱动并添加打印机", value=config.MODE_NEW,
                        variable=self.var_mode).pack(anchor="w", padx=8, pady=2)
        ttk.Radiobutton(mode, text="修复：删除指向该 IP 的所有旧打印机，重启打印服务后重新安装",
                        value=config.MODE_REPAIR, variable=self.var_mode).pack(anchor="w", padx=8, pady=2)

        opt = ttk.LabelFrame(root, text="选项")
        opt.pack(fill="x", **pad)
        self.var_default = tk.BooleanVar(value=True)
        self.var_test = tk.BooleanVar(value=False)
        self.var_duplex = tk.BooleanVar(value=False)
        row = ttk.Frame(opt)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Checkbutton(row, text="设为默认打印机", variable=self.var_default).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(row, text="安装后打印测试页", variable=self.var_test).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(row, text="默认双面打印", variable=self.var_duplex).pack(side="left")

        btns = ttk.Frame(root)
        btns.pack(fill="x", **pad)
        self.btn_start = ttk.Button(btns, text="开始", command=self.start)
        self.btn_start.pack(side="right")
        self.status = ttk.Label(btns, text="就绪")
        self.status.pack(side="left")

        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.pack(fill="x", padx=12)

        self.text = ScrolledText(root, height=14, state="disabled", wrap="word")
        self.text.pack(fill="both", expand=True, **pad)

        footer = ttk.Label(root, text=config.CONTACT, foreground="#c0392b", font=("", 12, "bold"))
        footer.pack(pady=(0, 10))

        self.root.after(100, self._drain)

    # ---------- 线程间通信 ----------
    def log(self, msg):
        self.q.put(("log", str(msg)))

    def step(self, title):
        self.q.put(("step", title))

    def _write(self, line):
        self.text.configure(state="normal")
        self.text.insert("end", line + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")
        if self.log_fh:
            self.log_fh.write(line + "\n")
            self.log_fh.flush()

    def _drain(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self._write(data)
                elif kind == "step":
                    self.status.configure(text=data + " ...")
                    self._write("【%s】" % data)
                elif kind == "done":
                    self._finish(*data)
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    # ---------- 动作 ----------
    def _options(self) -> Options:
        return Options(
            name=self.var_name.get(), ip=self.var_ip.get(), port=self.var_port.get(),
            mode=self.var_mode.get(), set_default=self.var_default.get(),
            test_page=self.var_test.get(), duplex=self.var_duplex.get(),
        )

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.btn_start.configure(state=state)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()

    def _run_bg(self, fn):
        self._set_busy(True)
        try:
            self.log_fh = open(log_file_path(), "a", encoding="utf-8")
        except OSError:
            self.log_fh = None

        def worker():
            try:
                fn()
                self.q.put(("done", (True, None)))
            except SetupError as e:
                self.q.put(("done", (False, str(e))))
            except Exception as e:  # noqa: BLE001
                import traceback

                self.log(traceback.format_exc())
                self.q.put(("done", (False, "未知错误：%s" % e)))

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, ok, err):
        self._set_busy(False)
        if self.log_fh:
            self.log_fh.close()
            self.log_fh = None
        if self._finish_cb:
            self._finish_cb(ok, err)

    _finish_cb = None

    def start(self):
        opts = self._options()
        errors = validate(opts)
        if errors:
            messagebox.showerror(config.APP_TITLE, "\n".join(errors))
            return
        if opts.mode == config.MODE_REPAIR and not messagebox.askyesno(
            config.APP_TITLE,
            "修复模式将删除本机所有指向 %s 的打印机，并清空打印队列，然后重新安装。\n\n确定继续吗？" % opts.ip.strip(),
        ):
            return
        self._write("—" * 30)
        started = time.time()

        def job():
            installer.run(opts, self.log, self.step)

        def done(ok, err):
            if ok:
                self.status.configure(text="完成（用时 %d 秒）" % (time.time() - started))
                messagebox.showinfo(config.APP_TITLE, "打印机「%s」已连接成功！" % opts.name.strip())
            else:
                self.status.configure(text="失败")
                self._write("失败：" + err)
                self._write("日志文件：%s" % log_file_path())
                messagebox.showerror(
                    config.APP_TITLE,
                    "%s\n\n%s\n日志文件：%s" % (err, config.CONTACT, log_file_path()))

        self._finish_cb = done
        self._run_bg(job)


def main():
    if is_windows():
        from . import platform_win

        if not platform_win.is_admin():
            if platform_win.relaunch_as_admin(sys.argv):
                return
            # 用户拒绝授权
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror(config.APP_TITLE, "需要管理员权限才能安装打印机。\n" + config.CONTACT)
            return
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    App(root)
    root.mainloop()
