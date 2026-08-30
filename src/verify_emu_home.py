# -*- coding: utf-8 -*-
"""
Verify EMU_HOME tap coordinate with real ADB capture (no guessing).

Usage:
    python3 verify_emu_home.py [--device 127.0.0.1:5595] [--file /tmp/emu_live.png]

Prints:
    - whether EMU_HOME is confirmed on screen (heuristic + template)
    - detected icon(s) position via template matching + color-blob analysis
    - comparison with config.EMU_HOME_TAP
Saves an annotated debug image next to the source as `*_verified.png`.
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detection import is_emu_home_visible, _get_template_gray  # noqa: E402
from config import EMU_HOME_TAP, STAGE_EMU_HOME_TEMPLATE, STAGE_EMU_HOME_REGION  # noqa: E402


def load_screen(device=None, file_path=None):
    if file_path:
        img = cv2.imread(file_path)
        if img is None:
            sys.exit(f"cannot read image: {file_path}")
        return img
    from adb import device_capture_screen

    ip, port = device.rsplit(":", 1)
    return device_capture_screen(ip, int(port))


def find_icon_by_template(screen):
    """matchTemplate with EMU_HOME_1.png — คืน (x, y, w, h) ของ match สูงสุด หรือ None"""
    best = None
    for name in STAGE_EMU_HOME_TEMPLATE:
        tpl = _get_template_gray(name)
        if tpl is None:
            continue
        th, tw = tpl.shape[:2]
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= 0.6:
            x, y = max_loc
            if best is None or max_val > best[0]:
                best = (max_val, x, y, tw, th)
    return best


def find_icon_by_color(screen):
    """
    Color-blob analysis: launcher icons are saturated colorful squares on dark bg.
    คืน list ของ (cx, cy, w, h, sat_mean) เรียงตาม saturation จากมากไปน้อย
    """
    hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    # เกณฑ์: พิกเซล saturated (S>90) และไม่ใช่แค่สีเทา
    mask = cv2.inRange(hsv, (0, 90, 60), (180, 255, 255))
    # ลด noise + รวมไอคอนที่อยู่ติดกันเป็น blob เดียว
    kernel = np.ones((9, 9), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w < 20 or h < 20 or w > 250 or h > 250:  # ตัวอักษร/แถบใหญ่ ไม่ใช่ไอคอน
            continue
        area_ratio = cv2.contourArea(c) / float(w * h)
        if area_ratio < 0.25:
            continue
        roi = sat[y : y + h, x : x + w]
        blobs.append((x + w // 2, y + h // 2, w, h, float(roi.mean())))
    blobs.sort(key=lambda b: -b[4])
    return blobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="127.0.0.1:5595")
    ap.add_argument("--file", default=None)
    args = ap.parse_args()

    screen = load_screen(args.device, args.file)
    h, w = screen.shape[:2]
    print(f"screen: {w}x{h}")
    src = args.file or args.device.replace(":", "_")

    # 1) ยืนยันว่าเป็นหน้า EMU_HOME จริง
    heur = is_emu_home_visible(screen)
    tpl = find_icon_by_template(screen)
    print(f"[1] is_emu_home_visible (heuristic): {heur}")
    if tpl:
        print(f"    template match {tpl[0]:.3f} -> icon at ({tpl[1] + tpl[3] // 2}, {tpl[2] + tpl[4] // 2})")
    else:
        print("    template match: not found (may still be EMU_HOME via heuristic)")

    # 2) color-blob: หาไอคอนทั้งหมด + ตรวจว่ามี blob อยู่ที่ config tap point ไหม
    blobs = find_icon_by_color(screen)
    print(f"[2] saturated icon-like blobs: {len(blobs)}")
    cfg_x, cfg_y = EMU_HOME_TAP
    cfg_hit = False
    for bx, by, bw, bh, sat in blobs[:12]:
        inside = (bx - cfg_x) ** 2 + (by - cfg_y) ** 2 <= 30 ** 2
        tag = " <-- config EMU_HOME_TAP อยู่บน blob นี้" if inside else ""
        if inside:
            cfg_hit = True
        print(f"    blob at ({bx:4d},{by:4d}) size {bw}x{bh} sat={sat:.0f}{tag}")

    # 3) เทียบพิกัด
    print(f"[3] config EMU_HOME_TAP = {EMU_HOME_TAP}")
    if blobs:
        top = blobs[0]
        print(f"    ไอคอนที่เด่นสุด (สีจัดสุด) = ({top[0]},{top[1]})  ขนาด {top[2]}x{top[3]}")
        d = ((cfg_x - top[0]) ** 2 + (cfg_y - top[1]) ** 2) ** 0.5
        print(f"    ระยะห่าง config->ไอคอนเด่น = {d:.0f} px  ({'OK' if d < 30 else 'MISMATCH!'})")
    print(f"    config tap อยู่บน icon blob หรือไม่: {'YES' if cfg_hit else 'NO'}")

    # 4) บันทึกภาพ annotate (debug)
    dbg = screen.copy()
    cv2.circle(dbg, (cfg_x, cfg_y), 12, (0, 0, 255), 3)  # red = config tap point
    cv2.putText(dbg, "config(628,341)", (cfg_x - 130, cfg_y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    for bx, by, bw, bh, sat in blobs[:12]:
        cv2.rectangle(dbg, (bx - bw // 2, by - bh // 2), (bx + bw // 2, by + bh // 2), (0, 255, 0), 2)
        cv2.putText(dbg, f"({bx},{by})", (bx + 8, by), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
    out = f"/tmp/{os.path.basename(src)}_verified.png"
    cv2.imwrite(out, dbg)
    print(f"annotated debug image saved: {out}")


if __name__ == "__main__":
    main()
