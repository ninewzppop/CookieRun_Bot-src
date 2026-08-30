# -*- coding: utf-8 -*-
"""
ui_console.py — สวยๆ Terminal helper สำหรับ CookieRun Bot

- ANSI colors + colorama (fallback ถ้าไม่มี หรือ terminal ไม่รองรับสี)
- โทนทอง-ดำ (YELLOW/GOLD) + เขียว/แดง/ฟ้า
- ASCII banner ขนาดกระทัดรัด (8 lines)
- Rich panels/tables ถ้ามี library `rich` (fallback เป็นกล่อง ASCII ธรรมดา)
- Spinner/progress สำหรับตอนติดตั้ง

ใช้ร่วมกันได้ทั้ง install.py และ run_web.py
"""
from __future__ import annotations

import os
import sys
import time
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Color init — พยายามใช้ colorama ถ้ามี (ช่วยให้ Windows cmd เก่าแสดงสีถูก)
# ---------------------------------------------------------------------------
_COLORAMA_OK = False
try:
    import colorama  # type: ignore

    colorama.just_fix_windows_console()
    # init จะ wrap stdout/stderr ให้แปลง ANSI -> Win32 API ถ้าจำเป็น
    try:
        colorama.init(autoreset=True)
        _COLORAMA_OK = True
    except Exception:
        pass
except ImportError:
    pass

# ลอง import rich ถ้ามี — ใช้ทำ Panel/Table/Progress สวยๆ
_RICH_OK = False
try:
    from rich.console import Console as _RichConsole  # type: ignore
    from rich.panel import Panel as _RichPanel  # type: ignore
    from rich.table import Table as _RichTable  # type: ignore
    from rich.text import Text as _RichText  # type: ignore
    from rich.progress import (  # type: ignore
        Progress as _RichProgress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeElapsedColumn,
    )
    _RICH_OK = True
except ImportError:
    _RichConsole = None  # type: ignore
    _RichPanel = None  # type: ignore
    _RichTable = None  # type: ignore

# ---------------------------------------------------------------------------
# ตรวจสอบว่า terminal รองรับสีไหม (pipe ไปไฟล์ -> ปิดสี)
# ---------------------------------------------------------------------------
def _supports_color() -> bool:
    # NO_COLOR env หรือถูก pipe -> ไม่ใช้สี
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    # ถ้า stdout ไม่ใช่ tty (ถูก pipe) -> ปิดสี
    try:
        if not sys.stdout.isatty():
            # แต่ถ้า rich รองรับ หรือ colorama เปิดอยู่ บน CI บางกรณีก็ควรปิดอยู่ดี
            return False
    except Exception:
        return False
    return True


_USE_COLOR = _supports_color()

# ANSI codes (fallback ถ้าไม่มี colorama)
_ANSI = {
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
    "GOLD": "\033[33m",      # yellow/gold — ธีมหลัก
    "YELLOW": "\033[33m",
    "GOLD_BOLD": "\033[1;33m",
    "GREEN": "\033[32m",
    "GREEN_BOLD": "\033[1;32m",
    "RED": "\033[31m",
    "RED_BOLD": "\033[1;31m",
    "CYAN": "\033[36m",
    "CYAN_BOLD": "\033[1;36m",
    "WHITE": "\033[37m",
    "WHITE_BOLD": "\033[1;37m",
    "GRAY": "\033[90m",
    "BG_GOLD": "\033[43m",
    "BG_RED": "\033[41m",
}

# ถ้ามี colorama ให้ใช้ค่าจาก colorama แทน (แม่นกว่า)
try:
    if _COLORAMA_OK:
        from colorama import Fore, Style  # type: ignore

        _ANSI.update(
            {
                "RESET": Style.RESET_ALL,
                "BOLD": Style.BRIGHT,
                "DIM": Style.DIM,
                "GOLD": Fore.YELLOW,
                "YELLOW": Fore.YELLOW,
                "GOLD_BOLD": Style.BRIGHT + Fore.YELLOW,
                "GREEN": Fore.GREEN,
                "GREEN_BOLD": Style.BRIGHT + Fore.GREEN,
                "RED": Fore.RED,
                "RED_BOLD": Style.BRIGHT + Fore.RED,
                "CYAN": Fore.CYAN,
                "CYAN_BOLD": Style.BRIGHT + Fore.CYAN,
                "WHITE": Fore.WHITE,
                "WHITE_BOLD": Style.BRIGHT + Fore.WHITE,
                "GRAY": Fore.LIGHTBLACK_EX,
            }
        )
except Exception:
    pass


def _c(text: str, color_key: str) -> str:
    """ใส่สีให้ text ถ้า terminal รองรับ, ไม่งั้นคืน text เปล่าๆ."""
    if not _USE_COLOR or not sys.stdout.isatty():
        # เช็คซ้ำแบบ runtime เผื่อถูก pipe ระหว่างรัน
        # ถ้า NO_COLOR ก็ปิด
        if os.environ.get("NO_COLOR"):
            return text
        # ถ้าไม่ใช่ tty จริงๆ ก็ปิด
        try:
            if not sys.stdout.isatty():
                return text
        except Exception:
            pass
        # ถ้ายังอยากให้มีสีในกรณีที่ rich handle ได้ ก็ให้ผ่านได้ แต่ default ปิด
        # ตรงนี้ปิดเพื่อกัน garbled
        return text
    code = _ANSI.get(color_key, "")
    reset = _ANSI["RESET"]
    return f"{code}{text}{reset}"


def c_gold(text: str) -> str:
    return _c(text, "GOLD_BOLD")


def c_green(text: str) -> str:
    return _c(text, "GREEN_BOLD")


def c_red(text: str) -> str:
    return _c(text, "RED_BOLD")


def c_cyan(text: str) -> str:
    return _c(text, "CYAN")


def c_gray(text: str) -> str:
    return _c(text, "GRAY")


def c_white(text: str) -> str:
    return _c(text, "WHITE_BOLD")


def c_dim(text: str) -> str:
    return _c(text, "DIM")


# ---------------------------------------------------------------------------
# ASCII banner — NINEWZ โทนทอง-ดำ (generate via pyfiglet)
# ---------------------------------------------------------------------------
# Subtitle lines คงเดิมตามสเปค — เปลี่ยนแค่โลโก้ตรงกลางจาก CookieRun Bot → NINEWZ
_SUBTITLE_LINES: List[str] = [
    "Classic Bot  •  Web Dashboard  v2.0",
    "Gold x Black  •  CookieRun Farm Bot",
]

def _build_banner_lines() -> List[str]:
    """สร้าง BANNER_LINES จาก pyfiglet 'NINEWZ' ถ้าทำได้, ไม่งั้น fallback — จัดกึ่งกลางในกรอบ"""
    figlet_lines: List[str] = []
    try:
        import pyfiglet  # type: ignore

        # ลองตามลำดับ: standard → small → slant (เลือกตัวที่กว้างไม่เกิน 60)
        for font in ("standard", "small", "slant"):
            try:
                raw = pyfiglet.figlet_format("NINEWZ", font=font)
                # pyfiglet คืน string มี \n ต่อท้าย, split และริด trailing spaces ออกแต่คง leading
                lines = [ln.rstrip() for ln in raw.rstrip("\n").splitlines()]
                # ตัดบรรทัดว่างท้ายที่ pyfiglet บาง font แถมมา
                while lines and lines[-1].strip() == "":
                    lines.pop()
                w = max(len(ln) for ln in lines) if lines else 0
                if w <= 60 and len(lines) <= 8:
                    figlet_lines = lines
                    break
                # ถ้ากว้างเกิน ลอง font ถัดไปที่แคบกว่า
                if not figlet_lines:
                    figlet_lines = lines
            except Exception:
                continue
    except ImportError:
        pass

    if not figlet_lines:
        # fallback แบบเดิมถ้าไม่มี pyfiglet
        figlet_lines = [
            r" _   _ ___ _   _ _______        _______",
            r"| \ | |_ _| \ | | ____\ \      / /__  /",
            r"|  \| || ||  \| |  _|  \ \ /\ / /  / / ",
            r"| |\  || || |\  | |___  \ V  V /  / /_ ",
            r"|_| \_|___|_| \_|_____|  \_/\_/  /____|",
        ]

    # จัดกึ่งกลางทั้ง figlet และ subtitle ให้อยู่กึ่งกลางกรอบเดียวกัน
    combined = figlet_lines + [""] + _SUBTITLE_LINES
    max_w = max(len(ln) for ln in combined) if combined else 0
    centered_figlet = [ln.center(max_w) for ln in figlet_lines]
    centered_sub = [ln.center(max_w) for ln in _SUBTITLE_LINES]
    return centered_figlet + ["".center(max_w)] + centered_sub


BANNER_LINES: List[str] = _build_banner_lines()


def get_banner_text() -> str:
    return "\n".join(BANNER_LINES)


def print_banner(subtitle: str = "Web Dashboard", version: str = "v2.0") -> None:
    """พิมพ์ banner สีทอง + เส้นขอบ."""
    # ใช้ rich Panel ถ้ามี
    if _RICH_OK and _USE_COLOR:
        try:
            console = _RichConsole()
            banner = "\n".join(BANNER_LINES)
            text = _RichText(banner, style="bold yellow", justify="center")
            console.print(_RichPanel(text, border_style="yellow", padding=(0, 2), title=f"[bold yellow]{subtitle}[/] {version}", title_align="center"))
            return
        except Exception:
            pass

    # fallback: ANSI manual — จัดกึ่งกลางในกรอบ
    width = max(len(line) for line in BANNER_LINES) + 4
    border = "+" + "-" * width + "+"
    # สีทองสำหรับ border
    print(c_gold(border))
    for line in BANNER_LINES:
        padded = line.center(width - 2)
        print(c_gold("| ") + c_gold(padded) + c_gold(" |"))
    print(c_gold(border))
    # subtitle ใต้ banner
    if subtitle or version:
        print(c_gray(f"  {subtitle} {version}".center(width + 2)))


def print_divider(char: str = "-", width: int = 60, color: str = "GOLD") -> None:
    line = char * width
    if color == "GOLD":
        print(c_gold(line))
    elif color == "GRAY":
        print(c_gray(line))
    else:
        print(line)


# ---------------------------------------------------------------------------
# Info / Success / Warning / Error — helpers
# ---------------------------------------------------------------------------
def print_info(msg: str) -> None:
    prefix = c_cyan("  [i]") if _USE_COLOR else "  [i]"
    print(f"{prefix} {msg}")


def print_success(msg: str) -> None:
    prefix = c_green("  [✓]") if _USE_COLOR else "  [OK]"
    # ข้อความสีเขียวถ้ารองรับ
    body = c_green(msg) if _USE_COLOR else msg
    print(f"{prefix} {body}")


def print_warning(msg: str) -> None:
    prefix = c_gold("  [!]") if _USE_COLOR else "  [!]"
    body = c_gold(msg) if _USE_COLOR else msg
    print(f"{prefix} {body}")


def print_error(msg: str) -> None:
    prefix = c_red("  [✗]") if _USE_COLOR else "  [ERR]"
    body = c_red(msg) if _USE_COLOR else msg
    print(f"{prefix} {body}")


def print_error_box(title: str, details: str = "", hint: str = "") -> None:
    """กรอบ error สีแดงเด่นชัด — ใช้ rich Panel ถ้ามี."""
    if _RICH_OK and _USE_COLOR:
        try:
            console = _RichConsole(stderr=True)
            body = details
            if hint:
                body += f"\n\n[dim]{hint}[/dim]"
            console.print(_RichPanel(body, title=f"[bold red]{title}[/]", border_style="red", padding=(1, 2)))
            return
        except Exception:
            pass
    # fallback ASCII box สีแดง
    import textwrap

    width = 62
    print(c_red("+" + "=" * width + "+"))
    print(c_red(f"|  {title}".ljust(width + 1) + "|"))
    print(c_red("+" + "-" * width + "+"))
    if details:
        for line in details.split("\n"):
            if not line.strip():
                print(c_red("|  ") + " " * (width - 4) + c_red("  |"))
                continue
            wrapped = textwrap.wrap(line, width=width - 4, break_long_words=False, break_on_hyphens=False) or [""]
            for w in wrapped:
                print(c_red("|  ") + w.ljust(width - 4) + c_red("  |"))
    if hint:
        print(c_red("+" + "-" * width + "+"))
        hint_line = f"Hint: {hint}"
        wrapped_hint = textwrap.wrap(hint_line, width=width - 4, break_long_words=False, break_on_hyphens=False) or [hint_line]
        for w in wrapped_hint:
            print(c_gray("|  ") + w.ljust(width - 4) + c_gray("  |"))
    print(c_red("+" + "=" * width + "+"))


def print_success_box(title: str, details: str = "") -> None:
    if _RICH_OK and _USE_COLOR:
        try:
            console = _RichConsole()
            console.print(_RichPanel(details, title=f"[bold green]{title}[/]", border_style="green", padding=(1, 2)))
            return
        except Exception:
            pass
    import textwrap

    width = 62
    print(c_green("+" + "=" * width + "+"))
    print(c_green(f"|  {title}".ljust(width + 1) + "|"))
    print(c_green("+" + "-" * width + "+"))
    if details:
        for line in details.split("\n"):
            if not line.strip():
                print(c_green("|  ") + " " * (width - 4) + c_green("  |"))
                continue
            wrapped = textwrap.wrap(line, width=width - 4, break_long_words=False, break_on_hyphens=False) or [""]
            for w in wrapped:
                print(c_green("|  ") + w.ljust(width - 4) + c_green("  |"))
    print(c_green("+" + "=" * width + "+"))


# ---------------------------------------------------------------------------
# Info panel สำหรับ run_web.py — แสดง URL / ADB / instance / version
# ---------------------------------------------------------------------------
def print_dashboard_info(
    port: int,
    adb_path: str,
    version: str = "v2.0",
    instances: Optional[List[Dict]] = None,
    lan_ip: str = "",
) -> None:
    """แสดงกล่องข้อมูลสำคัญตอนเริ่ม Web Dashboard."""
    import socket as _socket

    # หา LAN IP ถ้าไม่ได้ส่งมา
    if not lan_ip:
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
            s.close()
        except Exception:
            lan_ip = "—"

    local_url = f"http://127.0.0.1:{port}"
    lan_url = f"http://{lan_ip}:{port}" if lan_ip != "—" else "—"

    # นับ instance
    inst_count = len(instances) if instances is not None else 0
    # ADB status
    adb_ok = bool(adb_path and adb_path != "adb" and os.path.isfile(adb_path)) or adb_path != "adb"
    adb_display = adb_path if adb_path else "not found"
    # ตัดให้สั้นถ้ายาว
    if len(adb_display) > 48:
        adb_display = "..." + adb_display[-45:]

    if _RICH_OK and _USE_COLOR:
        try:
            console = _RichConsole()
            # สร้างตารางข้อมูล
            table = _RichTable(show_header=False, box=None, padding=(0, 1))
            table.add_column("key", style="bold yellow", no_wrap=True)
            table.add_column("val", style="white")

            # ใช้สัญลักษณ์สวยๆ
            table.add_row("⚡ Version", version)
            table.add_row("🍪 Dashboard", f"[cyan]{local_url}[/]  [dim](LAN: {lan_url})[/]")
            table.add_row("🔧 ADB Path", f"{'[green]✓[/]' if adb_ok else '[red]✗[/]'} {adb_display}")
            table.add_row("📱 Instances", str(inst_count) + ("  [green]ready[/]" if inst_count else "  [yellow]0 — add via web[/]"))
            table.add_row("📡 Host", f"0.0.0.0:{port}  [dim](press Ctrl+C to stop)[/]")

            console.print(_RichPanel(table, title="[bold yellow]CookieRun Bot — Dashboard Info[/]", border_style="yellow", padding=(1, 2)))

            # คำแนะนำสั้นๆ ใต้กล่อง
            console.print("[dim]  Tip: เปิดบนมือถือผ่าน Wi-Fi เดียวกันด้วย LAN URL ด้านบน  •  ดู logs แบบ live ที่หน้าเว็บ[/dim]")
            return
        except Exception:
            pass

    # fallback — กล่อง ASCII ธรรมดา
    width = 64
    print(c_gold("+" + "=" * width + "+"))
    print(c_gold("|") + c_white("  🍪  CookieRun Bot — Dashboard Info".ljust(width - 1)) + c_gold("|"))
    print(c_gold("+" + "-" * width + "+"))
    rows = [
        f"  ⚡ Version     : {version}",
        f"  🍪 Dashboard   : {local_url}",
        f"     LAN         : {lan_url}",
        f"  🔧 ADB Path    : {'✓ ' if adb_ok else '✗ '}{adb_display}",
        f"  📱 Instances   : {inst_count}",
        f"  📡 Host        : 0.0.0.0:{port}  (Ctrl+C to stop)",
    ]
    for r in rows:
        # ตัดถ้ายาวเกิน
        clipped = r[: width - 2] if len(r) > width - 2 else r
        print(c_gold("|") + clipped.ljust(width) + c_gold("|"))
    print(c_gold("+" + "=" * width + "+"))
    print(c_gray("  Tip: เปิดบนมือถือผ่าน Wi-Fi เดียวกันด้วย LAN URL ด้านบน"))


# ---------------------------------------------------------------------------
# Install progress helpers
# ---------------------------------------------------------------------------
def get_install_packages(requirements_path: str) -> List[str]:
    """อ่าน requirements.txt คืน list ของ package lines (ไม่เอา comment/ว่าง)."""
    pkgs: List[str] = []
    try:
        with open(requirements_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                pkgs.append(s)
    except FileNotFoundError:
        pass
    return pkgs


class InstallProgress:
    """Progress แบบ rich ถ้ามี, ไม่งั้น fallback เป็น spinner/text ธรรมดา."""

    def __init__(self, total: int):
        self.total = total
        self.current = 0
        self.start_time = time.time()
        self._rich_progress = None
        self._task_id = None
        self._use_rich = _RICH_OK and _USE_COLOR and sys.stdout.isatty()

        if self._use_rich:
            try:
                self._rich_progress = _RichProgress(
                    SpinnerColumn(spinner_style="yellow"),
                    TextColumn("[yellow]{task.description}[/]"),
                    BarColumn(bar_width=None, style="dim", complete_style="yellow"),
                    TaskProgressColumn(),
                    TimeElapsedColumn(),
                    transient=False,
                )
                self._rich_progress.start()
                self._task_id = self._rich_progress.add_task("Installing dependencies...", total=total)
            except Exception:
                self._rich_progress = None
                self._use_rich = False

    def advance(self, description: str = "") -> None:
        self.current += 1
        if self._rich_progress and self._task_id is not None:
            try:
                self._rich_progress.update(self._task_id, advance=1, description=description or f"Installing {self.current}/{self.total}")
                return
            except Exception:
                pass
        # fallback: พิมพ์บรรทัดสีเหลืองแบบเรียบๆ — ลอก rich markup ออกถ้าไม่ใช่ rich mode
        import re

        clean_desc = re.sub(r"\[.*?\]", "", description) if description else ""
        # แปลง [green]✓[/] ที่อาจหลุดมาให้เป็น ✓ เฉยๆ แล้ว (strip แล้ว)
        pct = int(self.current / max(1, self.total) * 100)
        bar_len = 24
        filled = int(bar_len * self.current / max(1, self.total))
        bar = "█" * filled + "░" * (bar_len - filled)
        # carriage return ให้ดูเป็น progress เดียว (ถ้า tty)
        try:
            if sys.stdout.isatty():
                sys.stdout.write(f"\r  {c_gold(bar)} {pct:3d}%  {clean_desc[:40]}")
                sys.stdout.flush()
                if self.current == self.total:
                    sys.stdout.write("\n")
            else:
                print(f"  [{self.current}/{self.total}] {clean_desc}")
        except Exception:
            print(f"  [{self.current}/{self.total}] {clean_desc}")

    def stop(self) -> None:
        if self._rich_progress:
            try:
                self._rich_progress.stop()
            except Exception:
                pass

    def elapsed(self) -> float:
        return time.time() - self.start_time


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def get_version(default: str = "v2.0") -> str:
    """ลองอ่าน version จาก web_server.py ถ้ามี."""
    try:
        # web_server.FastAPI version
        import web_server  # type: ignore

        v = getattr(web_server.app, "version", None)
        if v:
            return f"v{v}"
    except Exception:
        pass
    return default


def ensure_utf8_stdout() -> None:
    """บังคับ stdout เป็น UTF-8 (กัน garbled บน Windows)."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None:
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            except Exception:
                pass
