import random
import time

import config

def _human_sleep(a: float = 0.8, b: float = 1.4):
    """gauss แทน uniform — กันจับ timing ตายตัว, 3% ลังเลเพิ่ม 1-2.5s"""
    mid = (a + b) / 2
    sigma = (b - a) / 3.5
    v = random.gauss(mid, sigma)
    v = max(a, min(b, v))
    if random.random() < 0.03:
        v += random.uniform(1.0, 2.5)
    time.sleep(v)
from adb import safe_device_tap, safe_device_scroll, safe_device_long_press, device_capture_screen
from config import (
    ACCEPT_ALL_LIVES_RECEIVED_AND_SENT_BUTTON,
    ACCEPT_CONGRATULATIONS_BUTTON,
    ACCEPT_DAILY_CHECKIN_BOOST_SET_BUTTON,
    ACCEPT_DAILY_CHECKIN_BUTTON,
    ACCEPT_DAILY_TREASURE_BUTTON,
    ACCEPT_DAILY_NEW_BUTTON,
    ACCEPT_ENTER_LEAGUE_BUTTON,
    ACCEPT_LEAGUE_RESULTS_BUTTON,
    ACCEPT_LEVEL_UP_BUTTON,
    ACCEPT_MYSTERY_BOX_BUTTON,
    ACCEPT_OVERTAKE_BREAK_SCORE_BUTTON,
    ACCEPT_PREVIOUS_RANK_RESULTS_BUTTON,
    ACCEPT_TOO_MANY_TREASURES_BUTTON,
    ALL_LIVES_RECEIVED_AND_SENT_REGION,
    ALL_LIVES_RECEIVED_AND_SENT_TEMPLATE,
    ANNOUNCEMENT_CLOSE_BUTTON,
    ANR_WAIT_BUTTON,
    BOOST_DOUBLE_XP_CHECKED_TEMPLATE,
    BOOST_HP_EXTENSION_CHECKED_TEMPLATE,
    BOOST_POWER_JELLY_CHECKED_TEMPLATE,
    CLOSE_ANNOUNCEMENT_DIALOG_BUTTON,
    CLOSE_FRIEND_INFO_POPUP_BUTTON,
    CLOSE_SEND_LIFE_DIALOG_BUTTON,
    COMPLETE_FINISH_BUTTON,
    CONFIRM_SEND_LIFE_BUTTON,
    CONFIRM_SEND_LIFE_REGION,
    CONFIRM_SEND_LIFE_TEMPLATE,
    COOKIE_RELAY_ITEM,
    COOKIE_RELAY_USE_BUTTON,
    DOUBLE_XP_REGION,
    DOUBLE_XP_TAP_POS,
    EXIT_GAME_SETTINGS_BUTTON,
    EXIT_PARTY_RUN_MODE_BUTTON,
    FAST_START_ITEM,
    FAST_START_USE_BUTTON,
    FRIEND_BOTTOM_LEADERBOARD_REGION,
    JUMP_BUTTON,
    SLIDE_BUTTON,
    FRIEND_BOTTOM_LEADERBOARD_TEMPLATE,
    FRIEND_SEND_LIFE_REGION,
    FRIEND_SEND_LIFE_TEMPLATE,
    FRIEND_TOP_LEADERBOARD_REGION,
    FRIEND_TOP_LEADERBOARD_TEMPLATE,
    HP_EXTENSION_REGION,
    HP_EXTENSION_TAP_POS,
    INACTIVE_RELOAD_BUTTON,
    LEADERBOARD_BOTTOM_POSITION,
    LEADERBOARD_TOP_POSITION,
    MAIL_BOX_BUTTON,
    MAIL_BOX_LIVES_TAB_BUTTON,
    MAIL_BOX_CLOSE_BUTTON,
    MULTI_BUY_BUTTON,
    MULTI_PURCHASE_BUTTON,
    NO_LIVES_TO_RECEIVE_REGION,
    NO_LIVES_TO_RECEIVE_TEMPLATE,
    PLAY_BUTTON,
    POWER_JELLY_REGION,
    POWER_JELLY_TAP_POS,
    PURCHASE_BUTTON,
    QUICK_RECEIVE_AND_SEND_LIVES_BUTTON,
    RANDOM_BOOST_ITEM,
    RANDOM_BOOST_REGION,
    RELIC_CLAIM_BUTTON,
    RELIC_CLOSE_BUTTON,
    RELIC_COMPLETE_BUTTON,
    START_BUTTON,
    CONNECTION_LOST_RELOAD_BUTTON,
)
from detection import detect_templates, detect_anti_bot_odd_cards, detect_stage, find_close_x_button, find_green_ok_button
from config import (
    ANTI_BOT_CARD_POS_1, ANTI_BOT_CARD_POS_2, ANTI_BOT_CARD_POS_3,
    ANTI_BOT_CARD_POS_4, ANTI_BOT_CARD_POS_5, ANTI_BOT_CARD_POS_6,
    ANTI_BOT_CARD_WIDTH, ANTI_BOT_CARD_HEIGHT,
)

def _resolve_device(device_ip=None, device_port=None):
    """Resolve device ip/port — explicit args take precedence, fallback to legacy config global."""
    ip = device_ip if device_ip is not None else config.DEVICE_IP
    port = device_port if device_port is not None else config.DEVICE_PORT
    return ip, port

def start_game(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🏁 Starting the game on {ip}:{port}...")
    safe_device_tap(ip, port, START_BUTTON[0], START_BUTTON[1])
    _human_sleep(0.8, 1.4)


def play_game(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🎮 Playing the game on {ip}:{port}...")
    safe_device_tap(ip, port, PLAY_BUTTON[0], PLAY_BUTTON[1])
    # รอ screen โหลด (เข้าหน้าจอเริ่มเกม) ก่อนตรวจจับ GAME_START — กันกดเร็วเกินเกมไม่ทัน
    _human_sleep(1.5, 2.5)


def purchase_fast_start(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🛒 Purchasing Fast Start...")
    safe_device_tap(ip, port, FAST_START_ITEM[0], FAST_START_ITEM[1])
    _human_sleep(1.0, 1.8)
    # TODO: ต้องการ template ปุ่ม Buy สีฟ้า (PURCHASE_BUTTON) เพื่อเช็คด้วย detect_templates()
    # ปัจจุบันยังไม่มีไฟล์ PURCHASE_BUTTON_TEMPLATE ใน templates/ จึงใช้ sleep รอ popup แทน
    # ถ้ามีภาพจริงของปุ่ม Buy ให้แจ้ง จะสร้าง template แล้วแก้ loop เป็น:
    # for _ in range(6):
    #     chk = device_capture_screen(ip, port)
    #     if chk is not None and detect_templates(chk, PURCHASE_BUTTON_TEMPLATE, PURCHASE_BUTTON_REGION):
    #         break
    #     time.sleep(0.3)
    time.sleep(0.9)
    time.sleep(random.uniform(1, 2))


def purchase_cookie_relay(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🛒 Purchasing Cookie Relay...")
    safe_device_tap(ip, port, COOKIE_RELAY_ITEM[0], COOKIE_RELAY_ITEM[1])
    _human_sleep(1.0, 1.8)
    # TODO: ต้องการ template ปุ่ม Buy สีฟ้า (PURCHASE_BUTTON) เพื่อเช็คด้วย detect_templates()
    # ปัจจุบันยังไม่มีไฟล์ PURCHASE_BUTTON_TEMPLATE ใน templates/ จึงใช้ sleep รอ popup แทน
    # ถ้ามีภาพจริงของปุ่ม Buy ให้แจ้ง จะสร้าง template แล้วแก้ loop เป็น:
    # for _ in range(6):
    #     chk = device_capture_screen(ip, port)
    #     if chk is not None and detect_templates(chk, PURCHASE_BUTTON_TEMPLATE, PURCHASE_BUTTON_REGION):
    #         break
    #     time.sleep(0.3)
    time.sleep(0.9)
    time.sleep(random.uniform(1, 2))


def purchase_random_boost(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🛒 Purchasing Random Boost...")
    safe_device_tap(ip, port, RANDOM_BOOST_ITEM[0], RANDOM_BOOST_ITEM[1])
    _human_sleep(1.5, 2.5)
    safe_device_tap(ip, port, PURCHASE_BUTTON[0], PURCHASE_BUTTON[1])
    time.sleep(random.uniform(2.0, 3.0))


def purchase_desired_random_boost(desired_template, desired_name, device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🛒 Purchasing Desired Random Boost...")
    safe_device_tap(ip, port, RANDOM_BOOST_ITEM[0], RANDOM_BOOST_ITEM[1])
    _human_sleep(1.5, 2.5)  # รอ popup โผล่ก่อนกดปุ่มถัดไป
    safe_device_tap(ip, port, MULTI_PURCHASE_BUTTON[0], MULTI_PURCHASE_BUTTON[1])
    time.sleep(random.uniform(2.0, 3.0))  # รอ popup ซื้อโหลดเสร็จ
    safe_device_tap(ip, port, MULTI_BUY_BUTTON[0], MULTI_BUY_BUTTON[1])
    _human_sleep(1.5, 2.5)  # รอ animation ซื้อเสร็จ
    print(f"🔍 Waiting for desired boost to be detected: {desired_name}...")
    timeout = 30
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            print(f"⏰ Timeout: Could not detect desired boost '{desired_name}' within {timeout} seconds.")
            print("⚠️ Skipping Desired Random Boost. Please verify your in-game boost config is correct.")
            return
        screen = device_capture_screen(ip, port)
        if detect_templates(screen, desired_template, RANDOM_BOOST_REGION):
            print(f"✅ Desired Boost detected: {desired_name}!")
            break
        time.sleep(random.uniform(0.8, 1.2))


def using_fast_start(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"⚡ Using Fast Start at {FAST_START_USE_BUTTON} (jitter +-15) on {ip}:{port}...")
    # กดครั้งเดียว — ถ้าไม่ติด loop ตรวจจับ GAME_START จะเรียกใหม่เอง (กันกดเบิ้ล)
    safe_device_tap(ip, port, FAST_START_USE_BUTTON[0], FAST_START_USE_BUTTON[1])
    _human_sleep(1.2, 1.8)


def using_cookie_relay(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🍪 Using Cookie Relay at {COOKIE_RELAY_USE_BUTTON} (jitter +-15) on {ip}:{port}...")
    # กดครั้งเดียว — ถ้าไม่ติด loop ตรวจจับ GAME_RELAY จะเรียกใหม่เอง (กันกดเบิ้ล)
    safe_device_tap(ip, port, COOKIE_RELAY_USE_BUTTON[0], COOKIE_RELAY_USE_BUTTON[1])
    _human_sleep(1.2, 1.8)


def complete_finish(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🏆 Completing the game on {ip}:{port}...")
    x, y = COMPLETE_FINISH_BUTTON
    try:
        screen = device_capture_screen(ip, port)
        if screen is not None:
            pos = find_green_ok_button(screen)
            if pos:
                x, y = pos
                print(f"🟢 OK button found at {pos} (dynamic)")
    except Exception:
        pass
    safe_device_tap(ip, port, x, y)
    time.sleep(random.uniform(1.8, 2.4))


def humanlike_jump(device_ip=None, device_port=None):
    """กระโดด 1 ครั้ง (tap สั้นที่ปุ่ม Jump) — เล่นเสมือนมนุษย์"""
    ip, port = _resolve_device(device_ip, device_port)
    safe_device_tap(ip, port, JUMP_BUTTON[0], JUMP_BUTTON[1])


def humanlike_jump_double(device_ip=None, device_port=None, gap=0.4):
    """กระโดด 2 ครั้งติด (double jump) ห่างกันตาม gap วินาที ±เล็กน้อย"""
    ip, port = _resolve_device(device_ip, device_port)
    safe_device_tap(ip, port, JUMP_BUTTON[0], JUMP_BUTTON[1])
    time.sleep(max(0.05, gap + random.uniform(-0.05, 0.05)))
    safe_device_tap(ip, port, JUMP_BUTTON[0], JUMP_BUTTON[1])


def humanlike_slide(device_ip=None, device_port=None, hold_duration=0.8):
    """กดค้างที่ปุ่ม Slide นาน hold_duration วินาที (long-press ที่จุดเดิม)"""
    ip, port = _resolve_device(device_ip, device_port)
    ms = int(hold_duration * 1000)
    safe_device_long_press(ip, port, SLIDE_BUTTON[0], SLIDE_BUTTON[1], duration_ms=ms)


def accept_mystery_box(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🎁 Opening Mystery Boxes...")
    safe_device_tap(ip, port, ACCEPT_MYSTERY_BOX_BUTTON[0], ACCEPT_MYSTERY_BOX_BUTTON[1])
    time.sleep(random.uniform(1.8, 2.4))
    safe_device_tap(ip, port, ACCEPT_MYSTERY_BOX_BUTTON[0], ACCEPT_MYSTERY_BOX_BUTTON[1])
    time.sleep(random.uniform(1.0, 1.5))


def accept_congratulations(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🎉 Accepting Congratulations...")
    safe_device_tap(ip, port, ACCEPT_CONGRATULATIONS_BUTTON[0], ACCEPT_CONGRATULATIONS_BUTTON[1])
    _human_sleep(0.8, 1.4)


def accept_level_up(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("⬆️ Accepting Level Up...")
    safe_device_tap(ip, port, ACCEPT_LEVEL_UP_BUTTON[0], ACCEPT_LEVEL_UP_BUTTON[1])
    _human_sleep(0.8, 1.4)


def accept_daily_checkin(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("📅 Accepting Daily Check-in...")
    safe_device_tap(ip, port, ACCEPT_DAILY_CHECKIN_BUTTON[0], ACCEPT_DAILY_CHECKIN_BUTTON[1])
    _human_sleep(0.8, 1.4)


def accept_daily_checkin_boost_set(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("📅 Accepting Daily Check-in Boost Set...")
    safe_device_tap(ip, port, ACCEPT_DAILY_CHECKIN_BOOST_SET_BUTTON[0], ACCEPT_DAILY_CHECKIN_BOOST_SET_BUTTON[1])
    _human_sleep(0.8, 1.4)


def accept_daily_treasure(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("💎 Accepting Daily Treasure...")
    safe_device_tap(ip, port, ACCEPT_DAILY_TREASURE_BUTTON[0], ACCEPT_DAILY_TREASURE_BUTTON[1])
    _human_sleep(0.8, 1.4)


def accept_daily_new(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("📰 Accepting Daily New...")
    safe_device_tap(ip, port, ACCEPT_DAILY_NEW_BUTTON[0], ACCEPT_DAILY_NEW_BUTTON[1])
    _human_sleep(0.8, 1.4)


def accept_enter_league(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🏆 Accepting Enter League...")
    safe_device_tap(ip, port, ACCEPT_ENTER_LEAGUE_BUTTON[0], ACCEPT_ENTER_LEAGUE_BUTTON[1])
    _human_sleep(0.8, 1.4)


def accept_league_results(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🏆 Accepting League Results...")
    safe_device_tap(ip, port, ACCEPT_LEAGUE_RESULTS_BUTTON[0], ACCEPT_LEAGUE_RESULTS_BUTTON[1])
    _human_sleep(0.8, 1.4)


def accept_previous_rank_results(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🏆 Accepting Previous Rank Results...")
    safe_device_tap(ip, port, ACCEPT_PREVIOUS_RANK_RESULTS_BUTTON[0], ACCEPT_PREVIOUS_RANK_RESULTS_BUTTON[1])
    _human_sleep(0.8, 1.4)


def accept_too_many_treasures(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("💎 Accepting Too Many Treasures...")
    safe_device_tap(ip, port, ACCEPT_TOO_MANY_TREASURES_BUTTON[0], ACCEPT_TOO_MANY_TREASURES_BUTTON[1])
    _human_sleep(0.8, 1.4)


def accept_overtake_break_score(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🏆 Accepting Overtake Break Score...")
    safe_device_tap(ip, port, ACCEPT_OVERTAKE_BREAK_SCORE_BUTTON[0], ACCEPT_OVERTAKE_BREAK_SCORE_BUTTON[1])
    _human_sleep(0.8, 1.4)


def open_relic_complete(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🏺 Opening Relic Complete...")
    safe_device_tap(ip, port, RELIC_COMPLETE_BUTTON[0], RELIC_COMPLETE_BUTTON[1])
    _human_sleep(0.8, 1.4)


def accept_relic_claim(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🏺 Accepting Relic Claim...")
    safe_device_tap(ip, port, RELIC_CLAIM_BUTTON[0], RELIC_CLAIM_BUTTON[1])
    _human_sleep(0.8, 1.4)
    safe_device_tap(ip, port, RELIC_CLOSE_BUTTON[0], RELIC_CLOSE_BUTTON[1])
    time.sleep(random.uniform(10, 15))


def handle_anti_bot(screen, device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🤖 Solving Anti-Bot captcha on {ip}:{port}...")
    card_coords = [
        ANTI_BOT_CARD_POS_1, ANTI_BOT_CARD_POS_2, ANTI_BOT_CARD_POS_3,
        ANTI_BOT_CARD_POS_4, ANTI_BOT_CARD_POS_5, ANTI_BOT_CARD_POS_6,
    ]

    odd_indices = detect_anti_bot_odd_cards(screen)
    card_nums = [i + 1 for i in odd_indices]
    print(f"🃏 Found odd cards: Card {card_nums[0]} and Card {card_nums[1]}")

    for idx in odd_indices:
        cx, cy = card_coords[idx]
        margin = 20
        tx = random.randint(cx + margin, cx + ANTI_BOT_CARD_WIDTH - margin)
        ty = random.randint(cy + margin, cy + ANTI_BOT_CARD_HEIGHT - margin)
        print(f"  👆 Tapping Card {idx + 1} at ({tx}, {ty})")
        safe_device_tap(ip, port, tx, ty)
        time.sleep(random.uniform(10, 15))

    print("✅ Anti-Bot captcha solved!")
    _human_sleep(0.8, 1.4)


def handle_connection_lost(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🔌 Handling Connection Lost on {ip}:{port}...")
    safe_device_tap(ip, port, CONNECTION_LOST_RELOAD_BUTTON[0], CONNECTION_LOST_RELOAD_BUTTON[1])
    time.sleep(random.uniform(10, 15))


def handle_inactive(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"💤 Handling Inactive state on {ip}:{port}...")
    safe_device_tap(ip, port, INACTIVE_RELOAD_BUTTON[0], INACTIVE_RELOAD_BUTTON[1])
    time.sleep(random.uniform(10, 15))


def handle_send_friend_life(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"💌 Handling Send Friend Life on {ip}:{port}...")
    screen = device_capture_screen(ip, port)
    while True:
        if detect_templates(screen, FRIEND_TOP_LEADERBOARD_TEMPLATE, FRIEND_TOP_LEADERBOARD_REGION):
            print("✅ Top of Friend Leaderboard reached.")
            break
        print("🔄 Scrolling up to find Send Friend Life...")
        safe_device_scroll(ip, port, LEADERBOARD_BOTTOM_POSITION[0], LEADERBOARD_BOTTOM_POSITION[1], direction="down", distance=random.randint(285, 320), duration=random.randint(130, 175))
        time.sleep(random.uniform(0.85, 1.45))
        screen = device_capture_screen(ip, port)
    no_button_scroll_count = 0
    while True:
        screen = device_capture_screen(ip, port)
        if detect_templates(screen, FRIEND_BOTTOM_LEADERBOARD_TEMPLATE, FRIEND_BOTTOM_LEADERBOARD_REGION):
            print("✅ Bottom of Friend Leaderboard reached. Done sending lives.")
            break
        send_life_button_coords = detect_templates(screen, FRIEND_SEND_LIFE_TEMPLATE, FRIEND_SEND_LIFE_REGION)
        if send_life_button_coords:
            no_button_scroll_count = 0
            for x, y, w, h in send_life_button_coords:
                print("💌 Sending life to friend...")
                safe_device_tap(ip, port, x + w // 2, y + h // 2)
                _human_sleep(0.8, 1.4)
                print("💌 Confirming send life...")
                safe_device_tap(ip, port, CONFIRM_SEND_LIFE_BUTTON[0], CONFIRM_SEND_LIFE_BUTTON[1])
                _human_sleep(0.8, 1.4)
                print("💌 Closing send life dialog...")
                safe_device_tap(ip, port, CLOSE_SEND_LIFE_DIALOG_BUTTON[0], CLOSE_SEND_LIFE_DIALOG_BUTTON[1])
                _human_sleep(0.8, 1.4)
        else:
            no_button_scroll_count += 1
            if no_button_scroll_count >= 30:
                print("⚠️ No send life buttons found for 30 consecutive scrolls. Giving up.")
                break
            print(f"🔄 No send life buttons found, scrolling down... ({no_button_scroll_count}/30)")
            safe_device_scroll(ip, port, LEADERBOARD_TOP_POSITION[0], LEADERBOARD_TOP_POSITION[1], direction="up", distance=random.randint(62, 82), duration=random.randint(125, 175))
            time.sleep(random.uniform(0.85, 1.45))


def handle_quick_receive_and_send_lives(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"✉️ Handling Quick Receive and Send Lives on {ip}:{port}...")
    _human_sleep(0.8, 1.4)
    safe_device_tap(ip, port, MAIL_BOX_BUTTON[0], MAIL_BOX_BUTTON[1])
    _human_sleep(0.8, 1.4)
    safe_device_tap(ip, port, MAIL_BOX_LIVES_TAB_BUTTON[0], MAIL_BOX_LIVES_TAB_BUTTON[1])
    _human_sleep(0.8, 1.4)
    screen = device_capture_screen(ip, port)
    if detect_templates(screen, NO_LIVES_TO_RECEIVE_TEMPLATE, NO_LIVES_TO_RECEIVE_REGION):
        print("✉️ No lives to receive. Proceeding to send lives...")
        safe_device_tap(ip, port, MAIL_BOX_CLOSE_BUTTON[0], MAIL_BOX_CLOSE_BUTTON[1])
        return
    print("✉️ Receiving all lives...")
    safe_device_tap(ip, port, QUICK_RECEIVE_AND_SEND_LIVES_BUTTON[0], QUICK_RECEIVE_AND_SEND_LIVES_BUTTON[1])
    _human_sleep(0.8, 1.4)
    while True:
        screen = device_capture_screen(ip, port)
        all_lives_received_and_sent = detect_templates(screen, ALL_LIVES_RECEIVED_AND_SENT_TEMPLATE, ALL_LIVES_RECEIVED_AND_SENT_REGION)
        if all_lives_received_and_sent:
            print("✉️ All lives received and sent. Done!")
            safe_device_tap(ip, port, ACCEPT_ALL_LIVES_RECEIVED_AND_SENT_BUTTON[0], ACCEPT_ALL_LIVES_RECEIVED_AND_SENT_BUTTON[1])
            _human_sleep(0.8, 1.4)
            safe_device_tap(ip, port, MAIL_BOX_CLOSE_BUTTON[0], MAIL_BOX_CLOSE_BUTTON[1])
            _human_sleep(0.8, 1.4)
            break
        confirm_send_life_button_coords = detect_templates(screen, CONFIRM_SEND_LIFE_TEMPLATE, CONFIRM_SEND_LIFE_REGION)
        if confirm_send_life_button_coords:
            print("✉️ Sending lives to friends...")
            safe_device_tap(ip, port, CONFIRM_SEND_LIFE_BUTTON[0], CONFIRM_SEND_LIFE_BUTTON[1])
            _human_sleep(0.8, 1.4)
    print("✉️ Quick Receive and Send Lives completed.")


def close_announcement_popup(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    pos = _find_close_x_pos(ip, port) or ANNOUNCEMENT_CLOSE_BUTTON
    print(f"❌ Closing generic announcement popup at {pos} on {ip}:{port}...")
    safe_device_tap(ip, port, pos[0], pos[1])
    _human_sleep(0.8, 1.4)


def close_friend_info_popup(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"❌ Closing Friend's Info popup on {ip}:{port}...")
    # ใช้ tap แบบแม่นยำ + retry ถ้ายังไม่ปิด (popup บางทีต้องกด 2 ครั้งหรือดีเลย์นาน)
    for attempt in range(2):
        safe_device_tap(ip, port, CLOSE_FRIEND_INFO_POPUP_BUTTON[0], CLOSE_FRIEND_INFO_POPUP_BUTTON[1])
        _human_sleep(0.8, 1.4)
        try:
            chk = device_capture_screen(ip, port)
            if detect_stage(chk, ["FRIEND_INFO_POPUP"]) != "FRIEND_INFO_POPUP":
                print(f"✅ Friend's Info closed on attempt {attempt+1}")
                break
            print(f"⚠️ Still visible after attempt {attempt+1}, retrying...")
        except Exception:
            break


def _find_close_x_pos(ip, port):
    """capture หน้าจอแล้วหา X close แบบ dynamic — คืน (x,y) หรือ None (fallback ให้ config)"""
    try:
        screen = device_capture_screen(ip, port)
        return find_close_x_button(screen)
    except Exception:
        return None


def close_announcement_dialog(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🖱️ Closing announcement dialog on {ip}:{port}...")
    # กด X แล้วตรวจว่า X หายแล้วไหม — หยุดทันทีที่ปิดได้ (ไม่กดรัวๆ 4-6 ครั้งแบบเดิม)
    for attempt in range(3):
        pos = _find_close_x_pos(ip, port)
        if pos is None:
            print("✅ ไม่พบปุ่ม X แล้ว — popup ปิดเรียบร้อย")
            break
        print(f"🖱️ Tapping close X at {pos} (attempt {attempt+1}/3)")
        safe_device_tap(ip, port, pos[0], pos[1])
        _human_sleep(0.8, 1.4)
    _human_sleep(0.8, 1.4)
    device_screen = device_capture_screen(ip, port)
    # ตรวจ popup ก่อนเสมอ — กัน PARTY_RUN/GAME_SETTINGS false positive ตอน popup ยังเปิดอยู่
    if detect_stage(device_screen, ["ANNOUNCEMENT_POPUP"]) == "ANNOUNCEMENT_POPUP":
        close_announcement_popup(ip, port)
    elif detect_stage(device_screen, ["PARTY_RUN"]) == "PARTY_RUN":
        close_party_run_mode(ip, port)
    elif detect_stage(device_screen, ["GAME_SETTINGS"]) == "GAME_SETTINGS":
        close_game_settings(ip, port)


def close_party_run_mode(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🖱️ Closing Party Run mode on {ip}:{port}...")
    safe_device_tap(ip, port, EXIT_PARTY_RUN_MODE_BUTTON[0], EXIT_PARTY_RUN_MODE_BUTTON[1])
    _human_sleep(0.8, 1.4)


def close_game_settings(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🖱️ Closing Game Settings on {ip}:{port}...")
    safe_device_tap(ip, port, EXIT_GAME_SETTINGS_BUTTON[0], EXIT_GAME_SETTINGS_BUTTON[1])
    _human_sleep(0.8, 1.4)


def handle_emu_home(device_ip=None, device_port=None):
    """กดไอคอน CookieRun Classic ที่หน้า Emu Home เมื่อหลุดมาหน้าหลัก"""
    from config import EMU_HOME_TAP
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🏠 Detected EMU_HOME — tapping CookieRun Classic at {EMU_HOME_TAP} on {ip}:{port}...")
    safe_device_tap(ip, port, EMU_HOME_TAP[0], EMU_HOME_TAP[1])
    time.sleep(random.uniform(4, 6))


def tap_confirm_popup(device_ip=None, device_port=None):
    """กดปุ่ม Confirm เขียวใหญ่กลางหน้าต่างยืนยัน — กดครั้งเดียว + รอ (กันกดรัวๆ)"""
    ip, port = _resolve_device(device_ip, device_port)
    from config import CONFIRM_POPUP_TAP

    print(f"✅ Tapping CONFIRM at {CONFIRM_POPUP_TAP} on {ip}:{port}...")
    safe_device_tap(ip, port, CONFIRM_POPUP_TAP[0], CONFIRM_POPUP_TAP[1])
    _human_sleep(1.2, 1.8)


def handle_anr(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"⚠️ Handling ANR dialog on {ip}:{port}... tapping Wait at {ANR_WAIT_BUTTON}")
    safe_device_tap(ip, port, ANR_WAIT_BUTTON[0], ANR_WAIT_BUTTON[1])
    time.sleep(random.uniform(2.5, 3.5))


def _is_boost_checked_by_color(screen, region) -> bool:
    """ตรวจสีพื้นหลังเหลือง(ติ๊ก) vs เขียว(ไม่ติ๊ก) + tick เขียวมุมขวาล่าง — ทนต่อ template ไม่ตรง"""
    import cv2
    import numpy as np
    x1, y1, x2, y2 = region
    h, w = screen.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    crop = screen[y1:y2, x1:x2]
    if crop.size == 0:
        return False
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, np.array([18, 80, 180]), np.array([30, 255, 255]))
    yellow_ratio = np.count_nonzero(yellow) / (crop.shape[0]*crop.shape[1])
    ch, cw = crop.shape[:2]
    tx1, ty1 = max(0, cw-26), max(0, ch-26)
    tick_roi = crop[ty1:ty1+20, tx1:tx1+20]
    if tick_roi.size:
        tick_hsv = cv2.cvtColor(tick_roi, cv2.COLOR_BGR2HSV)
        tick_green = cv2.inRange(tick_hsv, np.array([35, 60, 80]), np.array([85, 255, 255]))
        tick_ratio = np.count_nonzero(tick_green) / 400
    else:
        tick_ratio = 0
    return yellow_ratio > 0.18 and tick_ratio > 0.12


def _is_boost_unchecked_by_color(screen, region) -> bool:
    """ตรงข้าม: เขียวเยอะ + ไม่มีเหลือง"""
    import cv2
    import numpy as np
    x1, y1, x2, y2 = region
    h, w = screen.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    crop = screen[y1:y2, x1:x2]
    if crop.size == 0:
        return False
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, np.array([35, 60, 100]), np.array([75, 255, 255]))
    yellow = cv2.inRange(hsv, np.array([18, 80, 180]), np.array([30, 255, 255]))
    green_ratio = np.count_nonzero(green) / (crop.shape[0]*crop.shape[1])
    yellow_ratio = np.count_nonzero(yellow) / (crop.shape[0]*crop.shape[1])
    return green_ratio > 0.25 and yellow_ratio < 0.10


def sync_boost_selection(desired_hp_ext, desired_power_jelly, desired_double_xp, device_ip=None, device_port=None):
    """เช็คสถานะติ๊กปัจจุบันของ 3 boost แล้วปรับให้ตรงกับค่าที่ต้องการ (desired_*: True/False)"""
    ip, port = _resolve_device(device_ip, device_port)
    screen = device_capture_screen(ip, port)

    items = [
        ("HP_EXTENSION", desired_hp_ext, HP_EXTENSION_REGION, HP_EXTENSION_TAP_POS, BOOST_HP_EXTENSION_CHECKED_TEMPLATE),
        ("POWER_JELLY", desired_power_jelly, POWER_JELLY_REGION, POWER_JELLY_TAP_POS, BOOST_POWER_JELLY_CHECKED_TEMPLATE),
        ("DOUBLE_XP", desired_double_xp, DOUBLE_XP_REGION, DOUBLE_XP_TAP_POS, BOOST_DOUBLE_XP_CHECKED_TEMPLATE),
    ]

    for name, desired, region, tap_pos, checked_template in items:
        # ใช้สีเป็นหลัก (เหลือง+tick) ทน template สังเคราะห์/สเกลไม่ตรง
        color_hit = _is_boost_checked_by_color(screen, region)
        # template เป็นตัวเสริมยืนยันเฉพาะเมื่อสีชัดเจน
        tmpl_hit = detect_templates(screen, checked_template, region)
        # ถ้าสีบอกว่า checked → ถือว่า checked (template อาจ false positive/negative)
        # ถ้าสีบอกว่า unchecked แต่ template บอก checked ด้วย score สูง → ให้เชื่อสี
        is_checked = color_hit
        # เก็บ tmpl ไว้ debug แต่ไม่ใช้กำหนด is_checked เพื่อกันเคส Power Jelly ทั้งคู่ hit
        if tmpl_hit and color_hit:
            src = "color+tmpl"
        elif color_hit:
            src = "color"
        elif tmpl_hit:
            src = "tmpl(ignored)"
            is_checked = False  # สีบอกว่าไม่เหลือง ให้เชื่อสีว่า unchecked
        else:
            src = "none"
        if desired and not is_checked:
            print(f"✅ Enabling {name}... (is_checked={is_checked} src={src} desired=ON)")
            safe_device_tap(ip, port, tap_pos[0], tap_pos[1])
            time.sleep(random.uniform(1.2, 1.8))
            try:
                screen = device_capture_screen(ip, port)
            except Exception:
                pass
        elif not desired and is_checked:
            print(f"❌ Disabling {name}... (is_checked={is_checked} src={src} desired=OFF)")
            safe_device_tap(ip, port, tap_pos[0], tap_pos[1])
            time.sleep(random.uniform(1.2, 1.8))
            try:
                screen = device_capture_screen(ip, port)
            except Exception:
                pass
        else:
            print(f"➖ {name} already {'checked' if is_checked else 'unchecked'} as desired ({'ON' if desired else 'OFF'}) src={src}")
