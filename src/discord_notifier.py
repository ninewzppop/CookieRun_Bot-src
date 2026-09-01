import io
import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional

import cv2
import requests


CONFIG_FILE = os.path.join(os.path.dirname(__file__), "discord_config.json")


class DiscordNotifier:
    def __init__(self):
        self.webhook_url: str = ""
        self.enabled: bool = False
        self.notify_boxes: bool = True
        self.notify_rounds: bool = True
        self.notify_antibot: bool = True
        self.notify_status: bool = True
        self.attach_screenshot: bool = True
        self.load_config()

    def load_config(self):
        if os.path.isfile(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.webhook_url = data.get("webhook_url", "")
                    self.enabled = bool(data.get("enabled", False))
                    self.notify_boxes = bool(data.get("notify_boxes", True))
                    self.notify_rounds = bool(data.get("notify_rounds", True))
                    self.notify_antibot = bool(data.get("notify_antibot", True))
                    self.notify_status = bool(data.get("notify_status", True))
                    self.attach_screenshot = bool(data.get("attach_screenshot", True))
            except Exception as e:
                print(f"[Discord] Error loading config: {e}")

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "webhook_url": self.webhook_url,
                    "enabled": self.enabled,
                    "notify_boxes": self.notify_boxes,
                    "notify_rounds": self.notify_rounds,
                    "notify_antibot": self.notify_antibot,
                    "notify_status": self.notify_status,
                    "attach_screenshot": self.attach_screenshot,
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Discord] Error saving config: {e}")

    def update_settings(self, settings: dict):
        if "webhook_url" in settings:
            self.webhook_url = str(settings["webhook_url"]).strip()
        if "enabled" in settings:
            self.enabled = bool(settings["enabled"])
        if "notify_boxes" in settings:
            self.notify_boxes = bool(settings["notify_boxes"])
        if "notify_rounds" in settings:
            self.notify_rounds = bool(settings["notify_rounds"])
        if "notify_antibot" in settings:
            self.notify_antibot = bool(settings["notify_antibot"])
        if "notify_status" in settings:
            self.notify_status = bool(settings["notify_status"])
        if "attach_screenshot" in settings:
            self.attach_screenshot = bool(settings["attach_screenshot"])
        self.save_config()

    def _async_send(self, payload: dict, screen_img=None):
        """Send webhook in a separate daemon thread so it never lags the bot loop."""
        threading.Thread(target=self._send_payload, args=(payload, screen_img), daemon=True).start()

    def _send_payload(self, payload: dict, screen_img=None):
        if not self.enabled or not self.webhook_url:
            return False

        try:
            files = {}
            if screen_img is not None and self.attach_screenshot:
                success, encoded_img = cv2.imencode(".jpg", screen_img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if success:
                    files["file"] = ("screen.jpg", io.BytesIO(encoded_img), "image/jpeg")
                    if "embeds" in payload and payload["embeds"]:
                        payload["embeds"][0]["image"] = {"url": "attachment://screen.jpg"}

            if files:
                data = {"payload_json": json.dumps(payload)}
                res = requests.post(self.webhook_url, data=data, files=files, timeout=10)
            else:
                res = requests.post(self.webhook_url, json=payload, timeout=10)

            return res.status_code in [200, 204]
        except Exception as e:
            print(f"[Discord] Webhook send error: {e}")
            return False

    def test_webhook(self, url: Optional[str] = None) -> tuple[bool, str]:
        """Test the webhook URL with a friendly test embed."""
        target_url = (url or self.webhook_url).strip()
        if not target_url:
            return False, "กรุณากรอก Discord Webhook URL"

        embed = {
            "title": "🍪 ทดสอบการแจ้งเตือน CookieRun Classic Bot",
            "description": "✅ เชื่อมต่อระบบแจ้งเตือน Discord Webhook สำเร็จเรียบร้อยแล้ว!",
            "color": 0x22C55E,  # Green
            "fields": [
                {
                    "name": "💰 ตัวอย่างเหรียญ (Coins)",
                    "value": "• **รอบนี้:** `+2,284` 🪙\n• **สะสมทั้งหมด:** `+14,506` 🪙",
                    "inline": True,
                },
                {
                    "name": "⭐ ตัวอย่าง EXP",
                    "value": "• **รอบนี้:** `+1,256` EXP\n• **สะสมทั้งหมด:** `+8,200` EXP",
                    "inline": True,
                },
                {"name": "⏰ เวลาทดสอบ", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "inline": False},
                {"name": "🤖 สถานะ", "value": "พร้อมรับการแจ้งเตือนทุกรอบ", "inline": True},
            ],
            "footer": {"text": "CookieRun Classic Bot - Web Dashboard"},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        try:
            res = requests.post(target_url, json={"username": "CookieRun Bot", "embeds": [embed]}, timeout=10)
            if res.status_code in [200, 204]:
                return True, "ส่งข้อความทดสอบสำเร็จ! โปรดตรวจสอบในห้อง Discord ของคุณ"
            return False, f"ส่งข้อความไม่สำเร็จ (HTTP {res.status_code}): {res.text[:100]}"
        except Exception as e:
            return False, f"ส่งข้อความไม่สำเร็จ: {str(e)}"

    def send_bot_start(self, device_ip: str, device_port: int):
        if not self.notify_status or not self.enabled or not self.webhook_url:
            return

        embed = {
            "title": "🟢 บอทเริ่มทำงาน (Bot Started)",
            "description": "🚀 เริ่มต้นการทำงานของบอทฟาร์ม CookieRun Classic",
            "color": 0x22C55E,  # Green
            "fields": [
                {"name": "📱 อุปกรณ์", "value": f"`{device_ip}:{device_port}`", "inline": True},
                {"name": "⏰ เวลาเริ่มต้น", "value": datetime.now().strftime("%H:%M:%S"), "inline": True},
            ],
            "footer": {"text": "CookieRun Classic Bot"},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self._async_send({"username": "CookieRun Bot", "embeds": [embed]})

    def send_bot_stop(self, uptime: str, rounds_played: int, total_boxes: int, coins_earned: int = 0, session_xp: int = 0):
        if not self.notify_status or not self.enabled or not self.webhook_url:
            return

        embed = {
            "title": "🔴 บอทหยุดทำงาน (Bot Stopped)",
            "description": "⏹️ บอทหยุดการทำงานเรียบร้อยแล้ว",
            "color": 0xEF4444,  # Red
            "fields": [
                {"name": "⏱️ เวลาทำงานรวม", "value": uptime, "inline": True},
                {"name": "🔄 รอบที่เล่น", "value": f"{rounds_played} รอบ", "inline": True},
                {"name": "🎁 กล่องปริศนา", "value": f"{total_boxes} กล่อง", "inline": True},
                {"name": "💰 เหรียญสะสมทั้งหมด", "value": f"+{coins_earned:,} 🪙", "inline": True},
                {"name": "⭐ EXPสะสมทั้งหมด", "value": f"+{session_xp:,} EXP", "inline": True},
                {"name": "⏰ เวลาหยุด", "value": datetime.now().strftime("%H:%M:%S"), "inline": True},
            ],
            "footer": {"text": "CookieRun Classic Bot"},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self._async_send({"username": "CookieRun Bot", "embeds": [embed]})

    def send_box_drop(self, round_num: int, boxes: List[str], total_boxes: Dict[str, int], coins_earned: int = 0, session_coins: int = 0, xp_earned: int = 0, session_xp: int = 0, screen_img=None):
        if not self.notify_boxes or not self.enabled or not self.webhook_url:
            return

        box_icons = {
            "wood": "🟤 กล่องไม้",
            "silver": "⚪ กล่องเงิน",
            "gold": "🟡 กล่องทอง",
            "rainbow": "🌈 กล่องรุ้ง",
        }

        boxes_str = " + ".join([box_icons.get(b, b) for b in boxes])

        # Pick color based on rarest box
        color = 0x854D0E  # Wood (Brown)
        if "rainbow" in boxes:
            color = 0xC084FC  # Purple/Pink for Rainbow
        elif "gold" in boxes:
            color = 0xEAB308  # Gold
        elif "silver" in boxes:
            color = 0x94A3B8  # Silver

        fields = [
            {
                "name": "💰 เหรียญ (Coins)",
                "value": f"• **รอบนี้:** `+{coins_earned:,}` 🪙\n• **สะสมทั้งหมด:** `+{session_coins:,}` 🪙",
                "inline": True,
            },
            {
                "name": "⭐ ค่าประสบการณ์ (EXP)",
                "value": f"• **รอบนี้:** `+{xp_earned:,}` EXP\n• **สะสมทั้งหมด:** `+{session_xp:,}` EXP",
                "inline": True,
            },
            {
                "name": "📦 สถิติกล่องสะสม",
                "value": (
                    f"🟤 ไม้: **{total_boxes.get('wood', 0)}** | "
                    f"⚪ เงิน: **{total_boxes.get('silver', 0)}**\n"
                    f"🟡 ทอง: **{total_boxes.get('gold', 0)}** | "
                    f"🌈 รุ้ง: **{total_boxes.get('rainbow', 0)}**"
                ),
                "inline": False,
            },
            {"name": "🏆 รวมกล่องทั้งหมด", "value": f"**{total_boxes.get('total', 0)}** กล่อง", "inline": True},
            {"name": "⏰ เวลา", "value": datetime.now().strftime("%H:%M:%S"), "inline": True},
        ]

        embed = {
            "title": f"🎁 ได้รับกล่องปริศนา! (รอบที่ #{round_num})",
            "description": f"✨ **กล่องที่ได้รอบนี้:** {boxes_str}",
            "color": color,
            "fields": fields,
            "footer": {"text": "CookieRun Classic Bot - Farm Tracker"},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        self._async_send({"username": "CookieRun Farm Tracker", "embeds": [embed]}, screen_img=screen_img)

    def send_round_summary(self, round_num: int, duration_str: str, coins_earned: int, session_coins: int, xp_earned: int, session_xp: int, boxes: List[str] = None, screen_img=None):
        if not self.notify_rounds or not self.enabled or not self.webhook_url:
            return

        # Always send round summary with complete coin, exp, and box summary

        box_icons = {
            "wood": "🟤 กล่องไม้",
            "silver": "⚪ กล่องเงิน",
            "gold": "🟡 กล่องทอง",
            "rainbow": "🌈 กล่องรุ้ง",
        }
        boxes_str = " + ".join([box_icons.get(b, b) for b in boxes]) if boxes else "*(ไม่ได้รับกล่อง)*"

        fields = [
            {
                "name": "💰 เหรียญ (Coins)",
                "value": f"• **รอบนี้:** `+{coins_earned:,}` 🪙\n• **สะสมทั้งหมด:** `+{session_coins:,}` 🪙",
                "inline": True,
            },
            {
                "name": "⭐ ค่าประสบการณ์ (EXP)",
                "value": f"• **รอบนี้:** `+{xp_earned:,}` EXP\n• **สะสมทั้งหมด:** `+{session_xp:,}` EXP",
                "inline": True,
            },
            {
                "name": "📦 กล่องปริศนา",
                "value": boxes_str,
                "inline": False,
            },
            {
                "name": "⏱️ ระยะเวลา",
                "value": f"`{duration_str}`",
                "inline": True,
            },
            {
                "name": "⏰ เวลาจบเกม",
                "value": datetime.now().strftime("%H:%M:%S"),
                "inline": True,
            },
        ]

        embed = {
            "title": f"🏁 สรุปผลลัพธ์รอบที่ #{round_num}",
            "description": f"✨ เล่นจบรอบที่ #{round_num} เรียบร้อยแล้ว",
            "color": 0x10B981,  # Emerald
            "fields": fields,
            "footer": {"text": "CookieRun Classic Bot - Round Summary"},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        self._async_send({"username": "CookieRun Farm Tracker", "embeds": [embed]}, screen_img=screen_img)

    def send_anti_bot_alert(self, stage: str, details: str = "", screen_img=None):
        if not self.notify_antibot or not self.enabled or not self.webhook_url:
            return

        embed = {
            "title": "⚠️ ตรวจพบระบบป้องกันบอท (Anti-Bot Captcha)",
            "description": f"🤖 กำลังแก้ระบบป้องกันอัตโนมัติ...\n{details}",
            "color": 0xF97316,  # Orange
            "fields": [
                {"name": "⏰ เวลาที่พบ", "value": datetime.now().strftime("%H:%M:%S"), "inline": True},
            ],
            "footer": {"text": "CookieRun Classic Bot - Security Alert"},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self._async_send({"username": "CookieRun Bot Alert", "embeds": [embed]}, screen_img=screen_img)

    def send_goal_reached(self, goal_description: str, uptime: str, rounds_played: int, total_boxes: int, coins_earned: int, session_xp: int):
        if not self.notify_status or not self.enabled or not self.webhook_url:
            return

        embed = {
            "title": "🎯 บรรลุเป้าหมายการฟาร์ม (Goal Reached)",
            "description": f"✨ **{goal_description}**\nบอทได้ทำการหยุดทำงานอัตโนมัติเรียบร้อยแล้ว",
            "color": 0xF59E0B,  # Amber / Gold
            "fields": [
                {"name": "🎯 เป้าหมายที่สำเร็จ", "value": goal_description, "inline": False},
                {"name": "⏱️ เวลาทำงานรวม", "value": uptime, "inline": True},
                {"name": "🔄 รอบที่เล่น", "value": f"{rounds_played} รอบ", "inline": True},
                {"name": "🎁 กล่องปริศนา", "value": f"{total_boxes} กล่อง", "inline": True},
                {"name": "💰 เหรียญสะสมทั้งหมด", "value": f"+{coins_earned:,} 🪙", "inline": True},
                {"name": "⭐ EXP สะสมทั้งหมด", "value": f"+{session_xp:,} EXP", "inline": True},
                {"name": "⏰ เวลาสิ้นสุด", "value": datetime.now().strftime("%H:%M:%S"), "inline": True},
            ],
            "footer": {"text": "CookieRun Classic Bot - Goal System"},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self._async_send({"username": "CookieRun Bot", "embeds": [embed]})


discord_notifier = DiscordNotifier()
