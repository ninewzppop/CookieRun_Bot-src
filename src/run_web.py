import os
import sys

# Ensure UTF-8 output encoding on Windows
if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr is not None:
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import socket
import threading
import time
import webbrowser
import uvicorn

def find_free_port(start_port=8000, max_attempts=30):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return start_port

def open_browser(port):
    time.sleep(1.0)
    url = f"http://127.0.0.1:{port}"
    print(f"\n🌐 กำลังเปิดหน้าเว็บ Web Dashboard ที่ {url}...")
    try:
        os.system(f'start {url}')
    except Exception:
        try:
            webbrowser.open(url)
        except Exception:
            pass

if __name__ == "__main__":
    port = find_free_port(8000)

    print("=" * 60)
    print("🍪 CookieRun Classic Bot - Web Dashboard")
    print("=" * 60)
    print(f"🚀 เซิร์ฟเวอร์เริ่มทำงานแล้วที่: http://127.0.0.1:{port}")
    print(f"💡 สามารถเปิดดูบนมือถือผ่าน Wi-Fi เดียวกันได้")
    print("=" * 60)

    # Launch browser automatically in background
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # Run FastAPI app
    uvicorn.run("web_server:app", host="0.0.0.0", port=port, reload=False, log_level="warning")
