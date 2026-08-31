import asyncio
import io
import os
import time
import uuid
from typing import Any, Dict, Optional

import cv2
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
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
    safe_device_tap,
    get_adb_path,
)
from fastapi.staticfiles import StaticFiles
from bot_engine import BOOST_OPTIONS, BotEngine, bot_engine
from discord_notifier import discord_notifier

app = FastAPI(title="CookieRun Classic Bot Web Dashboard (Multi-Instance)", version="2.0.0")

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

# ---------------------------------------------------------------------------
# Multi-Instance Registry
# ---------------------------------------------------------------------------
# bot_instances: dict[instance_id, BotEngine]
bot_instances: Dict[str, BotEngine] = {}

def _init_instances_from_config():
    # Initialize from config.DEVICES if present, otherwise legacy single device
    devices = getattr(config, "DEVICES", None)
    if devices:
        for dev in devices:
            iid = dev.get("id", f"device_{len(bot_instances)+1}")
            if iid in bot_instances:
                continue
            eng = BotEngine(
                instance_id=iid,
                device_ip=dev.get("host", dev.get("device_ip", "127.0.0.1")),
                device_port=int(dev.get("port", dev.get("device_port", 5595))),
                device_name=dev.get("name", iid),
            )
            bot_instances[iid] = eng
    # Fallback: ensure at least legacy singleton is registered
    if not bot_instances:
        # use global bot_engine singleton
        bot_instances[bot_engine.instance_id] = bot_engine
    else:
        # also ensure legacy alias still points to device_1 if exists
        if bot_engine.instance_id not in bot_instances:
            # keep global singleton accessible for backward imports
            pass
        else:
            # sync global alias to the dict entry (so old code via `from bot_engine import bot_engine` stays consistent)
            # we replace object's __dict__? simpler: point reference
            pass

_init_instances_from_config()

# Persisted settings file for devices (optional, not required but useful)
DEVICES_FILE = os.path.join(os.path.dirname(__file__), "bot_settings.json")
# Legacy single-settings compat handled below; for multi we store per-instance overrides differently


# Models
class StartBotRequest(BaseModel):
    device_ip: Optional[str] = None
    device_port: Optional[int] = None
    host: Optional[str] = None
    port: Optional[int] = None
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
    humanlike_play_enabled: Optional[bool] = None
    humanlike_jump_enabled: Optional[bool] = None
    humanlike_jump_interval: Optional[float] = None
    humanlike_jump_double_enabled: Optional[bool] = None
    humanlike_jump_double_interval: Optional[float] = None
    humanlike_jump_double_gap: Optional[float] = None
    humanlike_slide_enabled: Optional[bool] = None
    humanlike_slide_interval: Optional[float] = None
    humanlike_slide_hold_duration: Optional[float] = None


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


class CreateInstanceRequest(BaseModel):
    id: Optional[str] = None
    name: str = "New Emulator"
    host: str = "127.0.0.1"
    port: int = 5595

    # alternative keys
    device_ip: Optional[str] = None
    device_port: Optional[int] = None


def _get_instance_or_404(instance_id: str) -> BotEngine:
    eng = bot_instances.get(instance_id)
    if not eng:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")
    return eng

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    for eng in bot_instances.values():
        eng.loop = loop
    # Log startup using first instance or global
    first = next(iter(bot_instances.values()), None)
    if first:
        first.log(f"🌐 Web Server (Multi-Instance) started. Instances: {list(bot_instances.keys())} | ADB path: {get_adb_path()}")
    else:
        bot_engine.loop = loop
        bot_engine.log(f"🌐 Web Server started. ADB path: {get_adb_path()}")


# ---------------------------------------------------------------------------
# Legacy Single-Instance Endpoints (backward compat — proxy to default instance)
# ---------------------------------------------------------------------------
def _default_instance() -> BotEngine:
    # Prefer device_1, else first available
    if "device_1" in bot_instances:
        return bot_instances["device_1"]
    return next(iter(bot_instances.values()))

@app.get("/api/status")
def get_status():
    return _default_instance().get_status()


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
    data = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    save_bot_settings_to_file(data)
    eng = _default_instance()
    if eng.is_running:
        eng.update_live_config(data)
    return {"success": True, "message": "บันทึกการตั้งค่าบอทเรียบร้อยแล้ว"}


@app.post("/api/start")
def start_bot(req: StartBotRequest):
    if hasattr(req, "model_dump"):
        data = req.model_dump(exclude_unset=True)
    else:
        data = req.dict(exclude_unset=True)
    # normalize host/port aliases (only if actually sent)
    if data.get("host"):
        data["device_ip"] = data["host"]
    if data.get("port"):
        data["device_port"] = data["port"]
    # Merge with existing file to not lose persisted settings
    existing = load_bot_settings()
    existing.update(data)
    save_bot_settings_to_file(existing)
    eng = _default_instance()
    res = eng.start(data)
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/stop")
def stop_bot():
    eng = _default_instance()
    res = eng.stop()
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@app.post("/api/reset-stats")
def reset_stats():
    _default_instance().reset_stats()
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
    eng = _default_instance()
    ip = req.device_ip or eng.device_ip
    port = req.device_port or eng.device_port
    try:
        safe_device_tap(ip, port, req.x, req.y)
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
    img[:] = (10, 10, 10)
    cv2.putText(img, "CookieRun Classic Bot", (240, 210), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (168, 196, 212), 2, cv2.LINE_AA)
    cv2.putText(img, text, (270, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 220, 232), 1, cv2.LINE_AA)
    cv2.putText(img, "Resolution: 1280x720 | Click Start to stream live screen", (190, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (140, 150, 160), 1, cv2.LINE_AA)
    _, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buffer.tobytes()


@app.get("/api/stream")
def video_feed():
    eng = _default_instance()
    def frame_generator():
        last_idle_capture = 0
        while True:
            frame_bytes = None
            if eng.is_running and eng.latest_frame_jpeg is not None:
                frame_bytes = eng.latest_frame_jpeg
            else:
                now = time.time()
                if now - last_idle_capture > 1.5:
                    last_idle_capture = now
                    try:
                        screen = device_capture_screen(eng.device_ip, eng.device_port)
                        eng.update_frame(screen)
                        frame_bytes = eng.latest_frame_jpeg
                    except Exception:
                        pass
                if frame_bytes is None:
                    frame_bytes = eng.latest_frame_jpeg or generate_placeholder_frame("Device not connected / Idle")

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            time.sleep(0.1)

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/screenshot")
def get_screenshot():
    eng = _default_instance()
    try:
        screen = device_capture_screen(eng.device_ip, eng.device_port)
        _, buffer = cv2.imencode(".png", screen)
        return Response(content=buffer.tobytes(), media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/round-screenshot/{round_num}")
def get_round_screenshot(round_num: int):
    eng = _default_instance()
    jpeg_bytes = eng.round_screenshots.get(round_num)
    if jpeg_bytes is not None:
        return Response(content=jpeg_bytes, media_type="image/jpeg")
    blank = np.zeros((480, 854, 3), dtype=np.uint8)
    blank[:] = (10, 10, 10)
    cv2.putText(blank, f"No screenshot for Round #{round_num}", (220, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 220, 232), 2, cv2.LINE_AA)
    _, buf = cv2.imencode(".jpg", blank)
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket, instance_id: Optional[str] = Query(default=None)):
    """
    WebSocket for live logs.
    - If instance_id query provided: stream only that instance's logs (each msg includes instance_id).
    - Otherwise: broadcast logs from ALL instances (each msg includes instance_id so frontend can separate).
    """
    await websocket.accept()
    # Determine which engines to subscribe to
    if instance_id:
        eng = bot_instances.get(instance_id)
        if not eng:
            await websocket.close(code=4404)
            return
        targets = [eng]
    else:
        targets = list(bot_instances.values())

    queues = []
    try:
        for eng in targets:
            q: asyncio.Queue = asyncio.Queue()
            eng.ws_subscribers.append(q)
            queues.append((eng, q))
            # Send backlog for this engine
            for log_entry in list(eng.logs):
                # ensure instance_id present
                if "instance_id" not in log_entry:
                    log_entry["instance_id"] = eng.instance_id
                await websocket.send_json(log_entry)

        # Stream loop: wait for any queue
        while True:
            # wait for first available message across all queues
            # create tasks
            tasks = [asyncio.create_task(q.get()) for _, q in queues]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for p in pending:
                p.cancel()
            for d in done:
                try:
                    log_entry = d.result()
                    # tag already contains instance_id from BotEngine.log
                    await websocket.send_json(log_entry)
                except Exception:
                    pass
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        for eng, q in queues:
            if q in eng.ws_subscribers:
                eng.ws_subscribers.remove(q)


# ---------------------------------------------------------------------------
# NEW Multi-Instance API (spec Step 4)
# ---------------------------------------------------------------------------

@app.get("/api/instances")
def list_instances():
    return [eng.get_status() for eng in bot_instances.values()]

@app.post("/api/instances")
def create_instance(req: CreateInstanceRequest):
    host = req.host or req.device_ip or "127.0.0.1"
    port = req.port or req.device_port or 5595
    iid = (req.id or "").strip()
    if not iid:
        # auto-generate: device_N
        iid = f"device_{len(bot_instances)+1}"
        # ensure unique
        base = iid
        counter = 1
        while iid in bot_instances:
            iid = f"{base}_{counter}"
            counter += 1
    else:
        if iid in bot_instances:
            raise HTTPException(status_code=400, detail=f"Instance id '{iid}' already exists")
    name = req.name.strip() or iid
    try:
        port = int(port)
    except:
        raise HTTPException(status_code=400, detail="port must be integer")
    eng = BotEngine(instance_id=iid, device_ip=host, device_port=port, device_name=name)
    # assign current event loop if available
    try:
        eng.loop = asyncio.get_event_loop()
    except:
        pass
    bot_instances[iid] = eng
    # Update config.DEVICES in memory for introspection
    try:
        config.DEVICES.append({"id": iid, "name": name, "host": host, "port": port})
    except:
        pass
    return {"success": True, "instance_id": iid, "status": eng.get_status()}

@app.get("/api/instances/{instance_id}/status")
def get_instance_status(instance_id: str):
    eng = _get_instance_or_404(instance_id)
    return eng.get_status()

@app.post("/api/instances/{instance_id}/start")
def start_instance(instance_id: str, req: StartBotRequest):
    eng = _get_instance_or_404(instance_id)
    # Use exclude_unset so only fields actually sent by frontend are considered — prevents defaults from overwriting persisted settings (fixes revert bug)
    if hasattr(req, "model_dump"):
        data = req.model_dump(exclude_unset=True)
    else:
        data = req.dict(exclude_unset=True)

    # Use instance's registered host/port as primary if payload is missing/None/empty
    # Frontend currently sends device_ip/device_port; host/port may be None (model default) — must not overwrite with None
    def _clean(v):
        if v is None:
            return None
        sv = str(v).strip()
        if sv == "" or sv.lower() == "none":
            return None
        return v

    # Resolve host
    host_from_payload = _clean(data.get("host"))
    device_ip_from_payload = _clean(data.get("device_ip"))
    # Priority: payload device_ip > payload host > instance's stored value
    final_host = device_ip_from_payload or host_from_payload or _clean(eng.device_ip)
    if final_host is None:
        final_host = eng.device_ip

    # Resolve port
    port_from_payload = _clean(data.get("port"))
    device_port_from_payload = _clean(data.get("device_port"))
    final_port_raw = device_port_from_payload if device_port_from_payload is not None else port_from_payload
    if final_port_raw is None:
        final_port_raw = _clean(eng.device_port)
    if final_port_raw is None:
        final_port_raw = eng.device_port

    # Validation before calling eng.start — give clear HTTP 400 instead of letting adb spam "None:port"
    if final_host is None or str(final_host).strip() == "" or str(final_host).lower() == "none":
        raise HTTPException(status_code=400, detail=f"instance '{instance_id}' ยังไม่ได้ตั้งค่า ADB host — กรุณาตรวจสอบ host (host={final_host}, port={final_port_raw})")
    if final_port_raw is None or str(final_port_raw).strip() == "" or str(final_port_raw).lower() == "none":
        raise HTTPException(status_code=400, detail=f"instance '{instance_id}' ยังไม่ได้ตั้งค่า ADB port — กรุณาตรวจสอบ port (host={final_host}, port={final_port_raw})")
    try:
        final_port = int(final_port_raw)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"instance '{instance_id}' ค่า port ไม่ถูกต้อง: {final_port_raw}")
    if not (1 <= final_port <= 65535):
        raise HTTPException(status_code=400, detail=f"instance '{instance_id}' ค่า port อยู่นอกช่วง 1-65535: {final_port}")

    # Normalize data to always contain valid host/port/device_ip/device_port — never None
    data["host"] = str(final_host).strip()
    data["port"] = final_port
    data["device_ip"] = str(final_host).strip()
    data["device_port"] = final_port

    res = eng.start(data)
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["message"])
    return res

@app.post("/api/instances/{instance_id}/stop")
def stop_instance(instance_id: str):
    eng = _get_instance_or_404(instance_id)
    res = eng.stop()
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["message"])
    return res

@app.delete("/api/instances/{instance_id}")
def delete_instance(instance_id: str):
    eng = bot_instances.get(instance_id)
    if not eng:
        raise HTTPException(status_code=404, detail="Instance not found")
    if eng.is_running:
        raise HTTPException(status_code=400, detail="Cannot delete running instance — stop it first")
    del bot_instances[instance_id]
    # remove from config.DEVICES
    try:
        config.DEVICES[:] = [d for d in config.DEVICES if d.get("id") != instance_id]
    except:
        pass
    return {"success": True, "message": f"Instance {instance_id} deleted"}

@app.post("/api/instances/{instance_id}/reset-stats")
def reset_instance_stats(instance_id: str):
    eng = _get_instance_or_404(instance_id)
    eng.reset_stats()
    return {"success": True}

# Per-instance Bot Settings (persistent, isolated)
class InstanceSettingsRequest(BaseModel):
    use_fast_start: Optional[bool] = None
    fast_start_min_stock: Optional[int] = None
    use_cookie_relay: Optional[bool] = None
    cookie_relay_min_stock: Optional[int] = None
    hp_extension_enabled: Optional[bool] = None
    power_jelly_enabled: Optional[bool] = None
    double_xp_enabled: Optional[bool] = None
    use_desired_random_boost: Optional[bool] = None
    desired_boost_id: Optional[str] = None
    detect_relic: Optional[bool] = None
    send_friend_lives: Optional[bool] = None
    stop_goal_rounds_enabled: Optional[bool] = None
    stop_goal_rounds_target: Optional[int] = None
    stop_goal_time_enabled: Optional[bool] = None
    stop_goal_time_hours: Optional[float] = None
    humanlike_play_enabled: Optional[bool] = None
    humanlike_jump_enabled: Optional[bool] = None
    humanlike_jump_interval: Optional[float] = None
    humanlike_jump_double_enabled: Optional[bool] = None
    humanlike_jump_double_interval: Optional[float] = None
    humanlike_jump_double_gap: Optional[float] = None
    humanlike_slide_enabled: Optional[bool] = None
    humanlike_slide_interval: Optional[float] = None
    humanlike_slide_hold_duration: Optional[float] = None

@app.get("/api/instances/{instance_id}/settings")
def get_instance_settings(instance_id: str):
    eng = _get_instance_or_404(instance_id)
    return eng.get_settings()

@app.post("/api/instances/{instance_id}/settings")
def update_instance_settings(instance_id: str, req: InstanceSettingsRequest):
    eng = _get_instance_or_404(instance_id)
    # Only include fields that were actually sent (exclude_unset)
    data = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else {k: v for k, v in req.dict().items() if v is not None}
    # Also handle legacy keys if any
    if not data:
        raise HTTPException(status_code=400, detail="No settings fields provided")
    res = eng.update_settings(data)
    return res

@app.post("/api/instances/{instance_id}/tap")
def tap_instance(instance_id: str, req: TapRequest):
    eng = _get_instance_or_404(instance_id)
    try:
        safe_device_tap(eng.device_ip, eng.device_port, req.x, req.y)
        return {"success": True, "x": req.x, "y": req.y, "instance_id": instance_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/instances/{instance_id}/test-connection")
def test_instance_connection(instance_id: str):
    eng = _get_instance_or_404(instance_id)
    success, msg = device_check_connection(eng.device_ip, eng.device_port)
    return {"success": success, "message": msg, "adb_path": get_adb_path(), "instance_id": instance_id}

@app.post("/api/instances/{instance_id}/reset-app")
def reset_instance_app(instance_id: str):
    eng = _get_instance_or_404(instance_id)
    try:
        device_reset_app(eng.device_ip, eng.device_port)
        return {"success": True, "message": "App reset command executed", "instance_id": instance_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/instances/{instance_id}/send-hearts-now")
def send_hearts_now(instance_id: str):
    eng = _get_instance_or_404(instance_id)
    # กันกดรัว — ถ้ากำลังส่งอยู่ให้บอกก่อน
    if getattr(eng, "_sending_hearts", False):
        return {"success": False, "message": "กำลังส่งหัวใจอยู่แล้ว กรุณารอสักครู่"}
    import threading
    # ตั้ง flag ก่อน start thread ทันที — กัน main loop ปิด popup เมล์ระหว่าง race window
    # popup จะอยู่จนกว่า handle_quick_receive_and_send_lives() จะ return เท่านั้น (callback flag)
    eng._sending_hearts = True
    def _do_send():
        try:
            eng.log("💖 [Manual] ผู้ใช้กดส่งหัวใจทันที — กำลังเปิดกล่องจดหมาย...", "info")
            from actions import handle_quick_receive_and_send_lives
            handle_quick_receive_and_send_lives(eng.device_ip, eng.device_port)
            eng.log("✅ [Manual] ส่งหัวใจทันทีเสร็จแล้ว", "success")
        except Exception as e:
            eng.log(f"❌ [Manual] ส่งหัวใจล้มเหลว: {e}", "error")
        finally:
            eng._sending_hearts = False
    t = threading.Thread(target=_do_send, daemon=True, name=f"SendHeartsNow-{instance_id}")
    t.start()
    return {"success": True, "message": "เริ่มส่งหัวใจทันทีแล้ว — ดู Logs ด้านล่าง", "instance_id": instance_id}

@app.get("/api/instances/{instance_id}/stream")
def instance_video_feed(instance_id: str):
    eng = _get_instance_or_404(instance_id)
    def frame_generator():
        last_idle_capture = 0
        while True:
            frame_bytes = None
            if eng.is_running and eng.latest_frame_jpeg is not None:
                frame_bytes = eng.latest_frame_jpeg
            else:
                now = time.time()
                if now - last_idle_capture > 1.5:
                    last_idle_capture = now
                    try:
                        screen = device_capture_screen(eng.device_ip, eng.device_port)
                        eng.update_frame(screen)
                        frame_bytes = eng.latest_frame_jpeg
                    except Exception:
                        pass
                if frame_bytes is None:
                    frame_bytes = eng.latest_frame_jpeg or generate_placeholder_frame(f"{eng.device_name} — Idle")

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            time.sleep(0.1)

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/instances/{instance_id}/screenshot")
def instance_screenshot(instance_id: str):
    eng = _get_instance_or_404(instance_id)
    try:
        screen = device_capture_screen(eng.device_ip, eng.device_port)
        _, buffer = cv2.imencode(".png", screen)
        return Response(content=buffer.tobytes(), media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/instances/{instance_id}/round-screenshot/{round_num}")
def instance_round_screenshot(instance_id: str, round_num: int):
    eng = _get_instance_or_404(instance_id)
    jpeg_bytes = eng.round_screenshots.get(round_num)
    if jpeg_bytes is not None:
        return Response(content=jpeg_bytes, media_type="image/jpeg")
    blank = np.zeros((480, 854, 3), dtype=np.uint8)
    blank[:] = (10, 10, 10)
    cv2.putText(blank, f"No screenshot for Round #{round_num} [{instance_id}]", (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 220, 232), 2, cv2.LINE_AA)
    _, buf = cv2.imencode(".jpg", blank)
    return Response(content=buf.tobytes(), media_type="image/jpeg")

@app.websocket("/ws/logs/{instance_id}")
async def websocket_logs_instance(websocket: WebSocket, instance_id: str):
    eng = _get_instance_or_404(instance_id)
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    eng.ws_subscribers.append(queue)
    try:
        for log_entry in list(eng.logs):
            await websocket.send_json(log_entry)
        while True:
            log_entry = await queue.get()
            await websocket.send_json(log_entry)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        if queue in eng.ws_subscribers:
            eng.ws_subscribers.remove(queue)


@app.get("/", response_class=HTMLResponse)
def get_index():
    index_path = os.path.join(os.path.dirname(__file__), "web", "index.html")
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Web Dashboard UI file not found in web/index.html</h1>"
