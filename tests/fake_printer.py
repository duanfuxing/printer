"""CI 用的假打印机：监听 RAW 端口，把收到的数据追加写入文件。"""
import argparse
import socket
import threading


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=50081)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    lock = threading.Lock()
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", a.port))
    srv.listen(16)
    print("fake printer listening on", a.port, flush=True)

    def handle(conn):
        total = 0
        with conn:
            while True:
                data = conn.recv(65536)
                if not data:
                    break
                total += len(data)
                with lock, open(a.out, "ab") as f:
                    f.write(data)
        print("connection closed, %d bytes" % total, flush=True)

    while True:
        c, _ = srv.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()


if __name__ == "__main__":
    main()
