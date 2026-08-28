import asyncio
import io
import os
import time
from typing import Any, Dict, Optional

import cv2
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
import numpy as np
from pydantic import BaseModel

import config
from adb import (
    device_capture_screen,
    device_check_connection,
    device_reset_app,
    device_tap,
    get_adb_path,
)
from fastapi.staticfiles import StaticFiles
from bot_engine import BOOST_OPTIONS, bot_engine
from discord_notifier import discord_notifier

app = FastAPI(title="CookieRun Classic Bot Web Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates_path = os.path.join(os.path.dirname(__file__), "templates")
if os.path.isdir(templates_path):
    app.mount("/templates", StaticFiles(directory=templates_path), name="templates")

# Models
class StartBotRequest(BaseModel):
    device_ip: str = "127.0.0.1"
    device_port: int = 5595
    use_fast_start: bool = False
    fast_start_min_stock: int = 10
    use_cookie_relay: bool = False
    cookie_relay_min_stock: int = 10
    use_desired_random_boost: bool = False
    desired_boost_id: str = "double_coins"
    detect_relic: bool = True
    send_friend_lives: bool = True
    stop_goal_rounds_enabled: bool = False
    stop_goal_rounds_target: int = 50
    stop_goal_time_enabled: bool = False
    stop_goal_time_hours: float = 2.0


class ConnectionTestRequest(BaseModel):
    device_ip: str = "127.0.0.1"
    device_port: int = 5595


class TapRequest(BaseModel):
    x: int
    y: int
    device_ip: Optional[str] = None
    device_port: Optional[int] = None


class DiscordSettingsRequest(BaseModel):
    webhook_url: str = ""
    enabled: bool = False
    notify_boxes: bool = True
    notify_rounds: bool = True
    notify_antibot: bool = True
    notify_status: bool = True
    attach_screenshot: bool = True


class DiscordTestRequest(BaseModel):
    webhook_url: str = ""


@app.on_event("startup")
async def startup_event():
    bot_engine.loop = asyncio.get_event_loop()
    bot_engine.log(f"🌐 Web Server started. ADB path: {get_adb_path()}")


@app.get("/api/status")
def get_status():
    return bot_engine.get_status()


@app.get("/api/boosts")
def get_boost_options():
    return [{"id": b["id"], "name": b["name"]} for b in BOOST_OPTIONS]


SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "bot_settings.json")
DEFAULT_BOT_SETTINGS = {
    "device_ip": "127.0.0.1",
    "device_port": 5595,
    "use_fast_start": False,
    "fast_start_min_stock": 10,
    "use_cookie_relay": False,
    "cookie_relay_min_stock": 10,
    "use_desired_random_boost": False,
    "desired_boost_id": "double_coins",
    "detect_relic": True,
    "send_friend_lives": True,
    "stop_goal_rounds_enabled": False,
    "stop_goal_rounds_target": 50,
    "stop_goal_time_enabled": False,
    "stop_goal_time_hours": 2.0,
}


def load_bot_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            import json
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                res = DEFAULT_BOT_SETTINGS.copy()
                res.update(data)
                return res
        except Exception:
            pass
    return DEFAULT_BOT_SETTINGS.copy()


def save_bot_settings_to_file(settings: dict):
    try:
        import json
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save bot settings: {e}")


@app.get("/api/settings")
def get_bot_settings():
    return load_bot_settings()


@app.post("/api/settings/save")
def save_bot_settings(req: StartBotRequest):
    save_bot_settings_to_file(req.dict())
    return {"success": True, "message": "บันทึกการตั้งค่าบอทเรียบร้อยแล้ว"}


@app.post("/api/start")
def start_bot(req: StartBotRequest):
    # Auto-save settings on start
    save_bot_settings_to_file(req.dict())
    res = bot_engine.start(req.dict())
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/stop")
def stop_bot():
    res = bot_engine.stop()
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/reset-stats")
def reset_stats():
    bot_engine.reset_stats()
    return {"success": True}


@app.post("/api/test-connection")
def test_connection(req: ConnectionTestRequest):
    success, msg = device_check_connection(req.device_ip, req.device_port)
    return {
        "success": success,
        "message": msg,
        "adb_path": get_adb_path(),
    }


@app.post("/api/reset-app")
def trigger_reset_app(req: ConnectionTestRequest):
    try:
        device_reset_app(req.device_ip, req.device_port)
        return {"success": True, "message": "App reset command executed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tap")
def manual_tap(req: TapRequest):
    ip = req.device_ip or bot_engine.device_ip
    port = req.device_port or bot_engine.device_port
    try:
        device_tap(ip, port, req.x, req.y)
        return {"success": True, "x": req.x, "y": req.y}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/discord")
def get_discord_settings():
    return {
        "webhook_url": discord_notifier.webhook_url,
        "enabled": discord_notifier.enabled,
        "notify_boxes": discord_notifier.notify_boxes,
        "notify_rounds": discord_notifier.notify_rounds,
        "notify_antibot": discord_notifier.notify_antibot,
        "notify_status": discord_notifier.notify_status,
        "attach_screenshot": discord_notifier.attach_screenshot,
    }


@app.post("/api/discord/save")
def save_discord_settings(req: DiscordSettingsRequest):
    discord_notifier.update_settings(req.dict())
    return {"success": True, "message": "บันทึกการตั้งค่า Discord สำเร็จ"}


@app.post("/api/discord/test")
def test_discord_webhook(req: DiscordTestRequest):
    success, msg = discord_notifier.test_webhook(req.webhook_url)
    return {"success": success, "message": msg}


def generate_placeholder_frame(text: str = "CookieRun Bot Idle") -> bytes:
    img = np.zeros((480, 854, 3), dtype=np.uint8)
    img[:] = (20, 24, 35)  # Dark slate background
    # Add title text
    cv2.putText(img, "CookieRun Classic Bot", (240, 210), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 200, 100), 2, cv2.LINE_AA)
    cv2.putText(img, text, (270, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 190), 1, cv2.LINE_AA)
    cv2.putText(img, "Resolution: 1280x720 | Click Start to stream live screen", (190, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (120, 120, 130), 1, cv2.LINE_AA)
    _, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buffer.tobytes()


@app.get("/api/stream")
def video_feed():
    def frame_generator():
        last_idle_capture = 0
        while True:
            frame_bytes = None
            if bot_engine.is_running and bot_engine.latest_frame_jpeg is not None:
                frame_bytes = bot_engine.latest_frame_jpeg
            else:
                # If idle, try capturing a frame every 1.5s if device is reachable
                now = time.time()
                if now - last_idle_capture > 1.5:
                    last_idle_capture = now
                    try:
                        screen = device_capture_screen(bot_engine.device_ip, bot_engine.device_port)
                        bot_engine.update_frame(screen)
                        frame_bytes = bot_engine.latest_frame_jpeg
                    except Exception:
                        pass
                if frame_bytes is None:
                    frame_bytes = bot_engine.latest_frame_jpeg or generate_placeholder_frame("Device not connected / Idle")

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            time.sleep(0.1)

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/screenshot")
def get_screenshot():
    try:
        screen = device_capture_screen(bot_engine.device_ip, bot_engine.device_port)
        _, buffer = cv2.imencode(".png", screen)
        return Response(content=buffer.tobytes(), media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/round-screenshot/{round_num}")
def get_round_screenshot(round_num: int):
    jpeg_bytes = bot_engine.round_screenshots.get(round_num)
    if jpeg_bytes is not None:
        return Response(content=jpeg_bytes, media_type="image/jpeg")
    # Return fallback placeholder
    blank = np.zeros((480, 854, 3), dtype=np.uint8)
    blank[:] = (20, 24, 35)
    cv2.putText(blank, f"No screenshot for Round #{round_num}", (220, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 180, 190), 2, cv2.LINE_AA)
    _, buf = cv2.imencode(".jpg", blank)
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    queue = asyncio.Queue()
    bot_engine.ws_subscribers.append(queue)

    try:
        # Send existing log backlog
        for log_entry in list(bot_engine.logs):
            await websocket.send_json(log_entry)

        # Stream new logs
        while True:
            log_entry = await queue.get()
            await websocket.send_json(log_entry)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        if queue in bot_engine.ws_subscribers:
            bot_engine.ws_subscribers.remove(queue)


@app.get("/", response_class=HTMLResponse)
def get_index():
    index_path = os.path.join(os.path.dirname(__file__), "web", "index.html")
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Web Dashboard UI file not found in web/index.html</h1>"
