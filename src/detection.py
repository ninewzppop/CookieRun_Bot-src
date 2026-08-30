import os

import cv2
import numpy as np

from config import (
    ANTI_BOT_CARD_HEIGHT,
    ANTI_BOT_CARD_POS_6,
    ANTI_BOT_CARD_WIDTH,
    ANTI_BOT_CARD_POS_1,
    ANTI_BOT_CARD_POS_2,
    ANTI_BOT_CARD_POS_3,
    ANTI_BOT_CARD_POS_4,
    ANTI_BOT_CARD_POS_5,
    BOOST_TEMPLATES,
    MATCH_THRESHOLD,
    STAGE_REGIONS,
    STAGE_TEMPLATES,
    STAGE_THRESHOLDS,
    TEMPLATE_DIR,
)


_template_cache: dict = {}
_template_gray_cache: dict = {}

BOX_GRADE_TEMPLATES = {
    "wood": "BOX_WOOD.png",
    "silver": "BOX_SILVER.png",
    "gold": "BOX_GOLD.png",
    "rainbow": "BOX_RAINBOW.png",
}


def _get_template(filename):
    """Return cached template image, loading from disk on first access."""
    if filename not in _template_cache:
        path = os.path.join(TEMPLATE_DIR, filename)
        if os.path.exists(path):
            img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            _template_cache[filename] = _normalize(img)
        else:
            _template_cache[filename] = None
    return _template_cache[filename]


def _get_template_gray(filename):
    """Return cached grayscale template image, loading from disk on first access."""
    if filename not in _template_gray_cache:
        template = _get_template(filename)
        _template_gray_cache[filename] = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if template is not None else None
    return _template_gray_cache[filename]


def load_templates():
    """Pre-warm the template cache with all stage, boost, and box templates at startup."""
    for template_files in STAGE_TEMPLATES.values():
        for filename in template_files:
            _get_template_gray(filename)
    for template_files in BOOST_TEMPLATES:
        for filename in template_files:
            _get_template_gray(filename)
    for filename in BOX_GRADE_TEMPLATES.values():
        _get_template_gray(filename)


def _normalize(img):
    """Ensure image is BGR uint8 (3-channel). Returns None if conversion fails."""
    if img is None:
        return None
    if img.dtype != np.uint8:
        return None
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.ndim == 3 and img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    if img.ndim == 3 and img.shape[2] == 3:
        return img
    return None


def _normalize_gray(img):
    normalized = _normalize(img)
    if normalized is None:
        return None
    return cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)


def _crop_region(img, region):
    if region is None:
        return img
    x1, y1, x2, y2 = region
    return img[y1:y2, x1:x2]


def detect_templates(screen, template_files, region=None):
    screen_gray = _normalize_gray(screen)
    if screen_gray is None:
        return []
    screen_gray = _crop_region(screen_gray, region)
    offset_x, offset_y = (region[0], region[1]) if region is not None else (0, 0)
    matches = []
    for filename in template_files:
        template = _get_template_gray(filename)
        if template is None:
            continue
        result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        # use per-template threshold if available
        th_name = None
        for k, v in STAGE_TEMPLATES.items():
            if filename in v:
                th_name = k
                break
        threshold = STAGE_THRESHOLDS.get(th_name, MATCH_THRESHOLD) if th_name and isinstance(STAGE_THRESHOLDS, dict) else MATCH_THRESHOLD
        if max_val >= threshold:
            th, tw = template.shape[:2]
            x = max_loc[0] + offset_x
            y = max_loc[1] + offset_y
            matches.append((x, y, tw, th))
    return matches


CLOSE_X_TEMPLATE = "CLOSE_X_1.png"


def find_close_x_button(screen):
    """
    หาตำแหน่งปุ่ม X ปิด popup ด้วย template CLOSE_X_1.png ทั่วทั้งจอ (ทนต่อ popup variant
    ที่ X อยู่คนละตำแหน่ง เช่น (1126,57) เก่า vs (1213,89) ใหม่) — คืน (cx, cy) หรือ None
    """
    matches = detect_templates(screen, [CLOSE_X_TEMPLATE], None)
    if not matches:
        return None
    x, y, tw, th = matches[0]
    return (x + tw // 2, y + th // 2)


def detect_stage(screen, stage_names=None, exclude=None):
    screen_gray = _normalize_gray(screen)
    if screen_gray is None:
        return None
    if stage_names is None:
        stage_names = STAGE_TEMPLATES.keys()
    if exclude:
        stage_names = [s for s in stage_names if s not in exclude]
    for stage_name in stage_names:
        template_files = STAGE_TEMPLATES.get(stage_name)
        if not template_files:
            continue
        search_area = _crop_region(screen_gray, STAGE_REGIONS.get(stage_name))
        threshold = STAGE_THRESHOLDS.get(stage_name, MATCH_THRESHOLD) if isinstance(STAGE_THRESHOLDS, dict) else MATCH_THRESHOLD
        for filename in template_files:
            template = _get_template_gray(filename)
            if template is None:
                continue
            if (
                search_area.shape[0] < template.shape[0]
                or search_area.shape[1] < template.shape[1]
            ):
                continue
            result = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            if max_val >= threshold:
                if stage_name == "ANNOUNCEMENT_POPUP" and not _has_close_x(screen_gray):
                    # กัน false positive (MAINMENU/เกมปกติ มุมขวาบนมีไอคอนคล้าย X ที่ threshold 0.42)
                    # popup ประกาศจริงต้องมีปุ่ม X จริง (CLOSE_X_1.png match >= 0.8)
                    continue
                return stage_name
    return None


def _has_close_x(screen_gray):
    """ตรวจว่ามีปุ่ม X (CLOSE_X_1.png) จริงบนจอหรือไม่ — ใช้ยืนยัน ANNOUNCEMENT_POPUP"""
    from config import STAGE_ANNOUNCEMENT_POPUP_REGION

    search = _crop_region(screen_gray, STAGE_ANNOUNCEMENT_POPUP_REGION)
    template = _get_template_gray(CLOSE_X_TEMPLATE)
    if template is None or search is None:
        return False
    if search.shape[0] < template.shape[0] or search.shape[1] < template.shape[1]:
        return False
    result = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val >= MATCH_THRESHOLD


def is_confirm_popup_visible(screen) -> bool:
    """
    ตรวจหน้าต่างยืนยันกลางจอ (ปุ่มเขียวใหญ่ 288x98 ที่ (635,454) — วัดจาก ADB 1280×720)
    เกณฑ์: มีปุ่มเขียวขนาดใหญ่ (w 180-380, h 60-140) ในโซนกลางล่างของ popup
    กัน false positive: ปุ่มเมนูหลักเล็ก (~100x55), ปุ่ม dock ล่าง (~407x88 แต่อยู่นอกโซน y)
    """
    from config import CONFIRM_POPUP_REGION

    screen_bgr = _normalize(screen)
    if screen_bgr is None:
        return False
    x1, y1, x2, y2 = CONFIRM_POPUP_REGION
    crop = screen_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return False
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, (35, 60, 60), (85, 255, 255))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if 180 <= w <= 380 and 60 <= h <= 140:
            return True
    return False


def detect_mystery_box_grades(screen) -> list:
    """
    Detects mystery box locations and accurately classifies their grades on the screen.
    Returns a list of grade strings (e.g. ['wood', 'silver']).
    """
    screen_bgr = _normalize(screen)
    if screen_bgr is None:
        return []

    h_screen, w_screen = screen_bgr.shape[:2]
    # Search region for boxes
    y1, y2 = max(0, int(h_screen * 0.20)), min(h_screen, int(h_screen * 0.75))
    x1, x2 = max(0, int(w_screen * 0.15)), min(w_screen, int(w_screen * 0.85))
    search_crop = screen_bgr[y1:y2, x1:x2]

    # Load color templates
    templates = {}
    for grade, tmpl_fn in BOX_GRADE_TEMPLATES.items():
        t = _get_template(tmpl_fn)
        if t is not None:
            templates[grade] = t

    if not templates:
        return []

    all_matches = []
    for grade, tmpl in templates.items():
        for scale in [0.95, 1.0, 1.05, 1.1, 1.15]:
            t_scaled = tmpl if scale == 1.0 else cv2.resize(tmpl, (0, 0), fx=scale, fy=scale)
            if t_scaled.shape[0] > search_crop.shape[0] or t_scaled.shape[1] > search_crop.shape[1]:
                continue
            res = cv2.matchTemplate(search_crop, t_scaled, cv2.TM_CCOEFF_NORMED)
            locs = np.where(res >= 0.60)
            for pt in zip(*locs[::-1]):
                all_matches.append({
                    "score": float(res[pt[1], pt[0]]),
                    "x": int(pt[0] + x1),
                    "y": int(pt[1] + y1),
                    "w": int(t_scaled.shape[1]),
                    "h": int(t_scaled.shape[0]),
                    "grade": grade
                })

    all_matches = sorted(all_matches, key=lambda m: m["score"], reverse=True)
    detected_boxes = []
    for m in all_matches:
        overlap = False
        for b in detected_boxes:
            if abs(m["x"] - b["x"]) < 120 and abs(m["y"] - b["y"]) < 120:
                overlap = True
                break
        if not overlap:
            bx, by = max(0, m["x"]), max(0, m["y"])
            bw, bh = m["w"], m["h"]
            crop = screen_bgr[by:min(h_screen, by + bh), bx:min(w_screen, bx + bw)]
            if crop.size == 0:
                continue

            best_grade = m["grade"]
            best_corr = -1
            for g, tmpl in templates.items():
                t_resized = cv2.resize(tmpl, (crop.shape[1], crop.shape[0]))
                corr = float(cv2.matchTemplate(crop, t_resized, cv2.TM_CCOEFF_NORMED)[0][0])
                if corr > best_corr:
                    best_corr = corr
                    best_grade = g

            m["grade"] = best_grade
            m["score"] = best_corr
            detected_boxes.append(m)

    detected_boxes = sorted(detected_boxes, key=lambda b: b["x"])
    return [b["grade"] for b in detected_boxes]


def detect_anti_bot_odd_cards(screen):
    """
    Return 0-based indices of the 2 cards that differ from the majority 4.
    """
    card_coords = [
        ANTI_BOT_CARD_POS_1,
        ANTI_BOT_CARD_POS_2,
        ANTI_BOT_CARD_POS_3,
        ANTI_BOT_CARD_POS_4,
        ANTI_BOT_CARD_POS_5,
        ANTI_BOT_CARD_POS_6,
    ]

    screen_bgr = _normalize(screen)
    crops = []
    for cx, cy in card_coords:
        crop = screen_bgr[cy:cy + ANTI_BOT_CARD_HEIGHT, cx:cx + ANTI_BOT_CARD_WIDTH]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        crops.append(gray)

    n = len(crops)
    sim = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(n):
            if i != j:
                result = cv2.matchTemplate(crops[i], crops[j], cv2.TM_CCOEFF_NORMED)
                sim[i][j] = result[0][0]

    avg_sim = sim.sum(axis=1) / (n - 1)
    odd_indices = list(np.argsort(avg_sim)[:2])
    return odd_indices


_digit_templates_cache: dict = {}


def _load_digit_templates():
    if not _digit_templates_cache:
        digits_dir = os.path.join(TEMPLATE_DIR, "digits")
        for d in "0123456789":
            p = os.path.join(digits_dir, f"{d}.png")
            if os.path.exists(p):
                _digit_templates_cache[d] = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    return _digit_templates_cache


def extract_result_coins(screen) -> int:
    """
    Extract the exact in-game coins number from the GAME_COMPLETE (Result) screen.
    """
    if screen is None or screen.size == 0:
        return 0

    h, w = screen.shape[:2]
    if (w, h) != (1280, 720):
        screen_1280 = cv2.resize(screen, (1280, 720), interpolation=cv2.INTER_AREA)
    else:
        screen_1280 = screen

    crop = screen_1280[360:450, 750:1150]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 125, 255, cv2.THRESH_BINARY_INV)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if 16 <= bh <= 38 and 4 <= bw <= 34 and x >= 180:
            boxes.append((x, y, bw, bh))

    if not boxes:
        return 0

    boxes = sorted(boxes, key=lambda b: b[0])
    digits = _load_digit_templates()
    if not digits:
        return 0

    digits_str = ""
    for (x, y, bw, bh) in boxes:
        char_img = thresh[y:y+bh, x:x+bw]
        best_d = "0"
        best_score = -1.0
        for d, tmpl in digits.items():
            t_scaled = cv2.resize(tmpl, (char_img.shape[1], char_img.shape[0]))
            res = float(cv2.matchTemplate(char_img, t_scaled, cv2.TM_CCOEFF_NORMED)[0][0])
            if res > best_score:
                best_score = res
                best_d = d
        digits_str += best_d

    try:
        return int(digits_str) if digits_str else 0
    except ValueError:
        return 0


def extract_result_xp(screen) -> int:
    """
    Extract the exact in-game XP number from the GAME_COMPLETE (Result) screen.
    """
    if screen is None or screen.size == 0:
        return 0

    h, w = screen.shape[:2]
    if (w, h) != (1280, 720):
        screen_1280 = cv2.resize(screen, (1280, 720), interpolation=cv2.INTER_AREA)
    else:
        screen_1280 = screen

    crop = screen_1280[440:520, 750:1150]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 125, 255, cv2.THRESH_BINARY_INV)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if 16 <= bh <= 38 and 4 <= bw <= 34 and x >= 180:
            boxes.append((x, y, bw, bh))

    if not boxes:
        return 0

    boxes = sorted(boxes, key=lambda b: b[0])
    digits = _load_digit_templates()
    if not digits:
        return 0

    digits_str = ""
    for (x, y, bw, bh) in boxes:
        char_img = thresh[y:y+bh, x:x+bw]
        best_d = "0"
        best_score = -1.0
        for d, tmpl in digits.items():
            t_scaled = cv2.resize(tmpl, (char_img.shape[1], char_img.shape[0]))
            res = float(cv2.matchTemplate(char_img, t_scaled, cv2.TM_CCOEFF_NORMED)[0][0])
            if res > best_score:
                best_score = res
                best_d = d
        digits_str += best_d

    try:
        return int(digits_str) if digits_str else 0
    except ValueError:
        return 0


def extract_item_stock(screen, item_type: str) -> int:
    """
    Extract the item stock quantity from the PURCHASE_ITEM screen.
    item_type: 'fast_start' or 'cookie_relay'
    Returns integer stock count (0 if no badge/empty).
    """
    if screen is None or screen.size == 0:
        return 0

    h, w = screen.shape[:2]
    if (w, h) != (1280, 720):
        screen_1280 = cv2.resize(screen, (1280, 720), interpolation=cv2.INTER_AREA)
    else:
        screen_1280 = screen

    if item_type == "fast_start":
        # Fast Start item box top right: y: 525..565, x: 235..310
        crop = screen_1280[525:565, 235:310]
    elif item_type == "cookie_relay":
        # Cookie Relay item box top right: y: 525..565, x: 385..460
        crop = screen_1280[525:565, 385:460]
    else:
        return 0

    # Digits are pure white text with black border
    mask = cv2.inRange(crop, (215, 215, 215), (255, 255, 255))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if 14 <= bh <= 30 and 4 <= bw <= 25:
            boxes.append((x, y, bw, bh))

    if not boxes:
        return 0

    boxes = sorted(boxes, key=lambda b: b[0])
    digits = _load_digit_templates()
    if not digits:
        return 0

    digits_str = ""
    for (x, y, bw, bh) in boxes:
        char_img = mask[y:y+bh, x:x+bw]
        best_d = "0"
        best_score = -1.0
        for d, tmpl in digits.items():
            t_scaled = cv2.resize(tmpl, (char_img.shape[1], char_img.shape[0]))
            res = float(cv2.matchTemplate(char_img, t_scaled, cv2.TM_CCOEFF_NORMED)[0][0])
            if res > best_score:
                best_score = res
                best_d = d
        digits_str += best_d

    try:
        return int(digits_str) if digits_str else 0
    except ValueError:
        return 0



def is_announcement_popup_visible(screen) -> bool:
    """
    Heuristic fallback for generic popups (Party Pass etc.) that share the same X at 1126,57.
    Checks the close-button region for a gray circular button with white X — works across all variants
    even if the inner template changes.
    """
    screen_bgr = _normalize(screen)
    if screen_bgr is None:
        return False
    h, w = screen_bgr.shape[:2]
    # region รอบปุ่ม X — ครอบทั้งตำแหน่งเก่า (1126,57) และ variant ใหม่ (1213,89)
    x1, y1, x2, y2 = 1090, 15, 1240, 115
    if w < x2 or h < y2:
        # scale coordinates if screen not 1280x720
        x1, y1, x2, y2 = int(w*0.851), int(h*0.020), int(w*0.969), int(h*0.160)
    crop = screen_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return False
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Close button is light gray (~150-190) on darker background; check for circular blob
    # Simple check: mean std and presence of white X pixels
    _, thresh_white = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY)
    white_ratio = float(np.count_nonzero(thresh_white)) / thresh_white.size
    # X button has ~5-12% white pixels (the X) inside crop
    if 0.02 < white_ratio < 0.18:
        # also check gray circle presence: pixels 110-190
        gray_mask = cv2.inRange(gray, 110, 200)
        gray_ratio = float(np.count_nonzero(gray_mask)) / gray_mask.size
        if gray_ratio > 0.15:
            return True
    return False


def is_emu_home_visible(screen) -> bool:
    """
    Heuristic for Emu launcher home (หลุดมาหน้า Emu).
    Checks 2 cues:
    1) Top search bar: white rounded bar with 'Search for games & apps' near (640, 150)
    2) Store/System apps text row is not same as game UI
    Works without template file; fallback when EMU_HOME_1.png missing.
    """
    screen_bgr = _normalize(screen)
    if screen_bgr is None:
        return False
    h, w = screen_bgr.shape[:2]
    # Expect 1280x720, but scale-safe
    # Search bar region: y 110-180, x 350-920
    x1, y1, x2, y2 = int(w*0.27), int(h*0.13), int(w*0.72), int(h*0.25)
    crop = screen_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return False
    # White bar detection: high V, low S
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    white_mask = cv2.inRange(hsv, (0, 0, 200), (180, 40, 255))
    white_ratio = float(np.count_nonzero(white_mask)) / white_mask.size
    if white_ratio < 0.15:
        return False
    # Icon row check: look for ~3 icons around 537,235 area -> colorful blobs
    # Simple: bottom of search bar + dark background still has icons, but game screens never have this white bar ratio
    # Confirm dark background around
    bg_crop = screen_bgr[int(h*0.30):int(h*0.50), int(w*0.05):int(w*0.55)]
    gray = cv2.cvtColor(bg_crop, cv2.COLOR_BGR2GRAY)
    mean_val = float(np.mean(gray))
    # Emu home has dark overlay ~20-50 mean, game screens are brighter (~70+)
    if mean_val > 60:
        return False
    return True


def detect_result_screen_mystery_box(screen) -> list:
    """
    Checks the Result screen (GAME_COMPLETE) to see if mystery boxes were obtained.
    Returns a list of detected box grades (e.g. ['wood']).
    """
    screen_bgr = _normalize(screen)
    if screen_bgr is None:
        return []

    h, w = screen_bgr.shape[:2]
    # Crop right of the score area: x: 55% to 85%, y: 35% to 55%
    x1, x2 = int(w * 0.55), int(w * 0.85)
    y1, y2 = int(h * 0.35), int(h * 0.55)
    crop = screen_bgr[y1:y2, x1:x2]

    tmpl = _get_template("RESULT_BOX_BADGE.png")
    if tmpl is None:
        return []

    crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    tmpl_gray = _get_template_gray("RESULT_BOX_BADGE.png")
    if tmpl_gray is None:
        return []

    res = cv2.matchTemplate(crop_gray, tmpl_gray, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)

    if max_val >= 0.70:
        return ["wood"]  # Result screen shows mystery box badge
    return []
