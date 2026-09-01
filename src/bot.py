import random
import time

from adb import device_capture_screen, device_connect, device_is_app_running, device_reset_app, device_tap, safe_device_tap
from actions import (
    accept_congratulations,
    accept_daily_checkin,
    accept_daily_checkin_boost_set,
    accept_daily_new,
    accept_daily_treasure,
    accept_enter_league,
    accept_league_results,
    accept_level_up,
    accept_mystery_box,
    accept_overtake_break_score,
    accept_previous_rank_results,
    accept_relic_claim,
    accept_too_many_treasures,
    close_announcement_dialog,
    complete_finish,
    handle_anti_bot,
    handle_emu_home,
    tap_confirm_popup,
    handle_inactive,
    handle_quick_receive_and_send_lives,
    handle_send_friend_life,
    open_relic_complete,
    play_game,
    purchase_cookie_relay,
    purchase_desired_random_boost,
    purchase_fast_start,
    start_game,
    using_cookie_relay,
    using_fast_start,
)
from config import (
    BOOST_17P_BASE_SPEED_TEMPLATE,
    BOOST_15P_SCORE_BONUS_TEMPLATE,
    BOOST_20P_HP_FROM_POTIONS_TEMPLATE,
    BOOST_2PIT_LIFTS_TEMPLATE,
    BOOST_70P_CRUSH_CHANCE_TEMPLATE,
    BOOST_DOUBLE_COINS_TEMPLATE,
    BOOST_GOLD_COIN_MAGIC_TEMPLATE,
    BOOST_M15P_HP_DRAIN_TEMPLATE,
    BOOST_M30P_COLLISION_DAMAGE_TEMPLATE,
    BOOST_MAGNETIC_AURA_TEMPLATE,
    BOOST_REVIVE_ONCE_WITH_80HP_TEMPLATE,
    DETECTION_ALWAYS_STAGES,
    DETECTION_GROUPS,
    DETECTION_RECOVERY_SCAN_INTERVAL,
    DEVICE_IP,
    DEVICE_PORT,
    EMU_HOME_CHECK_INTERVAL,
    EMU_HOME_TAP,
    GAME_PACKAGE,
    SESSION_RESET_INTERVAL,
)
from detection import detect_stage, extract_result_coins, extract_result_xp, is_emu_home_visible, is_confirm_popup_visible, is_game_run_visible, load_templates
from debug import save_debug_screen

# -------------------
# BOT OPTIONS
# -------------------
BOOST_CHOICES = [
    ("Double Coins",            BOOST_DOUBLE_COINS_TEMPLATE),
    ("+15% Score Bonus",        BOOST_15P_SCORE_BONUS_TEMPLATE),
    ("-15% HP Drain",           BOOST_M15P_HP_DRAIN_TEMPLATE),
    ("Revive Once with 80 HP",  BOOST_REVIVE_ONCE_WITH_80HP_TEMPLATE),
    ("70% Crush Chance",        BOOST_70P_CRUSH_CHANCE_TEMPLATE),
    ("+17% Base Speed",         BOOST_17P_BASE_SPEED_TEMPLATE),
    ("Gold Coin Magic",         BOOST_GOLD_COIN_MAGIC_TEMPLATE),
    ("-30% Collision Damage",   BOOST_M30P_COLLISION_DAMAGE_TEMPLATE),
    ("+20% HP from Potions",    BOOST_20P_HP_FROM_POTIONS_TEMPLATE),
    ("Magnetic Aura",           BOOST_MAGNETIC_AURA_TEMPLATE),
    ("2 Pit Lifts",             BOOST_2PIT_LIFTS_TEMPLATE),
]


def get_detection_stage_names(group_name, exclude=None):
    stage_names = []
    # For non-in-game groups, always stages have higher priority
    if group_name != "IN_GAME":
        for stage_name in DETECTION_ALWAYS_STAGES:
            if stage_name not in stage_names:
                stage_names.append(stage_name)
    # Add stages from the specified detection group
    for stage_name in DETECTION_GROUPS[group_name]:
        if stage_name not in stage_names:
            stage_names.append(stage_name)
    # For in-game, always stages are appended last (original behavior)
    if group_name == "IN_GAME":
        for stage_name in DETECTION_ALWAYS_STAGES:
            if stage_name not in stage_names:
                stage_names.append(stage_name)
    if exclude:
        stage_names = [s for s in stage_names if s not in exclude]
    return stage_names


def prompt_user_options():
    desired_boost_template = None

    print("⚙️ --- Bot Options ---")
    use_fast_start = input("⚡ Use Fast Start (buy + use)? [y/n]: ").strip().lower() == "y"
    use_cookie_relay = input("🍪 Use Cookie Relay (buy + use)? [y/n]: ").strip().lower() == "y"
    use_desired_random_boost = input("🎲 Use Desired Random Boost (buy + use)? [y/n]: ").strip().lower() == "y"
    if use_desired_random_boost:
        print("  Select desired boost (must match the boost option configured in-game):")
        for i, (name, _) in enumerate(BOOST_CHOICES, 1):
            print(f"  {i:2}. {name}")
        while True:
            choice = input("  Enter number: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(BOOST_CHOICES):
                desired_boost_template = BOOST_CHOICES[int(choice) - 1][1]
                desired_boost_name = BOOST_CHOICES[int(choice) - 1][0]
                print(f"  ✅ Selected: {desired_boost_name}")
                break
            print(f"  ⚠️ Please enter a number between 1 and {len(BOOST_CHOICES)}.")
    detect_relic = input("🏺 Detect Relic (open + claim)? [y/n]: ").strip().lower() == "y"
    print("---------------------")

    return {
        "use_fast_start": use_fast_start,
        "use_cookie_relay": use_cookie_relay,
        "use_desired_random_boost": use_desired_random_boost,
        "desired_boost_template": desired_boost_template,
        "desired_boost_name": desired_boost_name if use_desired_random_boost else None,
        "detect_relic": detect_relic,
    }


# -------------------
# MAIN LOOP
# -------------------
def main():
    try:
        print("🚀 CookieRun Classic Bot Started")
        print("⚠️ Screen must be 1280x720 resolution for the bot to work properly.")
        print(f"📱 Connecting to device at {DEVICE_IP}:{DEVICE_PORT}...")

        device_connect(DEVICE_IP, DEVICE_PORT)
        load_templates()

        # * for debugging *
        # device_screen = device_capture_screen(DEVICE_IP, DEVICE_PORT)
        # save_debug_screen(device_screen)

        options = prompt_user_options()
        relic_exclude = None if options["detect_relic"] else {"RELIC_COMPLETE", "RELIC_CLAIM"}

        last_stage = None
        is_first_game = True
        detection_group = "PRE_GAME"
        last_detected_time = time.time()
        session_start_time = time.time()
        session_reset_interval = random.uniform(*SESSION_RESET_INTERVAL)
        last_lives_time = time.time()
        lives_interval = random.uniform(25 * 60, 35 * 60)
        pending_send_friend_life = False
        last_emu_check_time = time.time()
        emu_check_jitter = random.uniform(8, 12)

        while True:
            # Watchdog: หลุดมาหน้า Emu Home (แอปไม่รัน) -> กดเข้าเกมที่ (537,235) แบบ jitter
            if time.time() - last_emu_check_time >= emu_check_jitter:
                last_emu_check_time = time.time()
                emu_check_jitter = random.uniform(8, 12)
                try:
                    running = device_is_app_running(DEVICE_IP, DEVICE_PORT, GAME_PACKAGE)
                except Exception:
                    running = False
                if not running:
                    print("🏠 ตรวจพบหลุดมาหน้า Emu (แอปไม่รัน) — กำลังกดเข้าเกมใหม่ที่ (537,235)...")
                    handle_emu_home()
                    detection_group = "PRE_GAME"
                    last_stage = None
                    is_first_game = True
                    last_detected_time = time.time()
                    continue

            device_screen = device_capture_screen(DEVICE_IP, DEVICE_PORT)
            stage = detect_stage(device_screen, get_detection_stage_names(detection_group, exclude=relic_exclude))
            if stage is None and is_emu_home_visible(device_screen):
                stage = "EMU_HOME"
            if stage is None and is_confirm_popup_visible(device_screen):
                stage = "CONFIRM_POPUP"
            if stage is None:
                if time.time() - last_detected_time >= DETECTION_RECOVERY_SCAN_INTERVAL[detection_group]:
                    stage = detect_stage(device_screen, exclude=relic_exclude)
                    if stage is None and is_emu_home_visible(device_screen):
                        stage = "EMU_HOME"
                    if stage is None and is_confirm_popup_visible(device_screen):
                        stage = "CONFIRM_POPUP"
                    last_detected_time = time.time()
            else:
                last_detected_time = time.time()

            # อิงจากภาพหน้าจอจริง: ถ้าเห็นปุ่ม Jump/Slide = เกมวิ่งอยู่จริง → พลิกเป็น IN_GAME
            # (ไม่พึ่ง assumption หลังกด Play)
            if stage is None and is_game_run_visible(device_screen):
                detection_group = "IN_GAME"

            if stage == last_stage:
                time.sleep(random.uniform(0.09, 0.18) if detection_group == "IN_GAME" else random.uniform(0.11, 0.22))
                continue

            last_stage = stage

            if stage == "MAINMENU":
                print("🎮 Detected Stage: MAINMENU")
                wait_refresh = random.uniform(4.5, 5.5)
                print(f"⏳ Waiting {wait_refresh:.1f}s for screen refresh...")
                time.sleep(wait_refresh)
                if pending_send_friend_life:
                    print("💌 Sending friend lives after app reset...")
                    handle_send_friend_life()
                    pending_send_friend_life = False
                    last_lives_time = time.time()
                    last_stage = None
                    continue
                elapsed = time.time() - session_start_time
                if elapsed >= session_reset_interval:
                    print(f"🔄 Session reset triggered after {elapsed / 3600:.2f}h — restarting app...")
                    device_reset_app(DEVICE_IP, DEVICE_PORT)
                    time.sleep(random.uniform(4.5, 5.8))
                    close_announcement_dialog()
                    pending_send_friend_life = True
                    session_start_time = time.time()
                    session_reset_interval = random.uniform(*SESSION_RESET_INTERVAL)
                    last_lives_time = time.time()
                    lives_interval = random.uniform(25 * 60, 35 * 60)
                    detection_group = "PRE_GAME"
                    last_stage = None
                    is_first_game = True
                    continue
                lives_elapsed = time.time() - last_lives_time
                if lives_elapsed >= lives_interval:
                    print(f"💌 ~30 min passed ({lives_elapsed / 60:.1f} min) — receiving and sending lives...")
                    handle_quick_receive_and_send_lives()
                    last_lives_time = time.time()
                    lives_interval = random.uniform(25 * 60, 35 * 60)
                    last_stage = None
                    continue
                if detection_group == "POST_GAME":
                    detection_group = "PRE_GAME"
                    last_stage = None
                    continue
                if not is_first_game:
                    delay = random.uniform(5, 10)
                    print(f"⏳ Waiting for {delay:.2f} seconds before starting the next game...")
                    time.sleep(delay)
                is_first_game = False
                start_game()
                detection_group = "PRE_GAME"
            elif stage == "PURCHASE_ITEM":
                print("🛒 Detected Stage: PURCHASE_ITEM")
                if options["use_fast_start"]:
                    purchase_fast_start()
                if options["use_cookie_relay"]:
                    purchase_cookie_relay()
                if options["use_desired_random_boost"]:
                    purchase_desired_random_boost(options["desired_boost_template"], options["desired_boost_name"])
                play_game()
                # Root-cause fix: อย่าตั้ง IN_GAME ทันทีหลัง Play — ปล่อยให้ loop ถัดไป
                # ตรวจจากภาพจริง (is_game_run_visible / GAME_START) เป็นตัวตัดสิน ป้องกัน flicker
                # เมื่อมีหน้า PURCHASE_ITEM จริงคั่นก่อนเข้าเกม
                detection_group = "PRE_GAME"
                time.sleep(random.uniform(0.15, 0.30))
                last_stage = None
            elif stage == "GAME_START":
                print("🏁 Detected Stage: GAME_START")
                if options["use_fast_start"]:
                    using_fast_start()
                detection_group = "IN_GAME"
            elif stage == "GAME_RELAY":
                print("🔄 Detected Stage: GAME_RELAY")
                if options["use_cookie_relay"]:
                    using_cookie_relay()
                detection_group = "IN_GAME"
            elif stage == "GAME_COMPLETE":
                print("✅ Detected Stage: GAME_COMPLETE (adaptive polling...)")
                time.sleep(random.uniform(0.5, 0.8))
                safe_device_tap(DEVICE_IP, DEVICE_PORT, 640, 260)
                # Adaptive polling until coins/XP stable (สุ่มทุก poll)
                poll_deadline = time.time() + 8.0
                last_coins = -1
                last_xp = -1
                stable_count = 0
                second_tap_done = False
                while time.time() < poll_deadline:
                    time.sleep(random.uniform(0.32, 0.48))
                    try:
                        fresh = device_capture_screen(DEVICE_IP, DEVICE_PORT)
                        if fresh is not None:
                            device_screen = fresh
                    except Exception:
                        continue
                    c = extract_result_coins(device_screen) if device_screen is not None else 0
                    x = extract_result_xp(device_screen) if device_screen is not None else 0
                    if not second_tap_done and time.time() > poll_deadline - 6.5 and c == 0:
                        safe_device_tap(DEVICE_IP, DEVICE_PORT, 640, 260)
                        second_tap_done = True
                        continue
                    if c == last_coins and x == last_xp and c != 0:
                        stable_count += 1
                        if stable_count >= 2:
                            print(f"🔒 ตัวเลขนิ่งแล้ว: {c:,} 🪙 / {x:,} EXP — พร้อมกด OK")
                            break
                    else:
                        stable_count = 0
                    last_coins, last_xp = c, x
                jitter = random.uniform(0.5, 1.5)
                print(f"⏳ รอ {jitter:.1f}s ก่อนกด OK (jitter 0.5-1.5s)...")
                time.sleep(jitter)
                complete_finish()
                detection_group = "POST_GAME"
            elif stage == "MYSTERY_BOX":
                print("🎁 Detected Stage: MYSTERY_BOX")
                accept_mystery_box()
                time.sleep(random.uniform(2.7, 3.4))
                detection_group = "POST_GAME"
                last_stage = None
            elif stage == "CONGRATULATIONS":
                print("🎉 Detected Stage: CONGRATULATIONS")
                accept_congratulations()
                detection_group = "POST_GAME"
                last_stage = None
            elif stage == "LEVEL_UP":
                print("⬆️ Detected Stage: LEVEL_UP")
                accept_level_up()
                detection_group = "PRE_GAME"
            elif stage == "DAILY_CHECKIN":
                print("📅 Detected Stage: DAILY_CHECKIN")
                accept_daily_checkin()
                detection_group = "PRE_GAME"
            elif stage == "DAILY_CHECKIN_BOOST_SET":
                print("📅 Detected Stage: DAILY_CHECKIN_BOOST_SET")
                accept_daily_checkin_boost_set()
                detection_group = "PRE_GAME"
            elif stage == "DAILY_TREASURE":
                print("💎 Detected Stage: DAILY_TREASURE")
                accept_daily_treasure()
                detection_group = "PRE_GAME"
            elif stage == "DAILY_NEW":
                print("📰 Detected Stage: DAILY_NEW")
                accept_daily_new()
                detection_group = "PRE_GAME"
            elif stage == "ENTER_LEAGUE":
                print("🏆 Detected Stage: ENTER_LEAGUE")
                accept_enter_league()
                detection_group = "PRE_GAME"
            elif stage == "LEAGUE_RESULTS":
                print("🏆 Detected Stage: LEAGUE_RESULTS")
                accept_league_results()
                detection_group = "PRE_GAME"
            elif stage == "PREVIOUS_RANK_RESULTS":
                print("🏆 Detected Stage: PREVIOUS_RANK_RESULTS")
                accept_previous_rank_results()
                detection_group = "PRE_GAME"
            elif stage == "OVERTAKE_BREAK_SCORE":
                print("🏆 Detected Stage: OVERTAKE_BREAK_SCORE")
                accept_overtake_break_score()
                detection_group = "POST_GAME"
                last_stage = None
            elif stage == "TOO_MANY_TREASURES":
                print("💎 Detected Stage: TOO_MANY_TREASURES")
                accept_too_many_treasures()
                detection_group = "PRE_GAME"
            elif stage == "RELIC_COMPLETE":
                print("🏺 Detected Stage: RELIC_COMPLETE")
                open_relic_complete()
                detection_group = "PRE_GAME"
            elif stage == "RELIC_CLAIM":
                print("🏺 Detected Stage: RELIC_CLAIM")
                accept_relic_claim()
                detection_group = "PRE_GAME"
            elif stage == "ANTI_BOT":
                print("⚠️ Detected Stage: ANTI_BOT")
                handle_anti_bot(device_screen)
                last_stage = None
            elif stage == "EMU_HOME":
                print("🏠 Detected Stage: EMU_HOME — tapping CookieRun Classic...")
                handle_emu_home()
                detection_group = "PRE_GAME"
                last_stage = None
                is_first_game = True
            elif stage == "INACTIVE":
                print("💤 Detected Stage: INACTIVE")
                handle_inactive()
                last_stage = None
            elif stage == "ANNOUNCEMENT_POPUP":
                print("❌ Detected Stage: ANNOUNCEMENT_POPUP — closing popup...")
                close_announcement_dialog()
                last_stage = None
            elif stage == "CONFIRM_POPUP":
                print("✅ Detected Stage: CONFIRM_POPUP — tapping confirm...")
                tap_confirm_popup()
                last_stage = None
            time.sleep(random.uniform(0.10, 0.16) if detection_group == "IN_GAME" else random.uniform(0.20, 0.32))
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user.")
    except Exception as e:
        print(f"❌ An error occurred: {e}")
