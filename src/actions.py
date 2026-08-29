import random
import time

import config
from adb import safe_device_tap, safe_device_scroll, device_capture_screen
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
    CLOSE_ANNOUNCEMENT_DIALOG_BUTTON,
    CLOSE_SEND_LIFE_DIALOG_BUTTON,
    COMPLETE_FINISH_BUTTON,
    CONFIRM_SEND_LIFE_BUTTON,
    CONFIRM_SEND_LIFE_REGION,
    CONFIRM_SEND_LIFE_TEMPLATE,
    COOKIE_RELAY_ITEM,
    COOKIE_RELAY_USE_BUTTON,
    EXIT_GAME_SETTINGS_BUTTON,
    EXIT_PARTY_RUN_MODE_BUTTON,
    FAST_START_ITEM,
    FAST_START_USE_BUTTON,
    FRIEND_BOTTOM_LEADERBOARD_REGION,
    FRIEND_BOTTOM_LEADERBOARD_TEMPLATE,
    FRIEND_SEND_LIFE_REGION,
    FRIEND_SEND_LIFE_TEMPLATE,
    FRIEND_TOP_LEADERBOARD_REGION,
    FRIEND_TOP_LEADERBOARD_TEMPLATE,
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
from detection import detect_templates, detect_anti_bot_odd_cards, detect_stage
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
    time.sleep(random.uniform(0.8, 1.4))


def play_game(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🎮 Playing the game on {ip}:{port}...")
    safe_device_tap(ip, port, PLAY_BUTTON[0], PLAY_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def purchase_fast_start(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🛒 Purchasing Fast Start...")
    safe_device_tap(ip, port, FAST_START_ITEM[0], FAST_START_ITEM[1])
    time.sleep(random.uniform(0.8, 1.4))
    safe_device_tap(ip, port, PURCHASE_BUTTON[0], PURCHASE_BUTTON[1])
    time.sleep(random.uniform(1, 2))


def purchase_cookie_relay(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🛒 Purchasing Cookie Relay...")
    safe_device_tap(ip, port, COOKIE_RELAY_ITEM[0], COOKIE_RELAY_ITEM[1])
    time.sleep(random.uniform(0.8, 1.4))
    safe_device_tap(ip, port, PURCHASE_BUTTON[0], PURCHASE_BUTTON[1])
    time.sleep(random.uniform(1, 2))


def purchase_random_boost(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🛒 Purchasing Random Boost...")
    safe_device_tap(ip, port, RANDOM_BOOST_ITEM[0], RANDOM_BOOST_ITEM[1])
    time.sleep(random.uniform(0.8, 1.4))
    safe_device_tap(ip, port, PURCHASE_BUTTON[0], PURCHASE_BUTTON[1])
    time.sleep(random.uniform(1, 2))


def purchase_desired_random_boost(desired_template, desired_name, device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🛒 Purchasing Desired Random Boost...")
    safe_device_tap(ip, port, RANDOM_BOOST_ITEM[0], RANDOM_BOOST_ITEM[1])
    time.sleep(random.uniform(0.8, 1.4))
    safe_device_tap(ip, port, MULTI_PURCHASE_BUTTON[0], MULTI_PURCHASE_BUTTON[1])
    time.sleep(random.uniform(1, 2))
    safe_device_tap(ip, port, MULTI_BUY_BUTTON[0], MULTI_BUY_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))
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
        time.sleep(random.uniform(0.35, 0.65))


def using_fast_start(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"⚡ Using Fast Start at {FAST_START_USE_BUTTON} (jitter +-15) on {ip}:{port}...")
    safe_device_tap(ip, port, FAST_START_USE_BUTTON[0], FAST_START_USE_BUTTON[1])
    time.sleep(random.uniform(0.5, 0.8))
    safe_device_tap(ip, port, FAST_START_USE_BUTTON[0], FAST_START_USE_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.2))


def using_cookie_relay(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🍪 Using Cookie Relay at {COOKIE_RELAY_USE_BUTTON} (jitter +-15) on {ip}:{port}...")
    safe_device_tap(ip, port, COOKIE_RELAY_USE_BUTTON[0], COOKIE_RELAY_USE_BUTTON[1])
    time.sleep(random.uniform(0.5, 0.8))
    safe_device_tap(ip, port, COOKIE_RELAY_USE_BUTTON[0], COOKIE_RELAY_USE_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.2))


def complete_finish(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🏆 Completing the game on {ip}:{port}...")
    safe_device_tap(ip, port, COMPLETE_FINISH_BUTTON[0], COMPLETE_FINISH_BUTTON[1])
    time.sleep(random.uniform(1.8, 2.4))


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
    time.sleep(random.uniform(0.8, 1.4))


def accept_level_up(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("⬆️ Accepting Level Up...")
    safe_device_tap(ip, port, ACCEPT_LEVEL_UP_BUTTON[0], ACCEPT_LEVEL_UP_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def accept_daily_checkin(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("📅 Accepting Daily Check-in...")
    safe_device_tap(ip, port, ACCEPT_DAILY_CHECKIN_BUTTON[0], ACCEPT_DAILY_CHECKIN_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def accept_daily_checkin_boost_set(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("📅 Accepting Daily Check-in Boost Set...")
    safe_device_tap(ip, port, ACCEPT_DAILY_CHECKIN_BOOST_SET_BUTTON[0], ACCEPT_DAILY_CHECKIN_BOOST_SET_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def accept_daily_treasure(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("💎 Accepting Daily Treasure...")
    safe_device_tap(ip, port, ACCEPT_DAILY_TREASURE_BUTTON[0], ACCEPT_DAILY_TREASURE_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def accept_daily_new(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("📰 Accepting Daily New...")
    safe_device_tap(ip, port, ACCEPT_DAILY_NEW_BUTTON[0], ACCEPT_DAILY_NEW_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def accept_enter_league(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🏆 Accepting Enter League...")
    safe_device_tap(ip, port, ACCEPT_ENTER_LEAGUE_BUTTON[0], ACCEPT_ENTER_LEAGUE_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def accept_league_results(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🏆 Accepting League Results...")
    safe_device_tap(ip, port, ACCEPT_LEAGUE_RESULTS_BUTTON[0], ACCEPT_LEAGUE_RESULTS_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def accept_previous_rank_results(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🏆 Accepting Previous Rank Results...")
    safe_device_tap(ip, port, ACCEPT_PREVIOUS_RANK_RESULTS_BUTTON[0], ACCEPT_PREVIOUS_RANK_RESULTS_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def accept_too_many_treasures(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("💎 Accepting Too Many Treasures...")
    safe_device_tap(ip, port, ACCEPT_TOO_MANY_TREASURES_BUTTON[0], ACCEPT_TOO_MANY_TREASURES_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def accept_overtake_break_score(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🏆 Accepting Overtake Break Score...")
    safe_device_tap(ip, port, ACCEPT_OVERTAKE_BREAK_SCORE_BUTTON[0], ACCEPT_OVERTAKE_BREAK_SCORE_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def open_relic_complete(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🏺 Opening Relic Complete...")
    safe_device_tap(ip, port, RELIC_COMPLETE_BUTTON[0], RELIC_COMPLETE_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def accept_relic_claim(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print("🏺 Accepting Relic Claim...")
    safe_device_tap(ip, port, RELIC_CLAIM_BUTTON[0], RELIC_CLAIM_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))
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
    time.sleep(random.uniform(0.8, 1.4))


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
                time.sleep(random.uniform(0.8, 1.4))
                print("💌 Confirming send life...")
                safe_device_tap(ip, port, CONFIRM_SEND_LIFE_BUTTON[0], CONFIRM_SEND_LIFE_BUTTON[1])
                time.sleep(random.uniform(0.8, 1.4))
                print("💌 Closing send life dialog...")
                safe_device_tap(ip, port, CLOSE_SEND_LIFE_DIALOG_BUTTON[0], CLOSE_SEND_LIFE_DIALOG_BUTTON[1])
                time.sleep(random.uniform(0.8, 1.4))
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
    time.sleep(random.uniform(0.8, 1.4))
    safe_device_tap(ip, port, MAIL_BOX_BUTTON[0], MAIL_BOX_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))
    safe_device_tap(ip, port, MAIL_BOX_LIVES_TAB_BUTTON[0], MAIL_BOX_LIVES_TAB_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))
    screen = device_capture_screen(ip, port)
    if detect_templates(screen, NO_LIVES_TO_RECEIVE_TEMPLATE, NO_LIVES_TO_RECEIVE_REGION):
        print("✉️ No lives to receive. Proceeding to send lives...")
        safe_device_tap(ip, port, MAIL_BOX_CLOSE_BUTTON[0], MAIL_BOX_CLOSE_BUTTON[1])
        return
    print("✉️ Receiving all lives...")
    safe_device_tap(ip, port, QUICK_RECEIVE_AND_SEND_LIVES_BUTTON[0], QUICK_RECEIVE_AND_SEND_LIVES_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))
    while True:
        screen = device_capture_screen(ip, port)
        all_lives_received_and_sent = detect_templates(screen, ALL_LIVES_RECEIVED_AND_SENT_TEMPLATE, ALL_LIVES_RECEIVED_AND_SENT_REGION)
        if all_lives_received_and_sent:
            print("✉️ All lives received and sent. Done!")
            safe_device_tap(ip, port, ACCEPT_ALL_LIVES_RECEIVED_AND_SENT_BUTTON[0], ACCEPT_ALL_LIVES_RECEIVED_AND_SENT_BUTTON[1])
            time.sleep(random.uniform(0.8, 1.4))
            safe_device_tap(ip, port, MAIL_BOX_CLOSE_BUTTON[0], MAIL_BOX_CLOSE_BUTTON[1])
            time.sleep(random.uniform(0.8, 1.4))
            break
        confirm_send_life_button_coords = detect_templates(screen, CONFIRM_SEND_LIFE_TEMPLATE, CONFIRM_SEND_LIFE_REGION)
        if confirm_send_life_button_coords:
            print("✉️ Sending lives to friends...")
            safe_device_tap(ip, port, CONFIRM_SEND_LIFE_BUTTON[0], CONFIRM_SEND_LIFE_BUTTON[1])
            time.sleep(random.uniform(0.8, 1.4))
    print("✉️ Quick Receive and Send Lives completed.")


def close_announcement_popup(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"❌ Closing generic announcement popup at (1126,57) on {ip}:{port}...")
    safe_device_tap(ip, port, ANNOUNCEMENT_CLOSE_BUTTON[0], ANNOUNCEMENT_CLOSE_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def close_announcement_dialog(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🖱️ Closing announcement dialog on {ip}:{port}...")
    count = random.randint(4, 6)
    for i in range(count):
        print(f"🖱️ Tapping close announcement dialog button {i+1}/{count}")
        safe_device_tap(ip, port, CLOSE_ANNOUNCEMENT_DIALOG_BUTTON[0], CLOSE_ANNOUNCEMENT_DIALOG_BUTTON[1])
        time.sleep(random.uniform(0.75, 1.45))
    safe_device_tap(ip, port, ANNOUNCEMENT_CLOSE_BUTTON[0], ANNOUNCEMENT_CLOSE_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))
    device_screen = device_capture_screen(ip, port)
    if detect_stage(device_screen, ["PARTY_RUN"]) == "PARTY_RUN":
        close_party_run_mode(ip, port)
    elif detect_stage(device_screen, ["GAME_SETTINGS"]) == "GAME_SETTINGS":
        close_game_settings(ip, port)
    elif detect_stage(device_screen, ["ANNOUNCEMENT_POPUP"]) == "ANNOUNCEMENT_POPUP":
        close_announcement_popup(ip, port)


def close_party_run_mode(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🖱️ Closing Party Run mode on {ip}:{port}...")
    safe_device_tap(ip, port, EXIT_PARTY_RUN_MODE_BUTTON[0], EXIT_PARTY_RUN_MODE_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def close_game_settings(device_ip=None, device_port=None):
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🖱️ Closing Game Settings on {ip}:{port}...")
    safe_device_tap(ip, port, EXIT_GAME_SETTINGS_BUTTON[0], EXIT_GAME_SETTINGS_BUTTON[1])
    time.sleep(random.uniform(0.8, 1.4))


def handle_emu_home(device_ip=None, device_port=None):
    """กดไอคอน CookieRun Classic ที่หน้า Emu Home (537,235) เมื่อหลุดมาหน้าหลัก"""
    ip, port = _resolve_device(device_ip, device_port)
    print(f"🏠 Detected EMU_HOME — tapping CookieRun Classic at (537,235) on {ip}:{port}...")
    from config import EMU_HOME_TAP
    safe_device_tap(ip, port, EMU_HOME_TAP[0], EMU_HOME_TAP[1])
    time.sleep(random.uniform(4, 6))
