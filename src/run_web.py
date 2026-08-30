# -*- coding: utf-8 -*-
import os
import sys

# Ensure UTF-8 output encoding on Windows (กัน garbled)
if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr is not None:
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import argparse
import atexit
import signal
import socket
import subprocess
import threading
import time
import webbrowser

# ui_console — pretty terminal (fallback ถ้ายังไม่ได้ลง library)
HAS_UI = False
try:
    import ui_console  # type: ignore

    HAS_UI = True
    try:
        ui_console.ensure_utf8_stdout()
    except Exception:
        pass
except ImportError:
    ui_console = None  # type: ignore


LOCK_FILE = "/tmp/cookierun_bot.lock"
if os.name == "nt":
    LOCK_FILE = os.path.join(os.environ.get("TEMP", "/tmp"), "cookierun_bot.lock")


def _pid_alive(pid: int) -> bool:
    """เช็คว่า PID ยังทำงานอยู่จริงไหม (cross-platform)"""
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return False
            ctypes.windll.kernel32.CloseHandle(h)
            return True
        os.kill(pid, 0)  # Unix: signal 0 = probe ว่ามี process อยู่ไหม
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _port_owner(port: int) -> int | None:
    """หา PID ของ process ที่กำลัง listen ที่ port นี้ (ถ้าเจอ)"""
    try:
        if os.name == "nt":
            out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=10).stdout
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0] in ("TCP", "TCP6") and "LISTENING" in parts:
                    if parts[1].endswith(f":{port}"):
                        return int(parts[4])
        else:
            out = subprocess.run(
                ["lsof", "-tiTCP:" + str(port), "-sTCP:LISTEN"],
                capture_output=True, text=True, timeout=10,
            ).stdout
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    return int(line)
    except Exception:
        pass
    return None


def check_port_available(port: int) -> None:
    """เช็ค port ก่อนเริ่ม — ถ้าถูกใช้อยู่ error ชัดเจนทันที ไม่เลื่อน port เอง"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # SO_REUSEADDR: ข้าม TIME_WAIT ค้างจาก server เก่า — แต่ยังตรวจจับ
        # port ที่มี process อื่น LISTEN อยู่ได้จริง (บน macOS/Linux)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return  # port ว่าง ใช้ได้
        except OSError:
            pass
    pid = _port_owner(port)
    owner = f" โดย PID {pid}" if pid else ""
    kill_hint = f" (kill {pid})" if pid else ""
    print()
    print(f"⚠️  Port {port} ถูกใช้งานอยู่แล้ว{owner} กรุณาปิด process เดิมก่อน{kill_hint} หรือระบุ port อื่นด้วย --port")
    print(f"    เช่น:  python3 run_web.py --port {port + 1}")
    sys.exit(1)


def _acquire_lock(port: int) -> None:
    """สร้าง lock file กันรันซ้ำ — ถ้ามี server ตัวอื่นค้างอยู่ ปฏิเสธทันที"""
    if os.path.exists(LOCK_FILE):
        old_pid = 0
        old_port = 0
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                parts = f.read().strip().split()
            old_pid = int(parts[0]) if parts and parts[0].isdigit() else 0
            old_port = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        except Exception:
            pass
        if _pid_alive(old_pid):
            at_port = f" ที่ port {old_port}" if old_port else ""
            print()
            print(f"⚠️  มี Web Dashboard ตัวอื่นกำลังรันอยู่แล้ว (PID {old_pid}{at_port})")
            print(f"    กรุณาปิดตัวเดิมก่อน:  kill {old_pid}   แล้วค่อยรันใหม่")
            sys.exit(1)
        try:
            os.remove(LOCK_FILE)  # lock เก่าค้าง (process ตายแล้ว) — ลบได้
        except OSError:
            pass
    with open(LOCK_FILE, "w", encoding="utf-8") as f:
        f.write(f"{os.getpid()} {port}\n")


def _release_lock() -> None:
    """ลบ lock เฉพาะเมื่อเป็นของตัวเอง (ปิดปกติ Ctrl+C / SIGTERM / exit ใดๆ)"""
    try:
        if not os.path.exists(LOCK_FILE):
            return
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            parts = f.read().strip().split()
        if parts and parts[0].isdigit() and int(parts[0]) == os.getpid():
            os.remove(LOCK_FILE)
    except Exception:
        pass


def _handle_sigterm(signum, frame):
    _release_lock()
    sys.exit(0)


def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


def open_browser(port):
    time.sleep(1.2)
    url = f"http://127.0.0.1:{port}"
    msg = f"กำลังเปิดหน้าเว็บ Web Dashboard ที่ {url}..."
    if HAS_UI and ui_console is not None:
        try:
            ui_console.print_info(f"🌐 {msg}")
        except Exception:
            print(f"\n🌐 {msg}")
    else:
        print(f"\n🌐 {msg}")
    # Windows: start, macOS: open, Linux: xdg-open — ลองตามลำดับ
    opened = False
    # Windows
    if os.name == "nt":
        try:
            os.system(f'start "" "{url}"')
            opened = True
        except Exception:
            pass
    # macOS
    if not opened and sys.platform == "darwin":
        try:
            os.system(f'open "{url}"')
            opened = True
        except Exception:
            pass
    if not opened:
        try:
            webbrowser.open(url)
        except Exception:
            pass


def _check_required_packages() -> list[str]:
    """เช็คว่า package หลักครบไหม — คืน list ที่ขาด."""
    missing: list[str] = []
    checks = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("requests", "requests"),
        ("cv2", "opencv-python"),
        ("numpy", "numpy"),
    ]
    for mod, pip_name in checks:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pip_name)
    return missing


if __name__ == "__main__":
    # ---------- Parse args: port ----------
    parser = argparse.ArgumentParser(description="CookieRun Bot Web Dashboard")
    parser.add_argument("--port", type=int, default=8000, help="port ที่จะใช้รัน Dashboard (default: 8000)")
    args = parser.parse_args()
    port = args.port

    # ---------- Port check + lock (กันรันซ้ำ / port ชน) ----------
    check_port_available(port)
    _acquire_lock(port)
    atexit.register(_release_lock)
    signal.signal(signal.SIGTERM, _handle_sigterm)

    # ---------- Banner ----------
    version = "v2.0"
    if HAS_UI and ui_console is not None:
        try:
            version = ui_console.get_version("v2.0")
        except Exception:
            pass
        try:
            ui_console.print_banner(subtitle="Web Dashboard", version=version)
            print()
        except Exception:
            print("=" * 60)
            print("🍪 CookieRun Classic Bot - Web Dashboard")
            print("=" * 60)
    else:
        print("=" * 60)
        print("🍪 CookieRun Classic Bot - Web Dashboard")
        print("=" * 60)

    # ---------- Gather info for dashboard panel ----------
    adb_path = "adb"
    adb_ok = False
    try:
        from adb import get_adb_path  # type: ignore

        adb_path = get_adb_path()
        # ถ้าไม่ใช่ "adb" เฉยๆ ถือว่าเจอ path จริงหรือ which เจอ
        adb_ok = bool(adb_path and adb_path != "adb")
        # ถ้าเป็น path จริง เช็คว่าไฟล์มีอยู่
        if adb_path and adb_path != "adb":
            try:
                adb_ok = os.path.isfile(adb_path)
            except Exception:
                adb_ok = True
        else:
            # which adb เจอก็ถือว่า ok
            import shutil

            adb_ok = shutil.which("adb") is not None
            if adb_ok:
                adb_path = shutil.which("adb") or "adb"
    except Exception as e:
        adb_path = f"not found ({e})"
        adb_ok = False

    instances = []
    try:
        import config  # type: ignore

        devs = getattr(config, "DEVICES", None)
        if isinstance(devs, list):
            instances = devs
    except Exception:
        instances = []

    lan_ip = get_lan_ip()

    # ---------- Pretty info panel ----------
    if HAS_UI and ui_console is not None:
        try:
            ui_console.print_dashboard_info(port=port, adb_path=adb_path, version=version, instances=instances, lan_ip=lan_ip)
            print()
        except Exception:
            # fallback plain
            print(f"🚀 เซิร์ฟเวอร์: http://127.0.0.1:{port}  (LAN: http://{lan_ip}:{port})")
            print(f"🔧 ADB: {adb_path}  {'✓' if adb_ok else '✗'}")
            print(f"📱 Instances: {len(instances)}")
    else:
        print(f"🚀 เซิร์ฟเวอร์: http://127.0.0.1:{port}  (LAN: http://{lan_ip}:{port})")
        print(f"🔧 ADB: {adb_path}  {'✓' if adb_ok else '✗'}")
        print(f"📱 Instances: {len(instances)}")
        print("=" * 60)

    # ---------- Checks: missing packages ----------
    missing = _check_required_packages()
    if missing:
        detail = "ขาด package: " + ", ".join(missing) + "\n\nต้องติดตั้งก่อนถึงจะรัน Dashboard ได้"
        hint = "รัน:  pip install -r requirements.txt   หรือดับเบิลคลิก INSTALL.bat / ./INSTALL.sh"
        if HAS_UI and ui_console is not None:
            try:
                ui_console.print_error_box("❌ Packages ไม่ครบ", detail, hint)
            except Exception:
                print(f"[ERROR] Packages missing: {', '.join(missing)}")
                print(f"Hint: {hint}")
        else:
            print(f"[ERROR] Packages missing: {', '.join(missing)}")
            print(f"Hint: {hint}")
        sys.exit(1)

    # ---------- ADB warning (ไม่ fatal แต่แจ้งให้เด่น) ----------
    if not adb_ok:
        detail = f"ไม่พบ ADB ที่ {adb_path}\nบอทยังรัน Dashboard ได้ แต่จะเชื่อมต่อ Emulator ไม่ได้จนกว่าจะตั้งค่า ADB ให้ถูกต้อง"
        hint = "ติดตั้ง ADB หรือตั้งค่า ADB_PATH env, หรือลง Emulator (MuMu/LDPlayer) ที่มี adb.exe"
        if HAS_UI and ui_console is not None:
            try:
                ui_console.print_warning("⚠ ADB not found — Dashboard จะยังเปิดได้ แต่เชื่อมต่อจอไม่ได้")
                # แสดงกล่องเหลือง/แดงแบบ warning (ใช้ error_box แต่โทนเหลืองถ้าได้)
                # ที่นี่ใช้ print_warning แบบบรรทัดเดียวพอ ไม่ block
                print(ui_console.c_gray(f"   ADB path tried: {adb_path}"))
            except Exception:
                print(f"[WARN] ADB not found: {adb_path}")
        else:
            print(f"[WARN] ADB not found: {adb_path}")

    # ---------- Launch browser ----------
    if HAS_UI and ui_console is not None:
        try:
            ui_console.print_info(f"⚡ กำลังเริ่มเซิร์ฟเวอร์ที่ 0.0.0.0:{port} ...")
            ui_console.print_info(f"🍪 เปิด Dashboard: http://127.0.0.1:{port}")
            if lan_ip:
                ui_console.print_info(f"📱 บนมือถือ (Wi-Fi เดียวกัน): http://{lan_ip}:{port}")
        except Exception:
            print(f"⚡ Starting server at 0.0.0.0:{port} ...")
    else:
        print(f"⚡ Starting server at 0.0.0.0:{port} ...")
        print(f"🍪 Dashboard: http://127.0.0.1:{port}")

    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # ---------- Run FastAPI ----------
    try:
        import uvicorn  # type: ignore

        # ใช้ log_level warning เพื่อไม่ให้ log รก — แต่ถ้าต้องการดู log ให้เปลี่ยนเป็น info
        # timeout_graceful_shutdown: กัน SIGTERM/ปิดแล้วค้าง (lock file จะถูกลบโดย atexit)
        uvicorn.run("web_server:app", host="0.0.0.0", port=port, reload=False, log_level="warning", timeout_graceful_shutdown=5)
    except ImportError as e:
        detail = f"ไม่พบ package: {e}\nต้องติดตั้ง dependencies ก่อน"
        hint = "pip install -r requirements.txt  หรือรัน INSTALL.bat"
        if HAS_UI and ui_console is not None:
            try:
                ui_console.print_error_box("❌ Uvicorn/FastAPI ไม่พร้อม", detail, hint)
            except Exception:
                print(f"[ERROR] {detail}")
        else:
            print(f"[ERROR] {detail}")
        sys.exit(1)
    except OSError as e:
        # port ชน หรือ bind ไม่ได้
        detail = f"ไม่สามารถเปิดพอร์ต {port} ได้: {e}"
        hint = "ลองปิดโปรแกรมที่ใช้พอร์ตนี้อยู่ หรือรีสตาร์ทเครื่อง"
        if HAS_UI and ui_console is not None:
            try:
                ui_console.print_error_box("❌ Port error", detail, hint)
            except Exception:
                print(f"[ERROR] {detail}")
        else:
            print(f"[ERROR] {detail}")
        sys.exit(1)
    except KeyboardInterrupt:
        _release_lock()
        if HAS_UI and ui_console is not None:
            try:
                ui_console.print_warning("⏹ Stopped by user (Ctrl+C)")
            except Exception:
                print("\nStopped by user")
        else:
            print("\nStopped by user")
        sys.exit(0)
    except Exception as e:
        # กัน stack trace ยาวกระจัดกระจาย — แสดงกล่องแดงสั้นๆ แทน
        import traceback

        tb_short = traceback.format_exc().splitlines()[-6:]
        detail = f"{type(e).__name__}: {e}\n" + "\n".join(tb_short)
        hint = "ดู logs ด้านบน หรือรันด้วย log_level='info' เพื่อ debug เพิ่ม"
        if HAS_UI and ui_console is not None:
            try:
                ui_console.print_error_box("❌ Dashboard failed to start", detail, hint)
            except Exception:
                print(f"[ERROR] {detail}")
        else:
            print(f"[ERROR] {detail}")
            traceback.print_exc()
        sys.exit(1)
