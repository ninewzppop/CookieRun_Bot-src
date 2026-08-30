#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
debug_boost_test.py — ทดสอบ detect_templates 6 template (checked/unchecked x 3) กับภาพจริงจาก ADB (ห้าม synthetic)
- Capture จาก emulator จริง via device_capture_screen()
- ทดสอบทั้ง 6 template กับภาพจริงนั้น
"""
import os, sys, cv2
sys.path.insert(0, os.path.dirname(__file__))
from adb import device_capture_screen, get_adb_path
import config
from detection import detect_templates

def test_with_image(img, label=""):
    print(f"\n=== Test {label} ===")
    if img is None:
        print("❌ img is None")
        return
    h,w = img.shape[:2]
    print(f"Image {w}x{h}")
    if (w,h) != (1280,720):
        print(f"⚠️  Scale needed: sx={1280/w:.4f} sy={720/h:.4f}")

    # Define 6 tests
    tests = [
        ("HP_EXTENSION_CHECKED", config.BOOST_HP_EXTENSION_CHECKED_TEMPLATE, config.HP_EXTENSION_REGION, config.HP_EXTENSION_TAP_POS),
        ("HP_EXTENSION_UNCHECKED", config.BOOST_HP_EXTENSION_UNCHECKED_TEMPLATE, config.HP_EXTENSION_REGION, config.HP_EXTENSION_TAP_POS),
        ("POWER_JELLY_CHECKED", config.BOOST_POWER_JELLY_CHECKED_TEMPLATE, config.POWER_JELLY_REGION, config.POWER_JELLY_TAP_POS),
        ("POWER_JELLY_UNCHECKED", config.BOOST_POWER_JELLY_UNCHECKED_TEMPLATE, config.POWER_JELLY_REGION, config.POWER_JELLY_TAP_POS),
        ("DOUBLE_XP_CHECKED", config.BOOST_DOUBLE_XP_CHECKED_TEMPLATE, config.DOUBLE_XP_REGION, config.DOUBLE_XP_TAP_POS),
        ("DOUBLE_XP_UNCHECKED", config.BOOST_DOUBLE_XP_UNCHECKED_TEMPLATE, config.DOUBLE_XP_REGION, config.DOUBLE_XP_TAP_POS),
    ]
    for name, tmpl, region, tap in tests:
        hits = detect_templates(img, tmpl, region)
        status = "✅ FOUND" if hits else "❌ NOT FOUND"
        print(f"{status} {name}: tmpl={tmpl} region={region} tap={tap} hits={hits}")
        if hits:
            # debug maxVal
            import numpy as np
            from detection import _get_template_gray, _normalize_gray, _crop_region
            gray = _normalize_gray(img)
            search = _crop_region(gray, region)
            for fn in tmpl:
                t = _get_template_gray(fn)
                if t is None: continue
                res = cv2.matchTemplate(search, t, cv2.TM_CCOEFF_NORMED)
                _, mx, _, _ = cv2.minMaxLoc(res)
                print(f"  -> {fn} maxVal={mx:.4f}")

def main():
    # Try ADB capture
    print(f"ADB: {get_adb_path()}")
    ip = config.DEVICE_IP
    port = config.DEVICE_PORT
    if hasattr(config, "DEVICES") and config.DEVICES:
        for dev in config.DEVICES:
            from adb import device_check_connection
            ok,_ = device_check_connection(dev["host"], dev["port"])
            if ok:
                ip = dev["host"]; port = dev["port"]; break
    print(f"Capturing from {ip}:{port} (must be on Buy Upgrades! screen for valid test)...")
    try:
        img = device_capture_screen(ip, port)
    except Exception as e:
        print(f"❌ Capture failed: {e}")
        import traceback; traceback.print_exc()
        return
    h,w = img.shape[:2]
    print(f"✅ Captured {w}x{h}")
    out_dir = os.path.join(os.path.dirname(__file__), "debug_screenshots")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "boost_current.png")
    cv2.imwrite(out_path, img)
    print(f"Saved {out_path}")
    test_with_image(img, label="ADB real capture (current screen)")

    # Also test with synthetic? Skip per spec — only real
    print("\n=== Summary ===")
    print("If screen was on Buy Upgrades! with 3 boosts checked/unchecked, you should see 3 FOUND for matching state and 3 NOT FOUND for opposite.")
    print("If screen was NOT on Buy Upgrades!, all will be NOT FOUND (expected). Open Buy Upgrades! and re-run.")

if __name__ == "__main__":
    main()
