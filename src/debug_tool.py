#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
debug_tool.py — เครื่องมือ debug/diagnostic กลางสำหรับ CookieRun Bot

ใช้เมื่อเจอปัญหาใหม่เสมอ (Live Screen ไม่ทำงาน, บอทค้าง, popup/หน้าจอใหม่,
server ซ้อนพอร์ต ฯลฯ) — แทนการเขียนสคริปต์ cv2/curl ใหม่ทุกครั้ง:

  1) STEP แรกเสมอ:  python3 debug_tool.py capture --port 5595
       capture หน้าจอจริง + detect_stage + X button + bright panel + ตารางสรุป
  2) ถ้า stage = None (หน้าจอไม่รู้จัก):
       python3 debug_tool.py new-stage --name POPUP_NAME --port 5595
       → สร้าง template + region + print code snippet เตรียม paste ลง config.py
  3) ถ้าสงสัย server ซ้อน/ค้างพอร์ต:
       python3 debug_tool.py servers
  4) ก่อนบอกว่า "แก้เสร็จ" หลังแก้โค้ดทุกครั้ง:
       python3 debug_tool.py verify --port 5595

Commands:
  capture    — capture หน้าจอ ADB + วิเคราะห์ stage/X/popup/bright panel ทันที
  new-stage  — สร้าง template+region สำหรับ stage/popup ใหม่จากภาพจริง (ไม่สร้างเอง)
  servers    — สแกนพอร์ต 8000-8010 หา web server + instance ที่รันอยู่ + lock file
  verify     — regression: ทดสอบ detect_stage กับทุก template + รายงาน score ใกล้ threshold
"""
import argparse
import datetime
import os
import shutil
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import config  # noqa: E402
from adb import device_capture_screen  # noqa: E402
from detection import (  # noqa: E402
    _get_template_gray,
    detect_stage,
    detect_templates_multiscale,
    find_bright_panels,
    find_close_x_button,
    find_green_blobs,
    find_green_ok_button,
    is_announcement_popup_visible,
    is_confirm_popup_visible,
    load_templates,
)

ADB_IP = "127.0.0.1"
ADB_PORT = 5595
PORT_RANGE = range(8000, 8011)
MATCH_NEAR_DELTA = 0.05  # score ใกล้ threshold แค่นี้ → เตือนให้พิจารณาปรับ threshold
TEMPLATE_SIMILARITY_WARN = 0.85  # template ใหม่คล้าย template เดิมเกินนี้ → เตือน false positive
LOCK_FILE = "/tmp/cookierun_bot.lock"


# ---------------------------------------------------------------- helpers

def _print_table(headers, rows):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    line = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    print(line)
    print("|" + "|".join(f" {str(h).ljust(w)} " for h, w in zip(headers, widths)) + "|")
    print(line)
    for row in rows:
        print("|" + "|".join(f" {str(c).ljust(w)} " for c, w in zip(row, widths)) + "|")
    print(line)


def _load_screen(ip, port, path=None):
    """โหลดภาพ: path (ถ้าให้) หรือ capture สดจาก ADB"""
    if path:
        img = cv2.imread(path)
        if img is None:
            sys.exit(f"❌ อ่านไฟล์ภาพไม่ได้: {path}")
        return img
    img = device_capture_screen(ip, port)
    if img is None:
        sys.exit(f"❌ Capture หน้าจอจาก {ip}:{port} ไม่ได้ (เช็ค ADB / device)")
    return img


def _save_debug_image(img, prefix="debug"):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"/tmp/{prefix}_{ts}.png"
    cv2.imwrite(path, img)
    return path


def _center_region(img, x_frac=(0.15, 0.85), y_frac=(0.15, 0.85)):
    """region กลางจอ (เผื่อไว้เช็ค panel/popup) ตามสัดส่วน"""
    h, w = img.shape[:2]
    return (int(w * x_frac[0]), int(h * y_frac[0]), int(w * x_frac[1]), int(h * y_frac[1]))


# ---------------------------------------------------------------- capture

def capture_cmd(args):
    img = _load_screen(args.ip, args.port, args.file)
    save_path = _save_debug_image(img, "debug")
    h, w = img.shape[:2]

    print(f"📸 Screen: {w}x{h}  saved → {save_path}\n")

    load_templates()
    stage = detect_stage(img, exclude=set())
    print("🎯 Stage Detection")
    print(f"   current stage : {stage if stage else 'None (หน้าจอไม่รู้จัก — ใช้ new-stage สร้าง template)'}")

    if not args.no_groups:
        groups = dict(config.DETECTION_GROUPS)
        groups["ALWAYS"] = config.DETECTION_ALWAYS_STAGES
        rows = []
        for gname, stages in groups.items():
            gstage = detect_stage(img, stage_names=list(stages))
            rows.append([gname, ", ".join(stages), gstage if gstage else "—"])
        print("\n📦 Per-group check:")
        _print_table(["group", "stages", "match"], rows)

    print("\n✖️  Close X button")
    x_btn = find_close_x_button(img)
    print(f"   X button       : {x_btn if x_btn else 'not found'}")

    print("\n🔲 Bright panels (center 60%)")
    region = _center_region(img)
    panels = find_bright_panels(img, region=region)
    if panels:
        for (x1, y1, x2, y2) in panels[:5]:
            print(f"   bright panel   : ({x1},{y1})-({x2},{y2})  size {x2-x1}x{y2-y1}  center ({(x1+x2)//2},{(y1+y2)//2})")
    else:
        print("   no bright panel")

    print("\n🟢 Green buttons")
    blobs = find_green_blobs(img, region=(0, h // 2, w, h), min_w=200, max_w=420, min_h=60, max_h=140)
    if blobs:
        for (x1, y1, x2, y2) in blobs[:5]:
            print(f"   green button   : ({x1},{y1})-({x2},{y2})  center ({(x1+x2)//2},{(y1+y2)//2})")
    else:
        print("   no green button (lower half)")
    ok_pos = find_green_ok_button(img)
    if ok_pos:
        print(f"   OK button      : {ok_pos}")

    print("\n🧪 Heuristics")
    print(f"   confirm popup      : {is_confirm_popup_visible(img)}")
    print(f"   announcement popup : {is_announcement_popup_visible(img)}")

    print("\n💡 ถ้า stage = None → รัน:  python3 debug_tool.py new-stage --name XXX --port %d" % args.port)


# ---------------------------------------------------------------- new-stage

def _template_similarity(a_path, b_path):
    """
    วัดความคล้ายของ template 2 ไฟล์ (หลาย scale, ทั้ง 2 ทิศทาง)
    เพราะ region/crop ใหม่มักใหญ่กว่า template เดิม (region = search area)
    → ค้นหา b ภายใน a และ a ภายใน b ด้วย scale 0.8-1.25 แล้วคืนค่าสูงสุด
    """
    a = cv2.imread(a_path, cv2.IMREAD_GRAYSCALE)
    b = cv2.imread(b_path, cv2.IMREAD_GRAYSCALE)
    if a is None or b is None:
        return None

    def _search(haystack, needle):
        best = 0.0
        for scale in (0.8, 0.9, 1.0, 1.1, 1.25):
            t = cv2.resize(needle, (0, 0), fx=scale, fy=scale)
            if t.shape[0] > haystack.shape[0] or t.shape[1] > haystack.shape[1]:
                continue
            r = cv2.matchTemplate(haystack, t, cv2.TM_CCOEFF_NORMED)
            best = max(best, float(r.max()))
        return best

    return max(_search(a, b), _search(b, a))


def new_stage_cmd(args):
    name = args.name.upper().strip()
    if not name:
        sys.exit("❌ ต้องระบุ --name (เช่น --name PARTY_PASS_POPUP)")
    img = _load_screen(args.ip, args.port, args.file)
    h, w = img.shape[:2]
    save_path = _save_debug_image(img, f"newstage_{name}")

    print(f"📸 Screen: {w}x{h}  saved → {save_path}\n")

    # --- 1) หา region ---
    region = None
    if args.region:
        parts = [int(v) for v in args.region.replace(" ", "").split(",")]
        if len(parts) != 4:
            sys.exit("❌ --region ต้องเป็น x1,y1,x2,y2 เช่น --region 100,10,1180,78")
        region = tuple(parts)
    else:
        region = _prompt_region(img, name)

    x1, y1, x2, y2 = region
    if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
        sys.exit(f"❌ region {region} เกินขอบจอ {w}x{h}")
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        sys.exit("❌ crop ว่างเปล่า")

    # --- 2) บันทึก template ตาม convention: <NAME>_1.png ---
    fname = f"{name}_1.png"
    tpath = os.path.join(config.TEMPLATE_DIR, fname)
    cv2.imwrite(tpath, crop)
    print(f"💾 Template saved → {tpath}  ({x2-x1}x{y2-y1} px)\n")

    # --- 3) ทดสอบ match บนภาพเดียวกัน (ต้อง ~1.0) ---
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    t_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    res = cv2.matchTemplate(gray[y1:y2, x1:x2], t_gray, cv2.TM_CCOEFF_NORMED)
    score = float(res.max())
    print(f"🧪 Match on same image: {score:.4f}  ({'✅ OK' if score > 0.95 else '⚠️ ควรใกล้ 1.0 — ลอง crop region ที่แคบ/เฉพาะกว่า'})")

    # --- 4) เช็คความคล้ายกับ template เดิม ---
    similar = []
    for fn in os.listdir(config.TEMPLATE_DIR):
        if fn.endswith(".png") and fn != fname:
            sim = _template_similarity(tpath, os.path.join(config.TEMPLATE_DIR, fn))
            if sim is not None and sim >= TEMPLATE_SIMILARITY_WARN:
                similar.append((fn, sim))
    if similar:
        print("⚠️  เตือน: template นี้คล้ายกับ template เดิมมากเกินไป (เสี่ยง detect ข้าม stage):")
        for fn, sim in sorted(similar, key=lambda s: -s[1]):
            print(f"      {fn}  similarity={sim:.3f}")
    else:
        print("🔍 ไม่มี template เดิมที่คล้ายกันเกิน 0.85 — false positive risk ต่ำ")

    # --- 5) ทดสอบ detect_stage กับภาพนี้จริง (in-memory inject) ---
    config.STAGE_TEMPLATES[name] = [fname]
    config.STAGE_REGIONS[name] = region
    suggested_th = max(0.55, round(score - 0.25, 2))
    config.STAGE_THRESHOLDS[name] = suggested_th
    result = detect_stage(img, exclude=set())
    if result == name:
        print(f"🎯 detect_stage() บนภาพนี้ → {name}  (ผ่าน)")
    else:
        print(f"⚠️  detect_stage() บนภาพนี้ → {result} (ไม่ใช่ {name}) — สเตจอื่น match ก่อน")
        print(f"      แนะนำ: วาง '{name}' ไว้สูงกว่า '{result}' ใน STAGE_TEMPLATES หรือ crop region ให้เฉพาะกว่า")

    # --- 6) print code snippet สำหรับ config.py ---
    print(f"""
{'='*70}
📋  Paste ลง src/config.py (ตาม convention ที่มีอยู่):
{'='*70}
STAGE_{name}_TEMPLATE = [{fname!r}]
STAGE_{name}_REGION = {region}
# (ถ้ามีปุ่มกด) วัดจากภาพจริง {save_path} — เช่น find_green_blobs / find_bright_panels

# ใน STAGE_THRESHOLDS เพิ่ม:
    {name!r}: {suggested_th},

# ใน STAGE_TEMPLATES / STAGE_REGIONS เพิ่ม:
    {name!r}:              STAGE_{name}_TEMPLATE,
    ...
    {name!r}:              STAGE_{name}_REGION,

# กลุ่มที่ควรอยู่ (ตามบริบทที่เจอ):
#   PRE_GAME / IN_GAME / POST_GAME ใน DETECTION_GROUPS
#   หรือ DETECTION_ALWAYS_STAGES ถ้าเป็น popup ที่โผล่ได้ทุกเมื่อ
# แล้วเพิ่ม handler: elif stage == {name!r}: ... ใน bot_engine.py
{'='*70}
""")


def _prompt_region(img, name):
    """interactive: ให้ user ป้อน region หรือใช้ auto-suggestion จาก bright panel"""
    h, w = img.shape[:2]
    print("🔲 Bright panels ที่เจอบนจอนี้ (กด Enter เลือกอันแรก หรือพิมพ์เอง):")
    panels = find_bright_panels(img, region=_center_region(img))
    if panels:
        for i, (x1, y1, x2, y2) in enumerate(panels[:5]):
            print(f"   [{i+1}] ({x1},{y1})-({x2},{y2})  size {x2-x1}x{y2-y1}")
    else:
        print("   (ไม่เจอ bright panel — ต้องป้อนพิกัดเอง)")

    try:
        if not sys.stdin.isatty() and not panels:
            sys.exit("❌ อยู่ในโหมด non-interactive และไม่มี --region — ระบุ --region x1,y1,x2,y2")
        raw = input(f"Region สำหรับ {name} (x1,y1,x2,y2) [default = อันแรก]: ").strip()
        if not raw and panels:
            x1, y1, x2, y2 = panels[0]
            print(f"   → ใช้ ({x1},{y1})-({x2},{y2})")
            return (x1, y1, x2, y2)
    except EOFError:
        sys.exit("❌ ต้องการ input — ระบุ --region x1,y1,x2,y2 แทน")
    parts = [int(v) for v in raw.replace(" ", "").split(",")]
    if len(parts) != 4:
        sys.exit("❌ ต้องเป็น x1,y1,x2,y2 เช่น 100,10,1180,78")
    return tuple(parts)


# ---------------------------------------------------------------- servers

def _port_listening(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _port_pid(port):
    try:
        out = subprocess.run(["lsof", "-tiTCP:" + str(port), "-sTCP:LISTEN"],
                             capture_output=True, text=True, timeout=5).stdout
        pids = [ln.strip() for ln in out.splitlines() if ln.strip().isdigit()]
        return ",".join(pids) if pids else "?"
    except Exception:
        return "?"


def _port_instances(port):
    """ลองเรียก /api/instances — คืน string สรุป หรือ None ถ้าไม่ใช่ web server ของเรา"""
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/instances", timeout=1.5) as r:
            data = r.read().decode()
        import json
        insts = json.loads(data)
        parts = []
        for d in insts:
            mark = "▶" if d.get("is_running") else "·"
            parts.append(f"{mark}{d.get('instance_id')}@{d.get('device_port')}={d.get('current_stage')}")
        return "  ".join(parts) if parts else "(empty)"
    except Exception:
        return None


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def servers_cmd(args):
    print(f"🔎 Scanning ports {PORT_RANGE.start}-{PORT_RANGE.stop - 1} ...\n")
    rows = []
    for port in PORT_RANGE:
        listening = _port_listening(port)
        if not listening:
            continue
        pid = _port_pid(port)
        inst = _port_instances(port)
        rows.append([port, pid, inst if inst else "⚠️ listening แต่ไม่ใช่ /api/instances (service อื่น)"])
    if rows:
        _print_table(["port", "PID", "instances"], rows)
    else:
        print("✅ ไม่มี port ใดใน 8000-8010 ถูกใช้งาน")

    print("\n🔒 Lock file")
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                parts = f.read().strip().split()
            pid = int(parts[0]) if parts and parts[0].isdigit() else 0
            port = parts[1] if len(parts) > 1 else "?"
            alive = _pid_alive(pid)
            state = "รันอยู่" if alive else "⚠️ PID ตายแล้ว (lock ค้าง — ลบได้: rm /tmp/cookierun_bot.lock)"
            print(f"   {LOCK_FILE}: PID {pid} port {port} → {state}")
        except Exception as e:
            print(f"   อ่าน lock ไม่ได้: {e}")
    else:
        print("   ไม่มี lock file (ไม่มี server รัน หรือรันโดยไม่ใช้ run_web.py)")

    print("\n📱 ADB devices")
    try:
        out = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines()[1:]:
            if line.strip():
                print(f"   {line.strip()}")
    except Exception as e:
        print(f"   adb ไม่พร้อม: {e}")


# ---------------------------------------------------------------- verify

def verify_cmd(args):
    img = _load_screen(args.ip, args.port, args.file)
    save_path = _save_debug_image(img, "debug_verify")
    h, w = img.shape[:2]
    print(f"📸 Screen: {w}x{h}  saved → {save_path}\n")

    load_templates()
    main_stage = detect_stage(img, exclude=set())
    print(f"🎯 Current stage : {main_stage if main_stage else 'None'}\n")

    print("📊 All templates vs current screen (score ใน region ของตัวเอง):")
    rows = []
    near = []
    for stage_name, tmpls in config.STAGE_TEMPLATES.items():
        region = config.STAGE_REGIONS.get(stage_name)
        th = config.STAGE_THRESHOLDS.get(stage_name, config.MATCH_THRESHOLD)
        scores = []
        for fn in tmpls:
            t = _get_template_gray(fn)
            if t is None:
                continue
            search = img[region[1]:region[3], region[0]:region[2]] if region else img
            sg = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
            if sg.shape[0] < t.shape[0] or sg.shape[1] < t.shape[1]:
                continue
            r = cv2.matchTemplate(sg, t, cv2.TM_CCOEFF_NORMED)
            scores.append(float(r.max()))
        if not scores:
            continue
        best = max(scores)
        delta = best - th
        flag = ""
        if best >= th:
            flag = "✅ MATCH" if stage_name == main_stage else "✅"
        elif delta >= -MATCH_NEAR_DELTA:
            flag = "⚠️ NEAR THRESHOLD"
            near.append((stage_name, best, th))
        rows.append([stage_name, f"{best:.3f}", f"{th:.2f}", f"{delta:+.3f}", flag])
    _print_table(["stage", "score", "threshold", "delta", "status"], rows)

    if near:
        print("\n⚠️  Templates ที่ score ใกล้ threshold (พิจารณาปรับ threshold/region):")
        for name, score, th in near:
            print(f"   {name}: score {score:.3f} / threshold {th:.2f}")
    else:
        print("\n✅ ไม่มี template ไหนใกล้ threshold ที่เสี่ยง false positive")

    print("\n✖️  Close X multi-scale scan (หา X ปุ่มปิด popup ทุกขนาด)")
    x_matches = detect_templates_multiscale(img, ["CLOSE_X_1.png"], scales=(0.7, 0.85, 1.0, 1.2, 1.4))
    if x_matches:
        for m in x_matches[:5]:
            print(f"   {m['filename']} scale={m['scale']:.2f} score={m['score']:.3f} center ({(2*m['x']+m['w'])//2},{(2*m['y']+m['h'])//2})")
    else:
        print("   no X found")

    print("\n🟢 Green buttons + 🔲 bright panels")
    blobs = find_green_blobs(img, region=(0, h // 2, w, h), min_w=200, max_w=420, min_h=60, max_h=140)
    for (x1, y1, x2, y2) in blobs[:3]:
        print(f"   green: ({(x1+x2)//2},{(y1+y2)//2})")
    panels = find_bright_panels(img, region=_center_region(img))
    for (x1, y1, x2, y2) in panels[:3]:
        print(f"   bright: ({(x1+x2)//2},{(y1+y2)//2}) size {x2-x1}x{y2-y1}")

    if main_stage is None:
        print("\n💡 stage = None → รัน:  python3 debug_tool.py new-stage --name XXX --port %d" % args.port)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(
        description="CookieRun Bot — debug/diagnostic tool กลาง",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cap = sub.add_parser("capture", help="capture + วิเคราะห์ stage/X/popup ทันที")
    p_cap.add_argument("--port", type=int, default=ADB_PORT)
    p_cap.add_argument("--ip", default=ADB_IP)
    p_cap.add_argument("--file", help="ใช้ไฟล์ภาพแทน capture สด (สำหรับ debug ภาพเก่า)")
    p_cap.add_argument("--no-groups", action="store_true", help="ข้าม per-group check")
    p_cap.set_defaults(func=capture_cmd)

    p_new = sub.add_parser("new-stage", help="สร้าง template+region สำหรับ stage/popup ใหม่")
    p_new.add_argument("--name", required=True, help="ชื่อ stage (เช่น PARTY_PASS_POPUP)")
    p_new.add_argument("--port", type=int, default=ADB_PORT)
    p_new.add_argument("--ip", default=ADB_IP)
    p_new.add_argument("--file", help="ใช้ไฟล์ภาพแทน capture สด")
    p_new.add_argument("--region", help="x1,y1,x2,y2 (ไม่ระบุ = prompt interactive)")
    p_new.set_defaults(func=new_stage_cmd)

    p_serv = sub.add_parser("servers", help="สแกน port 8000-8010 หา server + instance")
    p_serv.set_defaults(func=servers_cmd)

    p_ver = sub.add_parser("verify", help="regression test กับทุก template + รายงาน threshold")
    p_ver.add_argument("--port", type=int, default=ADB_PORT)
    p_ver.add_argument("--ip", default=ADB_IP)
    p_ver.add_argument("--file", help="ใช้ไฟล์ภาพแทน capture สด")
    p_ver.set_defaults(func=verify_cmd)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
