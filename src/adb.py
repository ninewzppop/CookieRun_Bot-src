import os
import random
import shutil
import subprocess
import time

import cv2
import numpy as np

NO_WINDOW_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

def _run_cmd(cmd_list, **kwargs):
    if "creationflags" not in kwargs and NO_WINDOW_FLAGS:
        kwargs["creationflags"] = NO_WINDOW_FLAGS
    return subprocess.run(cmd_list, **kwargs)



def get_adb_path() -> str:
    """Find adb executable in system PATH or common emulator install locations."""
    if "ADB_PATH" in os.environ and os.path.isfile(os.environ["ADB_PATH"]):
        return os.environ["ADB_PATH"]

    which_adb = shutil.which("adb")
    if which_adb:
        return which_adb

    candidates = [
        os.path.join(os.path.dirname(__file__), "adb.exe"),
        r"C:\Program Files\Netease\MuMuPlayer\nx_device\15.0\shell\adb.exe",
        r"C:\Program Files\Netease\MuMuPlayer\nx_main\adb.exe",
        r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
        r"C:\Program Files\Netease\MuMuPlayer-12.0\nx_main\adb.exe",
        r"C:\LDPlayer\LDPlayer9\adb.exe",
        r"C:\Program Files\LDPlayer\LDPlayer9\adb.exe",
        r"C:\leidian\LDPlayer9\adb.exe",
        r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe",
        r"C:\Program Files\Nox\bin\nox_adb.exe",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path

    return "adb"


def device_check_connection(ip: str, port: int) -> tuple[bool, str]:
    """Test connection to the ADB device without raising exceptions."""
    try:
        adb = get_adb_path()
        result = _run_cmd(
            [adb, "connect", f"{ip}:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        out = (result.stdout + result.stderr).strip()
        if "connected" in out.lower() or "already connected" in out.lower():
            return True, f"Connected to {ip}:{port}"
        return False, out or f"Failed to connect to {ip}:{port}"
    except Exception as e:
        return False, str(e)


def device_connect(ip: str, port: int):
    adb = get_adb_path()
    result = _run_cmd(
        [adb, "connect", f"{ip}:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    print(f"🔌 {result.stdout.strip().capitalize()}")
    if "connected" not in result.stdout.lower() and "already connected" not in result.stdout.lower():
        raise Exception(f"❌ Failed to connect to {ip}:{port}\n{result.stderr.strip()}")


def device_capture_screen(ip: str, port: int):
    adb = get_adb_path()
    result = _run_cmd(
        [adb, "-s", f"{ip}:{port}", "exec-out", "screencap", "-p"],
        stdout=subprocess.PIPE,
        check=True,
    )
    img = np.frombuffer(result.stdout, dtype=np.uint8)
    return cv2.imdecode(img, cv2.IMREAD_COLOR)


def device_tap(ip: str, port: int, x: int, y: int):
    adb = get_adb_path()
    _run_cmd(
        [adb, "-s", f"{ip}:{port}", "shell", "input", "tap", str(x), str(y)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def safe_device_tap(ip: str, port: int, x: int, y: int, duration: int = None):
    # Human-like jitter: gauss(0,9) ±25px ทั่วปุ่ม (เดิม ±15 แคบไป) + 5% outlier ±30
    dx = int(random.gauss(0, 9))
    dy = int(random.gauss(0, 9))
    dx = max(-25, min(25, dx))
    dy = max(-25, min(25, dy))
    if random.random() < 0.05:
        dx = random.randint(-30, 30)
        dy = random.randint(-30, 30)
        dx = max(-30, min(30, dx))
        dy = max(-30, min(30, dy))
    # 2% miss-tap เล็กๆ ก่อนกดจริง (เหมือนคนจิ้มพลาดแล้วแก้)
    if random.random() < 0.02:
        miss_x = max(0, min(1280, x + random.randint(-45, 45)))
        miss_y = max(0, min(720, y + random.randint(-45, 45)))
        adb_miss = get_adb_path()
        _dur_miss = random.randint(65, 120)
        _run_cmd(
            [adb_miss, "-s", f"{ip}:{port}", "shell", "input", "swipe",
             str(miss_x), str(miss_y), str(miss_x), str(miss_y), str(_dur_miss)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        time.sleep(random.uniform(0.12, 0.28))
    jitter_x = max(0, min(1280, x + dx))
    jitter_y = max(0, min(720, y + dy))
    # ใช้ swipe มี duration แทน tap 0ms — กันจับ synthetic 0ms
    # Jump/Skill: Hold 60-120ms ตามวิจัย CookieRun (Point-touch ซ้ายล่าง)
    if duration is None:
        duration = random.randint(60, 120)
    adb = get_adb_path()
    _run_cmd(
        [adb, "-s", f"{ip}:{port}", "shell", "input", "swipe",
         str(jitter_x), str(jitter_y), str(jitter_x), str(jitter_y), str(duration)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def safe_device_long_press(ip: str, port: int, x: int, y: int, duration_ms: int = 800):
    """
    กดค้างที่จุด (x, y) นาน duration_ms — ใช้ input swipe x y x y <duration_ms>
    ที่จุดเดียวกัน (x1=x2, y1=y2) เพื่อจำลอง long-press ค้างไว้ตามเวลาที่กำหนด
    (มี jitter ±25px แบบ safe_device_tap + miss-tap 2% — เหมือนคน)
    """
    safe_device_tap(ip, port, x, y, duration=duration_ms)


def safe_device_scroll(ip: str, port: int, x: int, y: int, direction: str = "up", distance: int = 500, duration: int = 300):
    # เพิ่ม Bezier-like jitter + duration variance
    jx = x + int(max(-25, min(25, random.gauss(0, 9))))
    jy = y + int(max(-25, min(25, random.gauss(0, 9))))
    # duration แบบคน: ปัดให้ไม่ตายตัว
    if duration in (300, 500):
        duration = random.randint(220, 380)
    direction_map = {
        "up":    (jx, jy + distance, jx, jy - distance),
        "down":  (jx, jy - distance, jx, jy + distance),
        "left":  (jx + distance, jy, jx - distance, jy),
        "right": (jx - distance, jy, jx + distance, jy),
    }
    if direction not in direction_map:
        raise ValueError(f"Invalid direction '{direction}'. Use: up, down, left, right.")
    x1, y1, x2, y2 = direction_map[direction]
    adb = get_adb_path()
    _run_cmd(
        [adb, "-s", f"{ip}:{port}", "shell", "input", "swipe",
         str(x1), str(y1), str(x2), str(y2), str(duration)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def device_is_app_running(ip: str, port: int, package: str) -> bool:
    adb = get_adb_path()
    result = _run_cmd(
        [adb, "-s", f"{ip}:{port}", "shell", "pidof", package],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return bool(result.stdout.strip())


def _sleep_interruptible(seconds: float, stop_check=None) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        if stop_check and stop_check():
            return True
        time.sleep(min(0.2, end - time.time()))
    return False

def device_reset_app(ip: str, port: int, package: str = "com.devsisters.crg", max_retries: int = 5, stop_check=None):
    adb = get_adb_path()
    print(f"🔄 Resetting app {package} on device at {ip}:{port}...")
    _run_cmd(
        [adb, "-s", f"{ip}:{port}", "shell", "cmd", "activity", "force-stop", package],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    print(f"⏳ Waiting 15 seconds for app {package} to stop...")
    if _sleep_interruptible(random.uniform(14.5, 15.8), stop_check):
        print("⏹️ Reset interrupted")
        return

    for attempt in range(1, max_retries + 1):
        if stop_check and stop_check():
            print("⏹️ Reset interrupted before restart")
            return
        print(f"📱 Restarting app {package} on device at {ip}:{port} (attempt {attempt}/{max_retries})...")
        _run_cmd(
            [adb, "-s", f"{ip}:{port}", "shell", "monkey", "-p", package, "1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        print(f"⏳ Waiting 15 seconds to check if app started...")
        if _sleep_interruptible(random.uniform(14.2, 15.9), stop_check):
            print("⏹️ Reset interrupted")
            return

        if device_is_app_running(ip, port, package):
            print(f"📊 App {package} is running, verifying stability...")
            stable = True
            for check in range(1, 4):
                if _sleep_interruptible(random.uniform(19.5, 20.8), stop_check):
                    print("⏹️ Stability check interrupted")
                    return
                if not device_is_app_running(ip, port, package):
                    print(f"💥 App {package} crashed during stability check ({check}/3).")
                    stable = False
                    break
                print(f"✅ Stability check {check}/3 passed.")
            if stable:
                print(f"✅ App {package} is stable.")
                return

        print(f"💥 App {package} appears to have crashed after launch.")
        if attempt < max_retries:
            print(f"🔁 Retrying in 5 seconds...")
            if _sleep_interruptible(random.uniform(4.5, 5.7), stop_check):
                return

    raise Exception(f"❌ Failed to start {package} after {max_retries} attempts.")
