import asyncio
from collections import deque
from datetime import datetime
import os
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np

import config
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
    close_friend_info_popup,
    complete_finish,
    handle_anr,
    handle_anti_bot,
    handle_emu_home,
    tap_confirm_popup,
    handle_inactive,
    handle_quick_receive_and_send_lives,
    handle_send_friend_life,
    humanlike_jump,
    humanlike_jump_double,
    humanlike_slide,
    open_relic_complete,
    play_game,
    purchase_cookie_relay,
    purchase_desired_random_boost,
    purchase_fast_start,
    start_game,
    sync_boost_selection,
    using_cookie_relay,
    using_fast_start,
)
from adb import (
    device_capture_screen,
    device_check_connection,
    device_connect,
    device_is_app_running,
    device_reset_app,
    device_tap,
    safe_device_tap,
    get_adb_path,
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
    EMU_HOME_CHECK_INTERVAL,
    GAME_PACKAGE,
    SESSION_RESET_INTERVAL,
    X_CLOSE_EXCLUDE_ZONES,
    X_CLOSE_FALLBACK_THRESHOLD,
    X_CLOSE_FALLBACK_THRESHOLD_IN_GAME,
)
from detection import (
    detect_result_screen_mystery_box,
    detect_mystery_box_grades,
    detect_stage,
    extract_item_stock,
    extract_result_coins,
    extract_result_xp,
    find_close_x_button_safe,
    is_emu_home_visible,
    is_confirm_popup_visible,
    is_game_run_visible,
    load_templates,
)
from discord_notifier import discord_notifier

# Persistent per-instance settings file (survives server restart)
_INSTANCE_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "instance_settings.json")
_INSTANCE_SETTINGS_LOCK = threading.Lock()

def _load_all_instance_settings() -> dict:
    if os.path.isfile(_INSTANCE_SETTINGS_FILE):
        try:
            import json
            with open(_INSTANCE_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}

def _save_all_instance_settings(all_data: dict):
    try:
        import json
        with _INSTANCE_SETTINGS_LOCK:
            with open(_INSTANCE_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Settings] Failed to save instance_settings.json: {e}")

def _load_instance_settings(instance_id: str) -> dict:
    return _load_all_instance_settings().get(instance_id, {})

def _save_instance_settings(instance_id: str, settings: dict):
    all_data = _load_all_instance_settings()
    all_data[instance_id] = settings
    _save_all_instance_settings(all_data)

BOOST_OPTIONS = [
    {"id": "double_coins", "name": "Double Coins (2x)", "template": BOOST_DOUBLE_COINS_TEMPLATE},
    {"id": "score_15", "name": "+15% Score Bonus", "template": BOOST_15P_SCORE_BONUS_TEMPLATE},
    {"id": "hp_drain_15", "name": "-15% HP Drain", "template": BOOST_M15P_HP_DRAIN_TEMPLATE},
    {"id": "revive_80", "name": "Revive Once with 80 HP", "template": BOOST_REVIVE_ONCE_WITH_80HP_TEMPLATE},
    {"id": "crush_70", "name": "70% Crush Chance", "template": BOOST_70P_CRUSH_CHANCE_TEMPLATE},
    {"id": "speed_17", "name": "+17% Base Speed", "template": BOOST_17P_BASE_SPEED_TEMPLATE},
    {"id": "coin_magic", "name": "Gold Coin Magic", "template": BOOST_GOLD_COIN_MAGIC_TEMPLATE},
    {"id": "damage_30", "name": "-30% Collision Damage", "template": BOOST_M30P_COLLISION_DAMAGE_TEMPLATE},
    {"id": "potions_20", "name": "+20% HP from Potions", "template": BOOST_20P_HP_FROM_POTIONS_TEMPLATE},
    {"id": "magnetic", "name": "Magnetic Aura", "template": BOOST_MAGNETIC_AURA_TEMPLATE},
    {"id": "pit_lifts_2", "name": "2 Pit Lifts", "template": BOOST_2PIT_LIFTS_TEMPLATE},
]


def get_detection_stage_names(group_name: str, exclude: Optional[set] = None) -> List[str]:
    stage_names = []
    if group_name != "IN_GAME":
        for stage_name in DETECTION_ALWAYS_STAGES:
            if stage_name not in stage_names:
                stage_names.append(stage_name)
    for stage_name in DETECTION_GROUPS[group_name]:
        if stage_name not in stage_names:
            stage_names.append(stage_name)
    if group_name == "IN_GAME":
        for stage_name in DETECTION_ALWAYS_STAGES:
            if stage_name not in stage_names:
                stage_names.append(stage_name)
    if exclude:
        stage_names = [s for s in stage_names if s not in exclude]
    return stage_names


class BotEngine:
    """
    Multi-instance capable BotEngine.
    Each instance controls ONE ADB device (host:port) independently.
    All state is per-instance (self.xxx) with its own thread + lock.
    """

    def __init__(self, instance_id: str = "device_1", device_ip: str = "127.0.0.1", device_port: int = 5595, device_name: str = "จอ 1"):
        self.instance_id: str = instance_id
        self.device_name: str = device_name
        self.is_running = False
        self.should_stop = False
        self.thread: Optional[threading.Thread] = None
        # Per-instance lock — never shared cross-instance
        self.lock = threading.Lock()

        # Config state — per-instance, never reads from config global directly during loop
        self.device_ip = device_ip
        self.device_port = int(device_port)
        self.use_fast_start = False
        self.fast_start_min_stock = 10
        self.use_cookie_relay = False
        self.cookie_relay_min_stock = 10
        self.hp_extension_enabled = False
        self.power_jelly_enabled = False
        self.double_xp_enabled = False
        self.use_desired_random_boost = False
        self.desired_boost_id = "double_coins"
        self.detect_relic = True
        self.send_friend_lives = True
        self.stop_goal_rounds_enabled: bool = False
        self.stop_goal_rounds_target: int = 50
        self.stop_goal_time_enabled: bool = False
        self.stop_goal_time_hours: float = 2.0
        # Human-like play (สุ่มกด Jump/Slide ขณะวิ่ง) — ค่า default จาก config
        _hl = config.HUMANLIKE_PLAY_DEFAULTS
        self.humanlike_play_enabled: bool = False
        self.humanlike_jump_enabled: bool = True
        self.humanlike_jump_interval: float = float(_hl["jump_single_interval"])
        self.humanlike_jump_double_enabled: bool = True
        self.humanlike_jump_double_interval: float = float(_hl["jump_double_interval"])
        self.humanlike_jump_double_gap: float = float(_hl["jump_double_gap"])
        self.humanlike_slide_enabled: bool = True
        self.humanlike_slide_interval: float = float(_hl["slide_interval"])
        self.humanlike_slide_hold_duration: float = float(_hl["slide_hold_duration"])
        # Human-like background thread — per instance, exclusive กับ IN_GAME
        self.humanlike_thread: Optional[threading.Thread] = None
        self.humanlike_stop_event = threading.Event()
        self._in_game_since: float = 0.0
        self._humanlike_grace: float = 4.0  # เริ่มกดหลังเข้า IN_GAME 4 วิ (ข้าม countdown Ready-GO)
        # Generic popup X-close fallback — state กันกดซ้ำ/สแปมแจ้งเตือน
        self._x_fallback_cd_until: float = 0.0
        self._x_fallback_last_tap: float = 0.0
        self._x_fallback_last_pos: Optional[tuple] = None
        self._x_fallback_notified_pos: Optional[tuple] = None
        # Manual heart sending flag — กัน main loop ปิด popup เมล์ระหว่างทำงาน (thread แยก)
        self._sending_hearts: bool = False
        # Load persisted per-instance settings if exists (survives restart)
        try:
            _saved = _load_instance_settings(instance_id)
            if _saved:
                self.use_fast_start = bool(_saved.get("use_fast_start", self.use_fast_start))
                self.fast_start_min_stock = int(_saved.get("fast_start_min_stock", self.fast_start_min_stock))
                self.use_cookie_relay = bool(_saved.get("use_cookie_relay", self.use_cookie_relay))
                self.cookie_relay_min_stock = int(_saved.get("cookie_relay_min_stock", self.cookie_relay_min_stock))
                self.hp_extension_enabled = bool(_saved.get("hp_extension_enabled", self.hp_extension_enabled))
                self.power_jelly_enabled = bool(_saved.get("power_jelly_enabled", self.power_jelly_enabled))
                self.double_xp_enabled = bool(_saved.get("double_xp_enabled", self.double_xp_enabled))
                self.use_desired_random_boost = bool(_saved.get("use_desired_random_boost", self.use_desired_random_boost))
                self.desired_boost_id = _saved.get("desired_boost_id", self.desired_boost_id)
                self.detect_relic = bool(_saved.get("detect_relic", self.detect_relic))
                self.send_friend_lives = bool(_saved.get("send_friend_lives", self.send_friend_lives))
                self.stop_goal_rounds_enabled = bool(_saved.get("stop_goal_rounds_enabled", self.stop_goal_rounds_enabled))
                self.stop_goal_rounds_target = int(_saved.get("stop_goal_rounds_target", self.stop_goal_rounds_target))
                self.stop_goal_time_enabled = bool(_saved.get("stop_goal_time_enabled", self.stop_goal_time_enabled))
                self.stop_goal_time_hours = float(_saved.get("stop_goal_time_hours", self.stop_goal_time_hours))
                self.humanlike_play_enabled = bool(_saved.get("humanlike_play_enabled", self.humanlike_play_enabled))
                self.humanlike_jump_enabled = bool(_saved.get("humanlike_jump_enabled", self.humanlike_jump_enabled))
                self.humanlike_jump_interval = float(_saved.get("humanlike_jump_interval", self.humanlike_jump_interval))
                self.humanlike_jump_double_enabled = bool(_saved.get("humanlike_jump_double_enabled", self.humanlike_jump_double_enabled))
                self.humanlike_jump_double_interval = float(_saved.get("humanlike_jump_double_interval", self.humanlike_jump_double_interval))
                self.humanlike_jump_double_gap = float(_saved.get("humanlike_jump_double_gap", self.humanlike_jump_double_gap))
                self.humanlike_slide_enabled = bool(_saved.get("humanlike_slide_enabled", self.humanlike_slide_enabled))
                self.humanlike_slide_interval = float(_saved.get("humanlike_slide_interval", self.humanlike_slide_interval))
                self.humanlike_slide_hold_duration = float(_saved.get("humanlike_slide_hold_duration", self.humanlike_slide_hold_duration))
        except Exception as e:
            print(f"[{instance_id}] Failed to load persisted settings: {e}")

        # Runtime Stats — all per-instance, no global shared state
        self.start_time: Optional[float] = None
        self.current_stage: str = "IDLE"
        self.rounds_played: int = 0
        self.mystery_boxes: int = 0

        # Detailed Box Grade Stats
        self.box_counts: Dict[str, int] = {
            "wood": 0,
            "silver": 0,
            "gold": 0,
            "rainbow": 0,
            "total": 0,
        }
        self.box_history: deque = deque(maxlen=100)

        # 50-Round Detailed History & Screenshots
        self.round_history: deque = deque(maxlen=50)
        self.round_screenshots: Dict[int, bytes] = {}
        self.current_round_start_time: float = 0
        self.current_round_recorded: bool = False
        self.current_round_screen: Optional[np.ndarray] = None

        # Accumulated Coins & EXP Tracking
        self.session_coins_earned: int = 0
        self.last_round_coins: int = 0
        self.session_xp_earned: int = 0
        self.last_round_xp: int = 0

        # Frame buffer for live stream — per instance
        self.latest_frame_jpeg: Optional[bytes] = None
        self.latest_currency_crop_jpeg: Optional[bytes] = None
        self.last_frame_time: float = 0

        # Logs buffer — per instance
        self.logs: deque = deque(maxlen=200)
        self.ws_subscribers: List[asyncio.Queue] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            "time": timestamp,
            "message": message,
            "level": level,
            "instance_id": self.instance_id,
            "device_name": self.device_name,
        }
        self.logs.append(log_entry)
        print(f"[{timestamp}] [{self.instance_id}] [{level.upper()}] {message}")

        if self.loop and self.ws_subscribers:
            for q in list(self.ws_subscribers):
                try:
                    self.loop.call_soon_threadsafe(q.put_nowait, log_entry)
                except Exception:
                    pass

    def interruptible_sleep(self, seconds: float) -> bool:
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self.should_stop:
                return True
            time.sleep(0.1)
        return False

    def update_frame(self, screen_bgr: np.ndarray):
        if screen_bgr is not None:
            try:
                target_w = 854
                target_h = 480
                resized = cv2.resize(screen_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)
                _, buffer = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 75])
                self.latest_frame_jpeg = buffer.tobytes()
                self.last_frame_time = time.time()

                h, w = screen_bgr.shape[:2]
                if h >= 100 and w >= 1200:
                    curr_crop = screen_bgr[10:72, 730:1220]
                    _, curr_buf = cv2.imencode(".jpg", curr_crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    self.latest_currency_crop_jpeg = curr_buf.tobytes()
            except Exception:
                pass

    def start(self, user_config: Dict[str, Any]):
        with self.lock:
            if self.is_running:
                # ถ้า thread ตายไปแล้วแต่ flag ค้าง ให้ reset แทนที่จะ error ค้าง
                if self.thread and self.thread.is_alive():
                    return {"success": False, "message": f"[{self.instance_id}] Bot is already running"}
                else:
                    self.is_running = False
                    self.should_stop = False
                    self.current_stage = "IDLE"
                    self.log("⚠️ is_running ค้างแต่ thread ตายแล้ว — reset แล้วเริ่มใหม่", "warning")

            # Device identity: defensive resolution — never allow None to overwrite
            # Priority: host > device_ip > existing; port > device_port > existing
            # Also handle case where frontend sends None/empty string
            def _resolve_host(cfg, fallback):
                for key in ("host", "device_ip"):
                    if key in cfg:
                        v = cfg.get(key)
                        if v is not None and str(v).strip() != "" and str(v).lower() != "none":
                            return str(v).strip()
                return fallback

            def _resolve_port(cfg, fallback):
                for key in ("port", "device_port"):
                    if key in cfg:
                        v = cfg.get(key)
                        # allow 0? but port 0 is invalid, treat as missing
                        if v is not None and str(v).strip() != "" and str(v).lower() != "none":
                            try:
                                return int(v)
                            except (ValueError, TypeError):
                                continue
                # fallback may be None -> raise
                if fallback is None or str(fallback).strip() == "" or str(fallback).lower() == "none":
                    raise ValueError(f"Instance {self.instance_id}: ไม่พบค่า port สำหรับเชื่อมต่อ ADB กรุณาตรวจสอบการตั้งค่า (host={self.device_ip}, port={fallback})")
                try:
                    return int(fallback)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Instance {self.instance_id}: ค่า port ไม่ถูกต้อง ({fallback}): {e}")

            host_value = _resolve_host(user_config, self.device_ip)
            if host_value is None or str(host_value).strip() == "" or str(host_value).lower() == "none":
                raise ValueError(f"Instance {self.instance_id}: ไม่พบค่า host สำหรับเชื่อมต่อ ADB กรุณาตรวจสอบการตั้งค่า")
            self.device_ip = str(host_value).strip()

            port_value = _resolve_port(user_config, self.device_port)
            self.device_port = int(port_value)
            if "name" in user_config and user_config["name"]:
                self.device_name = str(user_config["name"])

            # Only update settings that are explicitly provided — keep persisted values otherwise (fixes revert bug d)
            self._apply_settings(user_config)
            # Persist the (possibly updated) settings so they survive restart and next start call
            try:
                _save_instance_settings(self.instance_id, self._settings_snapshot())
            except Exception as e:
                print(f"[{self.instance_id}] Persist on start failed: {e}")

            self.is_running = True
            self.should_stop = False
            self.start_time = time.time()
            self.current_round_start_time = time.time()
            self.current_round_recorded = False
            self.current_stage = "INITIALIZING"
            self.thread = threading.Thread(target=self._run_loop, daemon=True, name=f"BotThread-{self.instance_id}")
            self.thread.start()
            self.log(f"▶️ Bot started (Device: {self.device_ip}:{self.device_port})", "success")
            discord_notifier.send_bot_start(self.device_ip, self.device_port)

        return {"success": True, "message": f"[{self.instance_id}] Bot started successfully"}

    def _apply_settings(self, cfg: Dict[str, Any]):
        """Apply เฉพาะ keys ที่ส่งมา (ไม่ reset ค่าอื่น) — ใช้ร่วมกับ start/update/live"""
        if "use_fast_start" in cfg:
            self.use_fast_start = bool(cfg["use_fast_start"])
        if "fast_start_min_stock" in cfg:
            try: self.fast_start_min_stock = int(cfg["fast_start_min_stock"])
            except: pass
        if "use_cookie_relay" in cfg:
            self.use_cookie_relay = bool(cfg["use_cookie_relay"])
        if "cookie_relay_min_stock" in cfg:
            try: self.cookie_relay_min_stock = int(cfg["cookie_relay_min_stock"])
            except: pass
        if "hp_extension_enabled" in cfg:
            self.hp_extension_enabled = bool(cfg["hp_extension_enabled"])
        if "power_jelly_enabled" in cfg:
            self.power_jelly_enabled = bool(cfg["power_jelly_enabled"])
        if "double_xp_enabled" in cfg:
            self.double_xp_enabled = bool(cfg["double_xp_enabled"])
        if "use_desired_random_boost" in cfg:
            self.use_desired_random_boost = bool(cfg["use_desired_random_boost"])
        if "desired_boost_id" in cfg:
            self.desired_boost_id = str(cfg["desired_boost_id"])
        if "detect_relic" in cfg:
            self.detect_relic = bool(cfg["detect_relic"])
        if "send_friend_lives" in cfg:
            self.send_friend_lives = bool(cfg["send_friend_lives"])
        if "stop_goal_rounds_enabled" in cfg:
            self.stop_goal_rounds_enabled = bool(cfg["stop_goal_rounds_enabled"])
        if "stop_goal_rounds_target" in cfg:
            try: self.stop_goal_rounds_target = int(cfg["stop_goal_rounds_target"])
            except: pass
        if "stop_goal_time_enabled" in cfg:
            self.stop_goal_time_enabled = bool(cfg["stop_goal_time_enabled"])
        if "stop_goal_time_hours" in cfg:
            try: self.stop_goal_time_hours = float(cfg["stop_goal_time_hours"])
            except: pass
        if "humanlike_play_enabled" in cfg:
            self.humanlike_play_enabled = bool(cfg["humanlike_play_enabled"])
        if "humanlike_jump_enabled" in cfg:
            self.humanlike_jump_enabled = bool(cfg["humanlike_jump_enabled"])
        if "humanlike_jump_interval" in cfg:
            try: self.humanlike_jump_interval = float(cfg["humanlike_jump_interval"])
            except: pass
        if "humanlike_jump_double_enabled" in cfg:
            self.humanlike_jump_double_enabled = bool(cfg["humanlike_jump_double_enabled"])
        if "humanlike_jump_double_interval" in cfg:
            try: self.humanlike_jump_double_interval = float(cfg["humanlike_jump_double_interval"])
            except: pass
        if "humanlike_jump_double_gap" in cfg:
            try: self.humanlike_jump_double_gap = float(cfg["humanlike_jump_double_gap"])
            except: pass
        if "humanlike_slide_enabled" in cfg:
            self.humanlike_slide_enabled = bool(cfg["humanlike_slide_enabled"])
        if "humanlike_slide_interval" in cfg:
            try: self.humanlike_slide_interval = float(cfg["humanlike_slide_interval"])
            except: pass
        if "humanlike_slide_hold_duration" in cfg:
            try: self.humanlike_slide_hold_duration = float(cfg["humanlike_slide_hold_duration"])
            except: pass

    def _settings_snapshot(self) -> Dict[str, Any]:
        """คืน dict settings ปัจจุบันทั้งหมด (ใช้ persist + API)"""
        return {
            "use_fast_start": self.use_fast_start,
            "fast_start_min_stock": self.fast_start_min_stock,
            "use_cookie_relay": self.use_cookie_relay,
            "cookie_relay_min_stock": self.cookie_relay_min_stock,
            "hp_extension_enabled": self.hp_extension_enabled,
            "power_jelly_enabled": self.power_jelly_enabled,
            "double_xp_enabled": self.double_xp_enabled,
            "use_desired_random_boost": self.use_desired_random_boost,
            "desired_boost_id": self.desired_boost_id,
            "detect_relic": self.detect_relic,
            "send_friend_lives": self.send_friend_lives,
            "stop_goal_rounds_enabled": self.stop_goal_rounds_enabled,
            "stop_goal_rounds_target": self.stop_goal_rounds_target,
            "stop_goal_time_enabled": self.stop_goal_time_enabled,
            "stop_goal_time_hours": self.stop_goal_time_hours,
            "humanlike_play_enabled": self.humanlike_play_enabled,
            "humanlike_jump_enabled": self.humanlike_jump_enabled,
            "humanlike_jump_interval": self.humanlike_jump_interval,
            "humanlike_jump_double_enabled": self.humanlike_jump_double_enabled,
            "humanlike_jump_double_interval": self.humanlike_jump_double_interval,
            "humanlike_jump_double_gap": self.humanlike_jump_double_gap,
            "humanlike_slide_enabled": self.humanlike_slide_enabled,
            "humanlike_slide_interval": self.humanlike_slide_interval,
            "humanlike_slide_hold_duration": self.humanlike_slide_hold_duration,
        }

    def get_settings(self) -> Dict[str, Any]:
        """คืนค่า settings ปัจจุบันของ instance นี้ (สำหรับ API)"""
        with self.lock:
            return self._settings_snapshot()

    def update_settings(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """อัปเดต settings ของ instance นี้แบบ persistent (ใช้ได้ทั้งตอนรันและหยุด)"""
        with self.lock:
            # Update only keys present in payload — don't reset others to default
            self._apply_settings(user_config)
            # Persist to file (per-instance)
            settings_snapshot = self._settings_snapshot()
            try:
                _save_instance_settings(self.instance_id, settings_snapshot)
            except Exception as e:
                print(f"[{self.instance_id}] Persist failed: {e}")
            self.log(
                f"⚙️ บันทึกตั้งค่า [{self.instance_id}]: FastStart={'ON' if self.use_fast_start else 'OFF'}({self.fast_start_min_stock}) "
                f"| Relay={'ON' if self.use_cookie_relay else 'OFF'}({self.cookie_relay_min_stock}) "
                f"| HP={'ON' if self.hp_extension_enabled else 'OFF'} "
                f"| Jelly={'ON' if self.power_jelly_enabled else 'OFF'} "
                f"| DXP={'ON' if self.double_xp_enabled else 'OFF'} "
                f"| Boost={'ON' if self.use_desired_random_boost else 'OFF'}({self.desired_boost_id}) "
                f"| Humanlike={'ON' if self.humanlike_play_enabled else 'OFF'}",
                "info",
            )
            # return copy
            return {"success": True, "message": f"[{self.instance_id}] Settings saved", "settings": dict(settings_snapshot)}
        # outside lock for return — but we already returned inside, keep for safety
        return {"success": True, "message": f"[{self.instance_id}] Settings saved", "settings": self.get_settings()}

    def update_live_config(self, user_config: Dict[str, Any]):
        """อัปเดต config แบบ hot-reload ขณะบอทกำลังรัน (legacy) — ตอนนี้เรียก update_settings ด้วยเพื่อ persist"""
        # Reuse update_settings but keep running check for backward compat
        with self.lock:
            if not self.is_running:
                return {"success": False, "message": f"[{self.instance_id}] Bot is not running"}
            self._apply_settings(user_config)
            # Persist live changes as well
            try:
                _save_instance_settings(self.instance_id, self._settings_snapshot())
            except Exception as e:
                print(f"[{self.instance_id}] Persist live failed: {e}")
            self.log(
                f"⚙️ อัปเดตตั้งค่าแบบ Live: FastStart={'ON' if self.use_fast_start else 'OFF'}({self.fast_start_min_stock}) "
                f"| CookieRelay={'ON' if self.use_cookie_relay else 'OFF'}({self.cookie_relay_min_stock}) "
                f"| Humanlike={'ON' if self.humanlike_play_enabled else 'OFF'}",
                "info",
            )
        return {"success": True, "message": "Live config updated"}

    def stop(self):
        with self.lock:
            if not self.is_running:
                return {"success": False, "message": f"[{self.instance_id}] Bot is not running"}

            self.should_stop = True
            self.current_stage = "STOPPING"
            self.log("🛑 Stopping bot...", "warning")

        self._stop_humanlike_thread()
        # ไม่ block API นาน — ให้ thread หยุดเองใน background (เช็ค should_stop ทุก 0.1วิ)
        # UI จะเห็น STOPPING แล้วค่อย IDLE เมื่อ thread จบจริงใน _run_loop finally
        def _wait_stop():
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=15.0)
                if self.thread.is_alive():
                    self.log("⚠️ Thread ยังไม่หยุดหลัง 15วิ — จะหยุดเมื่อจบ action ปัจจุบัน", "warning")
            with self.lock:
                if self.is_running: # ยังไม่ถูก _run_loop ปิดให้
                    self.is_running = False
                    self.current_stage = "IDLE"
                    self.log("⏹️ Bot stopped (forced)", "info")
                    uptime_sec = int(time.time() - self.start_time) if self.start_time else 0
                    hours, remainder = divmod(uptime_sec, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    try:
                        discord_notifier.send_bot_stop(
                            uptime=uptime_str,
                            rounds_played=self.rounds_played,
                            total_boxes=self.mystery_boxes,
                            coins_earned=self.session_coins_earned,
                            session_xp=self.session_xp_earned,
                        )
                    except Exception:
                        pass
        import threading
        threading.Thread(target=_wait_stop, daemon=True).start()
        return {"success": True, "message": f"[{self.instance_id}] Stopping... (จะหยุดเมื่อจบ action ปัจจุบัน ไม่เกิน 15วิ)"}

    def reset_stats(self):
        self.rounds_played = 0
        self.mystery_boxes = 0
        self.box_counts = {
            "wood": 0,
            "silver": 0,
            "gold": 0,
            "rainbow": 0,
            "total": 0,
        }
        self.session_coins_earned = 0
        self.last_round_coins = 0
        self.session_xp_earned = 0
        self.last_round_xp = 0
        self.round_history.clear()
        self.round_screenshots.clear()
        self.box_history.clear()
        self.log("📊 Stats, Mystery Box counts, Coins, and EXP reset to zero", "info")

    # ----------------------------------------------------------------
    # Human-like play (สุ่มกด Jump/Slide ขณะ IN_GAME) — per instance
    # ----------------------------------------------------------------
    def _stop_humanlike_thread(self):
        """หยุด thread เล่นเสมือนมนุษย์ทันที (ไม่ join — daemon, เช็ค event เอง)"""
        self.humanlike_stop_event.set()

    def _sync_humanlike_thread(self, in_game: bool):
        """
        เรียกทุก loop iteration — เริ่ม thread เมื่อเข้า IN_GAME (และตั้งค่าเปิดอยู่),
        หยุดทันทีเมื่อออกจาก IN_GAME / ปิด toggle / บอทหยุด (กันกดมั่วตอน popup ขึ้น)
        มี grace period หลังเข้า IN_GAME (ข้าม countdown Ready-GO ช่วงแรกของรอบ)
        """
        if in_game:
            if self._in_game_since <= 0:
                self._in_game_since = time.time()
            in_game_ready = (time.time() - self._in_game_since) >= self._humanlike_grace
        else:
            self._in_game_since = 0.0
            in_game_ready = False
        if not in_game_ready or not self.humanlike_play_enabled or self.should_stop:
            if self.humanlike_thread and self.humanlike_thread.is_alive():
                self._stop_humanlike_thread()
            return
        if self.humanlike_thread is None or not self.humanlike_thread.is_alive():
            self.humanlike_stop_event.clear()
            self.humanlike_thread = threading.Thread(
                target=self._humanlike_play_loop,
                daemon=True,
                name=f"Humanlike-{self.instance_id}",
            )
            self.humanlike_thread.start()

    def _humanlike_play_loop(self):
        """วนลูปสุ่มกด Jump/Slide แบบมนุษย์ — หยุดเมื่อ stop_event / should_stop"""
        def _jit(v: float) -> float:
            # jitter ±35-40% ของ interval — กว้างพอให้ไม่เกิดแพทเทิร์นซ้ำ (เดิม ±20% แคบไป)
            j = v * random.uniform(0.35, 0.40)
            return max(0.15, v + random.uniform(-j, j))

        def _roll_weights() -> Dict[str, float]:
            # สุ่มน้ำหนักการกระทำใหม่ — กระโดดเดี่ยว/เบิ้ล/สไลด์ ไม่ได้สัดส่วนคงที่ตลอด
            w_double = random.uniform(0.15, 0.45) if self.humanlike_jump_double_enabled else 0.0
            w_single = random.uniform(0.35, 0.65) if self.humanlike_jump_enabled else 0.0
            w_slide = random.uniform(0.6, 0.95) if self.humanlike_slide_enabled else 0.0
            return {"double": w_double, "single": w_single, "slide": w_slide}

        self.log("🤖 เล่นเสมือนมนุษย์ ON — สุ่มกด Jump/Slide ขณะวิ่ง", "info")
        last_double_jump = 0.0
        next_jump = time.time() + _jit(self.humanlike_jump_interval)
        next_slide = time.time() + _jit(self.humanlike_slide_interval)
        weights = _roll_weights()
        next_reroll = time.time() + random.uniform(30, 60)
        try:
            while not self.humanlike_stop_event.is_set() and not self.should_stop:
                st = self.current_stage
                if st != "IN_GAME (Searching...)":
                    # สเตจที่แปลว่า "จบรอบ/ออกจากเกมแล้ว" → หยุด thread จริง
                    if st in (
                        "GAME_COMPLETE", "MAINMENU", "PURCHASE_ITEM",
                        "PRE_GAME (Searching...)", "POST_GAME (Searching...)",
                        "EMU_HOME", "CONNECTION_LOST", "INACTIVE", "ANTI_BOT",
                        "MYSTERY_BOX", "CONGRATULATIONS", "OVERTAKE_BREAK_SCORE",
                        "STOPPING", "IDLE", "INITIALIZING", "STARTING",
                    ):
                        # ยืนยันจากหน้าจอจริง: ถ้ายังเห็นปุ่ม Jump/Slide = เกมยังวิ่งอยู่
                        # (เช่น PURCHASE_ITEM โดน detect หลอกตอน countdown) → พัก ไม่แตก
                        try:
                            frame = device_capture_screen(self.device_ip, self.device_port)
                            if frame is not None and is_game_run_visible(frame):
                                self.humanlike_stop_event.wait(0.4)
                                continue
                        except Exception:
                            pass
                        break
                    # สเตจชั่วคราว (GAME_RELAY/CONFIRM/ANNOUNCEMENT ฯลฯ) — พักรอ
                    # ไม่กด กันชนกับ handler หลัก แล้วกลับมาเล่นต่อเองเมื่อวิ่งต่อ
                    self.humanlike_stop_event.wait(0.5)
                    continue
                now = time.time()
                # โอกาส "หยุดพัก" 5-8% ต่อรอบ — ข้ามการกระโดด/สไลด์ในรอบนี้ (เหมือนคนเผลอไม่ทัน)
                pause = random.random() < random.uniform(0.05, 0.08)
                if not pause and self.humanlike_jump_enabled and now >= next_jump:
                    try:
                        roll = random.random()
                        if (
                            weights["double"] > 0
                            and roll < weights["double"]
                            and (now - last_double_jump) >= self.humanlike_jump_double_interval
                        ):
                            humanlike_jump_double(self.device_ip, self.device_port, gap=self.humanlike_jump_double_gap)
                            last_double_jump = now
                        elif roll < weights["double"] + weights["single"]:
                            humanlike_jump(self.device_ip, self.device_port)
                        # นอกนั้น = ข้ามรอบ (เหมือนลังเล) ไม่กด
                        next_jump = now + _jit(self.humanlike_jump_interval)
                    except Exception as e:
                        self.log(f"⚠️ humanlike jump error: {e}", "error")
                if not pause and self.humanlike_slide_enabled and now >= next_slide:
                    try:
                        if random.random() < weights["slide"]:
                            # hold สุ่มกว้าง 300-1500ms แบบคน CookieRun Flat-press ขวาล่าง — สั้น 300ms อุโมงค์สั้น / ยาว 1500ms+ อุโมงค์ยาว
                            _hold = random.uniform(0.30, 1.50)
                            humanlike_slide(self.device_ip, self.device_port, hold_duration=_hold)
                        next_slide = now + _jit(self.humanlike_slide_interval)
                    except Exception as e:
                        self.log(f"⚠️ humanlike slide error: {e}", "error")
                if now >= next_reroll:
                    weights = _roll_weights()
                    next_reroll = now + random.uniform(30, 60)
                self.humanlike_stop_event.wait(0.15)
        finally:
            self.log("🤖 เล่นเสมือนมนุษย์ OFF — หยุดกด Jump/Slide แล้ว", "info")

    def get_status(self) -> Dict[str, Any]:
        uptime_sec = int(time.time() - self.start_time) if self.is_running and self.start_time else 0
        hours, remainder = divmod(uptime_sec, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        coins_per_hour = int(self.session_coins_earned / max(0.001, uptime_sec / 3600)) if (self.is_running and uptime_sec > 5) else 0

        return {
            "instance_id": self.instance_id,
            "device_name": self.device_name,
            "is_running": self.is_running,
            "current_stage": self.current_stage,
            "uptime": uptime_str,
            "uptime_seconds": uptime_sec,
            "rounds_played": self.rounds_played,
            "mystery_boxes": self.mystery_boxes,
            "box_counts": self.box_counts,
            "coin_stats": {
                "session_earned": self.session_coins_earned,
                "session_xp_earned": self.session_xp_earned,
                "coins_per_hour": coins_per_hour,
                "last_round": self.last_round_coins,
                "last_round_xp": self.last_round_xp,
            },
            "round_history": list(self.round_history),
            "device_ip": self.device_ip,
            "device_port": self.device_port,
            "host": self.device_ip,
            "port": self.device_port,
            "use_fast_start": self.use_fast_start,
            "fast_start_min_stock": self.fast_start_min_stock,
            "use_cookie_relay": self.use_cookie_relay,
            "cookie_relay_min_stock": self.cookie_relay_min_stock,
            "hp_extension_enabled": self.hp_extension_enabled,
            "power_jelly_enabled": self.power_jelly_enabled,
            "double_xp_enabled": self.double_xp_enabled,
            "use_desired_random_boost": self.use_desired_random_boost,
            "desired_boost_id": self.desired_boost_id,
            "detect_relic": self.detect_relic,
            "send_friend_lives": self.send_friend_lives,
            "stop_goal_rounds_enabled": self.stop_goal_rounds_enabled,
            "stop_goal_rounds_target": self.stop_goal_rounds_target,
            "stop_goal_time_enabled": self.stop_goal_time_enabled,
            "stop_goal_time_hours": self.stop_goal_time_hours,
            "humanlike_play_enabled": self.humanlike_play_enabled,
            "humanlike_jump_enabled": self.humanlike_jump_enabled,
            "humanlike_jump_interval": self.humanlike_jump_interval,
            "humanlike_jump_double_enabled": self.humanlike_jump_double_enabled,
            "humanlike_jump_double_interval": self.humanlike_jump_double_interval,
            "humanlike_jump_double_gap": self.humanlike_jump_double_gap,
            "humanlike_slide_enabled": self.humanlike_slide_enabled,
            "humanlike_slide_interval": self.humanlike_slide_interval,
            "humanlike_slide_hold_duration": self.humanlike_slide_hold_duration,
            "adb_path": get_adb_path(),
            "discord_settings": {
                "webhook_url": discord_notifier.webhook_url,
                "enabled": discord_notifier.enabled,
                "notify_boxes": discord_notifier.notify_boxes,
                "notify_antibot": discord_notifier.notify_antibot,
                "notify_status": discord_notifier.notify_status,
                "attach_screenshot": discord_notifier.attach_screenshot,
            }
        }

    def _run_loop(self):
        try:
            self.log(f"🔌 Connecting to device at {self.device_ip}:{self.device_port}...")
            device_connect(self.device_ip, self.device_port)
            self.log("✅ ADB Connection established", "success")

            self.log("🖼️ Pre-warming OpenCV templates...")
            load_templates()
            self.log("✅ Templates loaded", "success")

            # Desired boost จะ lookup แบบ live ทุกรอบใน PURCHASE_ITEM handler
            # (ไม่ cache ไว้ตอน start) เพื่อให้เปลี่ยนในเว็บระหว่างบอทวิ่งแล้วมีผลทันทีรอบถัดไป
            relic_exclude = None if self.detect_relic else {"RELIC_COMPLETE", "RELIC_CLAIM"}

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

            self.log("🏁 Main loop started. Waiting for game screen...")

            emu_check_jitter = random.uniform(8, 12)
            while not self.should_stop:
                # สุ่มกด Jump/Slide เฉพาะตอน IN_GAME — thread มี self-check ภายใน
                # (พักเมื่อ stage ชั่วคราว / หยุดเมื่อ GAME_COMPLETE/ออกจากเกม) อยู่แล้ว
                self._sync_humanlike_thread(detection_group == "IN_GAME")
                if time.time() - last_emu_check_time >= emu_check_jitter:
                    last_emu_check_time = time.time()
                    emu_check_jitter = random.uniform(8, 12)
                    try:
                        running = device_is_app_running(self.device_ip, self.device_port, GAME_PACKAGE)
                    except Exception:
                        running = False
                    if not running:
                        self.log("🏠 ตรวจพบหลุดมาหน้า Emu (แอปไม่รัน) — กดเข้าเกมที่ (537,235)...", "warning")
                        handle_emu_home(self.device_ip, self.device_port)
                        detection_group = "PRE_GAME"
                        last_stage = None
                        is_first_game = True
                        last_detected_time = time.time()
                        continue

                # กัน popup เมล์ถูกปิดจากภายนอกระหว่างส่งหัวใจ (manual thread แยก)
                # ถ้ากำลังส่งหัวใจ → หยุด loop ชั่วคราว ไม่ตรวจ stage/ไม่กด X fallback จนกว่า send_hearts() จะ return
                if getattr(self, "_sending_hearts", False):
                    if self.interruptible_sleep(0.5):
                        break
                    continue

                try:
                    device_screen = device_capture_screen(self.device_ip, self.device_port)
                    self.update_frame(device_screen)
                except Exception as e:
                    self.log(f"⚠️ Screen capture error: {e}", "error")
                    if self.interruptible_sleep(random.uniform(0.8, 1.2)):
                        break
                    continue

                stage = detect_stage(device_screen, get_detection_stage_names(detection_group, exclude=relic_exclude))
                if stage is None and is_emu_home_visible(device_screen):
                    stage = "EMU_HOME"
                if stage is None and is_confirm_popup_visible(device_screen):
                    stage = "CONFIRM_POPUP"
                if stage is None:
                    if time.time() - last_detected_time >= DETECTION_RECOVERY_SCAN_INTERVAL[detection_group]:
                        recovered = detect_stage(device_screen, exclude=relic_exclude)
                        if recovered and detection_group == "IN_GAME":
                            # กัน false positive: stage นอกกลุ่ม (เช่น PURCHASE_ITEM) ขึ้นขณะ
                            # เกมวิ่ง (countdown/HUD) — เช็คหน้าจอจริง: ถ้ายังเห็นปุ่ม Jump/Slide
                            # อยู่ = เกมยังวิ่ง → stage นั้นไม่จริง ทิ้งผล (จับเฉพาะ stage ในกลุ่ม
                            # IN_GAME + ALWAYS ซึ่ง legit ตอนวิ่ง)
                            in_game_names = get_detection_stage_names("IN_GAME", exclude=relic_exclude)
                            if recovered not in in_game_names and is_game_run_visible(device_screen):
                                recovered = None
                        stage = recovered
                        if stage is None and is_emu_home_visible(device_screen):
                            stage = "EMU_HOME"
                        if stage is None and is_confirm_popup_visible(device_screen):
                            stage = "CONFIRM_POPUP"
                        last_detected_time = time.time()
                else:
                    last_detected_time = time.time()

                # ── อิงจากภาพหน้าจอจริง: ถ้าเห็นปุ่ม Jump/Slide = เกมวิ่งอยู่จริง ──
                # (ไม่สนว่าใครกดเริ่มเกม — ครอบคลุมกรณี user กดเองใน emulator / state หลุด sync)
                if stage is None and is_game_run_visible(device_screen):
                    detection_group = "IN_GAME"

                # ── Generic popup X-close fallback ──
                # popup ที่ไม่รู้จัก (stage ยังเป็น None) แต่มีปุ่ม X → ปิดให้อัตโนมัติ
                # ระหว่าง IN_GAME: threshold สูง (0.90) + ข้าม exclude zones (Pause/Jump/Slide)
                # กันไม่ให้ปิด popup เมล์ระหว่างส่งหัวใจ (manual thread)
                if stage is None and not getattr(self, "_sending_hearts", False):
                    now = time.time()
                    if now >= self._x_fallback_cd_until:
                        in_game = detection_group == "IN_GAME"
                        x_find = find_close_x_button_safe(
                            device_screen,
                            threshold=(X_CLOSE_FALLBACK_THRESHOLD_IN_GAME if in_game else X_CLOSE_FALLBACK_THRESHOLD),
                            exclude_zones=(X_CLOSE_EXCLUDE_ZONES if in_game else None),
                        )
                        if x_find is not None:
                            x_pos, x_score = x_find
                            if x_pos != self._x_fallback_last_pos or now >= self._x_fallback_last_tap + 6.0:
                                safe_device_tap(self.device_ip, self.device_port, x_pos[0], x_pos[1])
                                self._x_fallback_last_pos = x_pos
                                self._x_fallback_last_tap = now
                                self._x_fallback_cd_until = now + 3.5
                                if x_pos != self._x_fallback_notified_pos:
                                    self._x_fallback_notified_pos = x_pos
                                    self.log(
                                        f"🛑 พบ popup ที่ไม่รู้จัก (stage=None, group={detection_group}) — "
                                        f"เจอ X@{x_pos} score={x_score:.3f} — กดปิดให้แล้ว "
                                        f"ถ้ายังติดซ้ำ: รัน debug_tool.py capture แล้วใช้ new-stage เพื่อเพิ่ม template",
                                        "warning",
                                    )
                                last_stage = None
                                continue

                if stage:
                    self.current_stage = stage
                elif self.current_stage not in ("STARTING", "STOPPING"):
                    self.current_stage = f"{detection_group} (Searching...)"

                if stage == last_stage:
                    # throttle polling 100ms+ กันโดนจับ adb ถี่ — ขยายให้กว้าง humanlike ไม่สม่ำเสมอ
                    fast_sleep = random.uniform(0.05, 0.30) if detection_group == "IN_GAME" else random.uniform(0.08, 0.35)
                    if self.interruptible_sleep(fast_sleep):
                        break
                    continue

                last_stage = stage

                if stage == "MAINMENU":
                    self.log("🎮 Detected Stage: MAINMENU", "stage")
                    wait_refresh = random.uniform(4.5, 5.5)
                    self.log(f"⏳ Waiting {wait_refresh:.1f}s for screen refresh...")
                    if self.interruptible_sleep(wait_refresh):
                        break

                    if pending_send_friend_life and self.send_friend_lives:
                        self.log("💌 Sending friend lives after app reset...")
                        handle_send_friend_life(self.device_ip, self.device_port)
                        pending_send_friend_life = False
                        last_lives_time = time.time()
                        last_stage = None
                        continue

                    elapsed = time.time() - session_start_time
                    if elapsed >= session_reset_interval:
                        self.log(f"🔄 Session reset triggered after {elapsed / 3600:.2f}h — restarting app...")
                        device_reset_app(self.device_ip, self.device_port)
                        if self.interruptible_sleep(random.uniform(4.5, 5.8)):
                            break
                        close_announcement_dialog(self.device_ip, self.device_port)
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
                    if self.send_friend_lives and lives_elapsed >= lives_interval:
                        self.log(f"💌 ~30 min passed ({lives_elapsed / 60:.1f} min) — receiving and sending lives...")
                        handle_quick_receive_and_send_lives(self.device_ip, self.device_port)
                        last_lives_time = time.time()
                        lives_interval = random.uniform(25 * 60, 35 * 60)
                        last_stage = None
                        continue

                    if detection_group == "POST_GAME":
                        detection_group = "PRE_GAME"
                        last_stage = None
                        continue

                    if self.stop_goal_rounds_enabled and self.rounds_played >= self.stop_goal_rounds_target:
                        goal_msg = f"วิ่งครบตามเป้าหมาย {self.stop_goal_rounds_target} รอบ"
                        self.log(f"🎯 บรรลุเป้าหมาย: {goal_msg}! กำลังหยุดการทำงานบอทอัตโนมัติ...", "success")
                        uptime_sec = int(time.time() - self.start_time) if self.start_time else 0
                        hours, remainder = divmod(uptime_sec, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        discord_notifier.send_goal_reached(
                            goal_description=goal_msg,
                            uptime=uptime_str,
                            rounds_played=self.rounds_played,
                            total_boxes=self.mystery_boxes,
                            coins_earned=self.session_coins_earned,
                            session_xp=self.session_xp_earned,
                        )
                        break

                    elapsed_hours = (time.time() - self.start_time) / 3600 if self.start_time else 0
                    if self.stop_goal_time_enabled and elapsed_hours >= self.stop_goal_time_hours:
                        goal_msg = f"ปล่อยบอทครบตามเป้าหมาย {self.stop_goal_time_hours:g} ชั่วโมง"
                        self.log(f"🎯 บรรลุเป้าหมาย: {goal_msg}! กำลังหยุดการทำงานบอทอัตโนมัติ...", "success")
                        uptime_sec = int(time.time() - self.start_time) if self.start_time else 0
                        hours, remainder = divmod(uptime_sec, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        discord_notifier.send_goal_reached(
                            goal_description=goal_msg,
                            uptime=uptime_str,
                            rounds_played=self.rounds_played,
                            total_boxes=self.mystery_boxes,
                            coins_earned=self.session_coins_earned,
                            session_xp=self.session_xp_earned,
                        )
                        break

                    if not is_first_game:
                        delay = random.uniform(5, 10)
                        self.log(f"⏳ Waiting {delay:.1f}s before starting next round to avoid detection...")
                        if self.interruptible_sleep(delay):
                            break

                    is_first_game = False
                    start_game(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"

                elif stage == "PURCHASE_ITEM":
                    self.log("🛒 Detected Stage: PURCHASE_ITEM", "stage")
                    # หน้าซื้อบูสต์/ไอเทม = เฟสก่อนเกม (เริ่มจาก PLAY แต่ยังไม่วิ่ง)
                    # — reset group กลับ PRE_GAME กัน state IN_GAME ค้างตอนซื้อของ
                    #   (ไม่งั้น humanlike thread เริ่ม/แตกกระพริบระหว่างซื้อ)
                    detection_group = "PRE_GAME"

                    if self.use_fast_start:
                        stock_fs = extract_item_stock(device_screen, "fast_start")
                        if stock_fs > 99:
                            self.log(f"⚠️ Fast Start อ่านได้ {stock_fs} ดูเพี้ยน (>99) — ถือว่า OCR พลาด จะลองซื้อกันพลาด", "warning")
                            stock_fs = 0
                        if stock_fs <= self.fast_start_min_stock:
                            self.log(f"⚡ Fast Start ในคลัง ({stock_fs} ชิ้น <= เกณฑ์ {self.fast_start_min_stock}) -> กำลังซื้อเพิ่ม...", "info")
                            purchase_fast_start(self.device_ip, self.device_port)
                        else:
                            self.log(f"⚡ Fast Start ในคลังมี {stock_fs} ชิ้น (มากกว่าเกณฑ์ {self.fast_start_min_stock}) -> ข้ามการซื้อเพื่อประหยัดเหรียญ", "info")
                    else:
                        self.log("⚡ Fast Start ปิดอยู่ (OFF) — ข้ามการเช็คซื้อในหน้า PURCHASE_ITEM", "info")

                    if self.use_cookie_relay:
                        stock_cr = extract_item_stock(device_screen, "cookie_relay")
                        if stock_cr > 99:
                            self.log(f"⚠️ Cookie Relay อ่านได้ {stock_cr} ดูเพี้ยน (>99) — ถือว่า OCR พลาด จะลองซื้อกันพลาด", "warning")
                            stock_cr = 0
                        if stock_cr <= self.cookie_relay_min_stock:
                            self.log(f"🍪 Cookie Relay ในคลัง ({stock_cr} ชิ้น <= เกณฑ์ {self.cookie_relay_min_stock}) -> กำลังซื้อเพิ่ม...", "info")
                            purchase_cookie_relay(self.device_ip, self.device_port)
                        else:
                            self.log(f"🍪 Cookie Relay ในคลังมี {stock_cr} ชิ้น (มากกว่าเกณฑ์ {self.cookie_relay_min_stock}) -> ข้ามการซื้อเพื่อประหยัดเหรียญ", "info")
                    else:
                        self.log("🍪 Cookie Relay ปิดอยู่ (OFF) — ข้ามการเช็คซื้อในหน้า PURCHASE_ITEM", "info")

                    # Boost Selection (Buy some Boosts!) — sync checked state to web settings
                    self.log(f"✨ Boost Selection sync: HP={'ON' if self.hp_extension_enabled else 'OFF'} "
                             f"| Jelly={'ON' if self.power_jelly_enabled else 'OFF'} "
                             f"| DXP={'ON' if self.double_xp_enabled else 'OFF'}", "info")
                    try:
                        sync_boost_selection(self.hp_extension_enabled, self.power_jelly_enabled, self.double_xp_enabled,
                                             self.device_ip, self.device_port)
                    except Exception as e:
                        self.log(f"⚠️ Boost Selection sync failed: {e}", "warning")

                    if self.use_desired_random_boost:
                        # lookup สดทุกรอบ — ถ้า user เปลี่ยน boost ในเว็บระหว่างรันจะได้ตัวใหม่ทันที
                        _boost_item = next((b for b in BOOST_OPTIONS if b["id"] == self.desired_boost_id), None)
                        if _boost_item is None:
                            _boost_item = BOOST_OPTIONS[0]
                            self.log(f"⚠️ desired_boost_id='{self.desired_boost_id}' ไม่พบใน BOOST_OPTIONS — fallback เป็น {_boost_item['name']}", "warning")
                        _desired_tpl, _desired_name = _boost_item["template"], _boost_item["name"]
                        self.log(f"🎲 Rolling boost for: {_desired_name} (id={self.desired_boost_id})...", "info")
                        purchase_desired_random_boost(_desired_tpl, _desired_name, self.device_ip, self.device_port, desired_boost_id=self.desired_boost_id)
                    play_game(self.device_ip, self.device_port)
                    # Root-cause fix (ON/OFF flicker): อย่าตั้ง IN_GAME ทันทีหลังกด Play
                    # — บางรอบมี PURCHASE_ITEM จริงคั่นก่อนเข้าเกม (ไม่ใช่ false positive)
                    #   ถ้าตั้ง IN_GAME ทันที → humanlike thread เริ่ม/กระพริบก่อน handler จะรีเซ็ตกลับ PRE_GAME
                    # → ตั้ง PRE_GAME ไว้ก่อน ให้ main loop รอบถัดไปตรวจจากภาพจริงตัดสินเอง:
                    #   - is_game_run_visible() == True → จะพลิกเป็น IN_GAME เอง (บรรทัด 873-876)
                    #   - หรือเจอ GAME_START/GAME_RELAY → handler นั้นจะตั้ง IN_GAME ให้เอง
                    detection_group = "PRE_GAME"
                    self.rounds_played += 1
                    self.current_round_start_time = time.time()
                    self.current_round_recorded = False
                    self.current_round_screen = None
                    self.log(f"🏁 Round {self.rounds_played} started!", "success")
                    if self.use_fast_start:
                        self.log("⏳ รอตรวจ GAME_START หลังกด PLAY (fallback 3s)...", "info")
                        for _ in range(6):
                            if self.should_stop:
                                break
                            time.sleep(random.uniform(0.35, 0.55))
                            try:
                                fb = device_capture_screen(self.device_ip, self.device_port)
                                if fb is not None:
                                    self.update_frame(fb)
                                    if detect_stage(fb, ["GAME_START"]) == "GAME_START":
                                        self.log("🏁 [Fallback] เจอ GAME_START หลัง PLAY — กำลังกดใช้ Fast Start ทันที!", "success")
                                        using_fast_start(self.device_ip, self.device_port)
                                        last_stage = "GAME_START"
                                        break
                            except Exception:
                                pass
                    if self.interruptible_sleep(random.uniform(0.15, 0.30)):
                        break
                    last_stage = None

                elif stage == "GAME_START":
                    self.log("🏁 Detected Stage: GAME_START", "stage")
                    if self.use_fast_start:
                        self.log(f"⚡ Fast Start เปิดอยู่ (ON) — กำลังกดใช้ไอเทมที่ (655,340)...", "info")
                        using_fast_start(self.device_ip, self.device_port)
                    else:
                        self.log("⚡ Fast Start ปิดอยู่ (OFF) — ข้ามการใช้ไอเทม", "info")
                    detection_group = "IN_GAME"

                elif stage == "GAME_RELAY":
                    self.log("🔄 Detected Stage: GAME_RELAY (Cookie Relay Triggered)", "stage")
                    if self.use_cookie_relay:
                        self.log(f"🍪 Cookie Relay เปิดอยู่ (ON) — กำลังกดใช้ตัวผลัดที่ (655,340)...", "info")
                        using_cookie_relay(self.device_ip, self.device_port)
                    else:
                        self.log("🍪 Cookie Relay ปิดอยู่ (OFF) — ข้ามการใช้ตัวผลัด", "info")
                    detection_group = "IN_GAME"

                elif stage == "GAME_COMPLETE":
                    self.log("✅ Detected Stage: GAME_COMPLETE (กำลังรอสรุปผลคะแนน, เหรียญ & EXP...)", "stage")
                    time.sleep(random.uniform(0.5, 0.8))
                    safe_device_tap(self.device_ip, self.device_port, 640, 260)

                    self.log("⏳ รอเหรียญ/EXP นับเสร็จ (adaptive polling)...", "info")
                    poll_deadline = time.time() + 8.0
                    last_coins = -1
                    last_xp = -1
                    stable_count = 0
                    round_coins = 0
                    round_xp = 0
                    second_tap_done = False
                    while time.time() < poll_deadline:
                        if self.should_stop:
                            break
                        time.sleep(random.uniform(0.32, 0.48))
                        try:
                            fresh_screen = device_capture_screen(self.device_ip, self.device_port)
                            if fresh_screen is not None:
                                device_screen = fresh_screen
                                self.update_frame(device_screen)
                        except Exception:
                            continue
                        c = extract_result_coins(device_screen) if device_screen is not None else 0
                        x = extract_result_xp(device_screen) if device_screen is not None else 0
                        if not second_tap_done and time.time() > poll_deadline - 6.5 and c == 0:
                            safe_device_tap(self.device_ip, self.device_port, 640, 260)
                            second_tap_done = True
                            continue
                        if c == last_coins and x == last_xp and c != 0:
                            stable_count += 1
                            if stable_count >= 2:
                                round_coins, round_xp = c, x
                                self.log(f"🔒 ตัวเลขนิ่งแล้ว: {c:,} 🪙 / {x:,} EXP — พร้อมกด OK", "info")
                                break
                        else:
                            stable_count = 0
                        last_coins, last_xp = c, x
                        round_coins, round_xp = c, x

                    if round_coins == 0 and device_screen is not None:
                        self.log("⚠️ ยังอ่านเหรียญได้ 0 — ลองแตะซ้ำแล้วอ่านใหม่", "warning")
                        safe_device_tap(self.device_ip, self.device_port, 640, 260)
                        time.sleep(random.uniform(0.8, 1.25))
                        try:
                            fresh_screen = device_capture_screen(self.device_ip, self.device_port)
                            if fresh_screen is not None:
                                device_screen = fresh_screen
                                round_coins = extract_result_coins(device_screen)
                                round_xp = extract_result_xp(device_screen)
                        except Exception:
                            pass

                    if device_screen is not None:
                        self.current_round_screen = device_screen.copy()
                        try:
                            _, buf = cv2.imencode(".jpg", device_screen, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            self.round_screenshots[self.rounds_played] = buf.tobytes()
                            if len(self.round_screenshots) > 50:
                                oldest_key = min(self.round_screenshots.keys())
                                del self.round_screenshots[oldest_key]
                        except Exception:
                            pass

                    if round_coins > 0:
                        self.session_coins_earned += round_coins
                        self.last_round_coins = round_coins
                    if round_xp > 0:
                        self.session_xp_earned += round_xp
                        self.last_round_xp = round_xp

                    round_boxes = detect_result_screen_mystery_box(device_screen) if device_screen is not None else []
                    if round_boxes:
                        for b in round_boxes:
                            self.box_counts[b] = self.box_counts.get(b, 0) + 1
                        self.box_counts["total"] += len(round_boxes)
                        self.mystery_boxes = self.box_counts["total"]

                    if not self.current_round_recorded:
                        dur_sec = int(time.time() - self.current_round_start_time) if self.current_round_start_time else 0
                        dur_str = f"{dur_sec // 60}m {dur_sec % 60}s" if dur_sec >= 60 else f"{dur_sec}s"

                        item = {
                            "round": self.rounds_played,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "duration": dur_str,
                            "coins": round_coins,
                            "xp": round_xp,
                            "boxes": round_boxes,
                            "box_count": len(round_boxes),
                            "has_screenshot": True,
                        }
                        self.round_history.appendleft(item)
                        self.current_round_recorded = True
                        xp_log = f" | +{round_xp:,} EXP" if round_xp > 0 else ""
                        box_log = f" | 📦 ได้รับกล่อง {len(round_boxes)} กล่อง" if round_boxes else ""
                        self.log(f"🏁 จบรอบที่ #{self.rounds_played}: ได้รับ +{round_coins:,} 🪙{xp_log}{box_log} (ยอดสะสม: {self.session_coins_earned:,} 🪙 | {self.session_xp_earned:,} EXP)", "success")
                        discord_notifier.send_round_summary(
                            round_num=self.rounds_played,
                            duration_str=dur_str,
                            coins_earned=round_coins,
                            session_coins=self.session_coins_earned,
                            xp_earned=round_xp,
                            session_xp=self.session_xp_earned,
                            boxes=round_boxes,
                            screen_img=device_screen,
                        )

                    jitter = random.uniform(0.5, 1.5)
                    self.log(f"⏳ รอ {jitter:.1f}s ก่อนกด OK (jitter 0.5-1.5s)...", "info")
                    if self.interruptible_sleep(jitter):
                        break

                    complete_finish(self.device_ip, self.device_port)
                    detection_group = "POST_GAME"

                elif stage == "MYSTERY_BOX":
                    time.sleep(random.uniform(0.75, 1.35))
                    fresh_mb_screen = device_capture_screen(self.device_ip, self.device_port)
                    if fresh_mb_screen is not None:
                        device_screen = fresh_mb_screen

                    detected_grades = detect_mystery_box_grades(device_screen)
                    if not detected_grades:
                        detected_grades = ["wood"]

                    box_names_th = {
                        "wood": "🟤 ไม้",
                        "silver": "⚪ เงิน",
                        "gold": "🟡 ทอง",
                        "rainbow": "🌈 รุ้ง",
                    }
                    grade_str = ", ".join([box_names_th.get(g, g) for g in detected_grades])

                    for g in detected_grades:
                        self.box_counts[g] = self.box_counts.get(g, 0) + 1
                    self.box_counts["total"] += len(detected_grades)
                    self.mystery_boxes = self.box_counts["total"]

                    dur_sec = int(time.time() - self.current_round_start_time) if self.current_round_start_time else 0
                    dur_str = f"{dur_sec // 60}m {dur_sec % 60}s" if dur_sec >= 60 else f"{dur_sec}s"

                    if device_screen is not None:
                        try:
                            _, buf = cv2.imencode(".jpg", device_screen, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            self.round_screenshots[self.rounds_played] = buf.tobytes()
                            if len(self.round_screenshots) > 50:
                                oldest_key = min(self.round_screenshots.keys())
                                del self.round_screenshots[oldest_key]
                        except Exception:
                            pass

                    if self.round_history and self.round_history[0]["round"] == self.rounds_played:
                        self.round_history[0]["boxes"] = detected_grades
                        self.round_history[0]["box_count"] = len(detected_grades)
                    else:
                        round_coins = extract_result_coins(device_screen) if device_screen is not None else 0
                        round_xp = extract_result_xp(device_screen) if device_screen is not None else 0
                        if round_coins > 0:
                            self.session_coins_earned += round_coins
                            self.last_round_coins = round_coins
                        if round_xp > 0:
                            self.session_xp_earned += round_xp
                            self.last_round_xp = round_xp

                        item = {
                            "round": self.rounds_played,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "duration": dur_str,
                            "coins": round_coins,
                            "xp": round_xp,
                            "boxes": detected_grades,
                            "box_count": len(detected_grades),
                            "has_screenshot": True,
                        }
                        self.round_history.appendleft(item)
                        self.current_round_recorded = True

                    self.log(f"🎁 ได้รับกล่องปริศนา: [{grade_str}] (รวมทั้งหมด: {self.mystery_boxes} กล่อง)", "success")
                    discord_notifier.send_box_drop(
                        self.rounds_played,
                        detected_grades,
                        self.box_counts,
                        coins_earned=self.last_round_coins,
                        session_coins=self.session_coins_earned,
                        xp_earned=self.last_round_xp,
                        session_xp=self.session_xp_earned,
                        screen_img=device_screen
                    )

                    accept_mystery_box(self.device_ip, self.device_port)
                    if self.interruptible_sleep(random.uniform(1.7, 2.4)):
                        break
                    detection_group = "POST_GAME"
                    last_stage = None

                elif stage == "CONGRATULATIONS":
                    self.log("🎉 Detected Stage: CONGRATULATIONS", "stage")
                    accept_congratulations(self.device_ip, self.device_port)
                    detection_group = "POST_GAME"
                    last_stage = None

                elif stage == "LEVEL_UP":
                    self.log("⬆️ Detected Stage: LEVEL_UP", "success")
                    accept_level_up(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"

                elif stage == "DAILY_CHECKIN":
                    self.log("📅 Detected Stage: DAILY_CHECKIN", "stage")
                    accept_daily_checkin(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"

                elif stage == "DAILY_CHECKIN_BOOST_SET":
                    self.log("📅 Detected Stage: DAILY_CHECKIN_BOOST_SET", "stage")
                    accept_daily_checkin_boost_set(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"

                elif stage == "DAILY_TREASURE":
                    self.log("💎 Detected Stage: DAILY_TREASURE", "stage")
                    accept_daily_treasure(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"

                elif stage == "DAILY_NEW":
                    self.log("📰 Detected Stage: DAILY_NEW", "stage")
                    accept_daily_new(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"

                elif stage == "ENTER_LEAGUE":
                    self.log("🏆 Detected Stage: ENTER_LEAGUE", "stage")
                    accept_enter_league(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"

                elif stage == "LEAGUE_RESULTS":
                    self.log("🏆 Detected Stage: LEAGUE_RESULTS", "stage")
                    accept_league_results(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"

                elif stage == "PREVIOUS_RANK_RESULTS":
                    self.log("🏆 Detected Stage: PREVIOUS_RANK_RESULTS", "stage")
                    accept_previous_rank_results(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"

                elif stage == "OVERTAKE_BREAK_SCORE":
                    self.log("🏆 Detected Stage: OVERTAKE_BREAK_SCORE", "stage")
                    accept_overtake_break_score(self.device_ip, self.device_port)
                    detection_group = "POST_GAME"
                    last_stage = None

                elif stage == "TOO_MANY_TREASURES":
                    self.log("💎 Detected Stage: TOO_MANY_TREASURES", "warning")
                    accept_too_many_treasures(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"

                elif stage == "RELIC_COMPLETE":
                    self.log("🏺 Detected Stage: RELIC_COMPLETE", "stage")
                    open_relic_complete(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"

                elif stage == "RELIC_CLAIM":
                    self.log("🏺 Detected Stage: RELIC_CLAIM", "stage")
                    accept_relic_claim(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"

                elif stage == "ANTI_BOT":
                    self.log("⚠️ Detected Stage: ANTI_BOT — solving captcha automatically...", "warning")
                    discord_notifier.send_anti_bot_alert("ANTI_BOT", screen_img=device_screen)
                    handle_anti_bot(device_screen, self.device_ip, self.device_port)
                    last_stage = None

                elif stage == "CONNECTION_LOST":
                    self.log("🔌 Detected Stage: CONNECTION_LOST — resetting app...", "error")
                    discord_notifier.send_connection_lost(self.device_ip, self.device_port)
                    device_reset_app(self.device_ip, self.device_port)
                    if self.interruptible_sleep(random.uniform(4.5, 5.8)):
                        break
                    close_announcement_dialog(self.device_ip, self.device_port)
                    session_start_time = time.time()
                    session_reset_interval = random.uniform(*SESSION_RESET_INTERVAL)
                    last_lives_time = time.time()
                    lives_interval = random.uniform(25 * 60, 35 * 60)
                    detection_group = "PRE_GAME"
                    last_stage = None
                    is_first_game = True

                elif stage == "EMU_HOME":
                    from config import EMU_HOME_TAP
                    self.log(f"🏠 Detected Stage: EMU_HOME — tapping CookieRun Classic at {EMU_HOME_TAP}...", "warning")
                    handle_emu_home(self.device_ip, self.device_port)
                    detection_group = "PRE_GAME"
                    last_stage = None
                    is_first_game = True

                elif stage == "INACTIVE":
                    self.log("💤 Detected Stage: INACTIVE — reconnecting...", "warning")
                    handle_inactive(self.device_ip, self.device_port)
                    last_stage = None

                elif stage == "FRIEND_INFO_POPUP":
                    self.log("👥 Detected Stage: FRIEND_INFO_POPUP — closing popup...", "stage")
                    close_friend_info_popup(self.device_ip, self.device_port)
                    last_stage = None
                    # ไม่เปลี่ยน detection_group — ให้วนกลับไปตรวจ stage เดิมต่อทันที

                elif stage == "ANR_DIALOG":
                    self.log("⚠️ Detected Stage: ANR_DIALOG — tapping Wait...", "warning")
                    handle_anr(self.device_ip, self.device_port)
                    last_stage = None

                elif stage == "ANNOUNCEMENT_POPUP":
                    self.log("❌ Detected Stage: ANNOUNCEMENT_POPUP — closing popup...", "warning")
                    close_announcement_dialog(self.device_ip, self.device_port)
                    last_stage = None

                elif stage == "CONFIRM_POPUP":
                    self.log("✅ Detected Stage: CONFIRM_POPUP — tapping confirm...", "warning")
                    tap_confirm_popup(self.device_ip, self.device_port)
                    last_stage = None

                loop_sleep = random.uniform(0.05, 0.30) if detection_group == "IN_GAME" else random.uniform(0.08, 0.35)
                if self.interruptible_sleep(loop_sleep):
                    break

        except Exception as e:
            self.log(f"❌ Bot runtime error: {e}", "error")
        finally:
            self._stop_humanlike_thread()
            with self.lock:
                self.is_running = False
                self.current_stage = "IDLE"
            self.log("⏹️ Bot execution ended", "info")


# Global singleton for backward compatibility (legacy single-instance code)
# New code should use BotEngine(instances dict) via web_server.bot_instances
bot_engine = BotEngine(
    instance_id="device_1",
    device_ip=config.DEVICE_IP,
    device_port=config.DEVICE_PORT,
    device_name="จอ 1",
)
