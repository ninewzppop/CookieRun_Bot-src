# -*- coding: utf-8 -*-
"""
install.py — ติดตั้ง dependencies แบบสวยๆ สำหรับ CookieRun Bot
- แสดง banner ทอง-ดำ
- progress bar / spinner ต่อ package (ใช้ rich ถ้ามี, fallback tqdm/text)
- สรุปท้าย + เวลา + ✅ พร้อมใช้งาน

เรียกใช้:
  python install.py
  python -m install
  หรือจาก INSTALL.bat (Windows) / ./INSTALL.sh (macOS/Linux)
"""
from __future__ import annotations

import os
import sys
import time
import subprocess
import shutil

# Ensure UTF-8 on Windows
if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr is not None:
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ui_console อาจยังไม่มี colorama/rich ตอนเริ่ม — import แบบยืดหยุ่น
try:
    import ui_console  # type: ignore

    HAS_UI = True
except ImportError:
    HAS_UI = False
    ui_console = None  # type: ignore

# ลอง import rich แยก (ถ้ายังไม่ได้ลง ก็จะ fallback)
_HAS_RICH = False
try:
    from rich.console import Console  # type: ignore

    _HAS_RICH = True
except ImportError:
    pass

_HAS_TQDM = False
try:
    from tqdm import tqdm  # type: ignore

    _HAS_TQDM = True
except ImportError:
    pass


def _print_banner_fallback():
    print("=" * 62)
    print("  CookieRun Classic Bot - Installing Dependencies...")
    print("=" * 62)


def _run_pip_install(requirements_path: str) -> tuple[bool, str, float, int]:
    """ติดตั้งแบบมี progress สวยๆ — คืน (success, log, elapsed, count)."""
    start = time.time()

    # อ่านรายการ package เพื่อนับจำนวน
    pkgs: list[str] = []
    if HAS_UI and ui_console is not None:
        try:
            pkgs = ui_console.get_install_packages(requirements_path)  # type: ignore
        except Exception:
            pkgs = []
    else:
        try:
            with open(requirements_path, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if s and not s.startswith("#"):
                        pkgs.append(s)
        except FileNotFoundError:
            pass

    total = len(pkgs) if pkgs else 0

    # เตรียม progress
    progress = None
    if HAS_UI and ui_console is not None and total > 0:
        try:
            progress = ui_console.InstallProgress(total)  # type: ignore
        except Exception:
            progress = None

    # ใช้ pip install แบบเงียบ แล้วเราทำ progress เองแบบ simulate ต่อ package
    # ทางเลือกที่สวยกว่า: รัน pip install ทีละ package เพื่อให้เห็น progress จริง
    # แต่จะช้ากว่า — เราเลยรัน pip install รวมทีเดียวแล้วทำ spinner ระหว่างรอ
    # ถ้าต้องการ progress ต่อ package จริงๆ ให้ใช้ per-package loop ด้านล่าง (เปิดได้)

    # เลือกโหมด: per-package เพื่อให้เห็นชื่อแต่ละตัว (สวยกว่า)
    per_package = True  # ตั้ง False ถ้าอยากเร็วแบบรวมทีเดียว

    success = True
    log_lines: list[str] = []
    installed = 0
    failed: list[str] = []

    python_exe = sys.executable or "python"

    if per_package and total > 0:
        # อัปเกรด pip ก่อน (เงียบ)
        if HAS_UI and ui_console is not None:
            try:
                ui_console.print_info("Upgrading pip...")
            except Exception:
                print("Upgrading pip...")
        try:
            subprocess.run(
                [python_exe, "-m", "pip", "install", "--upgrade", "pip"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
        except Exception:
            pass

        for idx, pkg in enumerate(pkgs, 1):
            desc = pkg.split(";")[0].strip()
            # ตัด version spec ให้สั้น
            short = desc.split("==")[0].split(">=")[0].split("~=")[0].strip()
            if HAS_UI and ui_console is not None and progress is not None:
                try:
                    # จะ advance หลังติดตั้งเสร็จ — ระหว่างรอให้ spinner หมุน
                    pass
                except Exception:
                    pass

            # แสดงว่ากำลังติดตัวไหน (ถ้าไม่มี rich progress ก็ print เอง)
            if progress is None:
                if HAS_UI and ui_console is not None:
                    try:
                        ui_console.print_info(f"Installing [{idx}/{total}] {desc} ...")
                    except Exception:
                        print(f"[{idx}/{total}] Installing {desc} ...")
                else:
                    print(f"[{idx}/{total}] Installing {desc} ...")

            try:
                result = subprocess.run(
                    [python_exe, "-m", "pip", "install", desc, "--quiet", "--disable-pip-version-check"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=180,
                )
                out = (result.stdout or "") + (result.stderr or "")
                if result.returncode == 0:
                    installed += 1
                    log_lines.append(f"OK {desc}")
                    if progress is not None:
                        try:
                            progress.advance(f"[green]✓[/] {short}")
                        except Exception:
                            pass
                else:
                    success = False
                    failed.append(desc)
                    log_lines.append(f"FAIL {desc}: {out.strip()[:300]}")
                    if progress is not None:
                        try:
                            progress.advance(f"[red]✗[/] {short}")
                        except Exception:
                            pass
                    # แสดง error ทันที
                    if HAS_UI and ui_console is not None:
                        try:
                            ui_console.print_error(f"Failed {desc}: {out.strip().splitlines()[-1][:120] if out.strip() else 'unknown'}")
                        except Exception:
                            print(f"  Failed {desc}")
                    else:
                        print(f"  Failed {desc}: {out.strip()[:200]}")
            except subprocess.TimeoutExpired:
                success = False
                failed.append(desc)
                log_lines.append(f"TIMEOUT {desc}")
                if progress is not None:
                    try:
                        progress.advance(f"[red]✗ timeout[/] {short}")
                    except Exception:
                        pass
            except Exception as e:
                success = False
                failed.append(desc)
                log_lines.append(f"EXC {desc}: {e}")
                if progress is not None:
                    try:
                        progress.advance(f"[red]✗ error[/] {short}")
                    except Exception:
                        pass
        if progress is not None:
            try:
                progress.stop()
            except Exception:
                pass
    else:
        # โหมดเร็ว: pip install -r requirements.txt ทีเดียว + spinner
        spinner_desc = "Installing dependencies..."
        # ถ้ามี rich ให้ใช้ Progress spinner ระหว่างรัน pip
        rich_progress = None
        task_id = None
        if _HAS_RICH and sys.stdout.isatty():
            try:
                from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn  # type: ignore

                rich_progress = Progress(SpinnerColumn(spinner_style="yellow"), TextColumn("[yellow]{task.description}[/]"), TimeElapsedColumn())
                rich_progress.start()
                task_id = rich_progress.add_task(spinner_desc, total=None)
            except Exception:
                rich_progress = None

        # อัปเกรด pip
        try:
            subprocess.run([python_exe, "-m", "pip", "install", "--upgrade", "pip"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        except Exception:
            pass

        cmd = [python_exe, "-m", "pip", "install", "-r", requirements_path, "--disable-pip-version-check"]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600)
            out = (result.stdout or "") + (result.stderr or "")
            log_lines.append(out[-2000:])
            if result.returncode == 0:
                installed = total or 1
                success = True
            else:
                success = False
                log_lines.append(f"pip exit {result.returncode}")
        except Exception as e:
            success = False
            log_lines.append(str(e))
        finally:
            if rich_progress is not None:
                try:
                    rich_progress.stop()
                except Exception:
                    pass
        if progress is not None:
            try:
                for _ in pkgs:
                    progress.advance("done")
                progress.stop()
            except Exception:
                pass

    elapsed = time.time() - start
    log_text = "\n".join(log_lines)
    if failed:
        log_text += "\nFailed: " + ", ".join(failed)
    return success, log_text, elapsed, installed


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    requirements_path = os.path.join(here, "requirements.txt")

    # Banner
    if HAS_UI and ui_console is not None:
        try:
            ui_console.ensure_utf8_stdout()
            ui_console.print_banner(subtitle="Installer", version="v2.0")
            print()
            ui_console.print_info(f"Python: {sys.version.split()[0]}  |  {sys.executable}")
            ui_console.print_info(f"Requirements: {requirements_path}")
            ui_console.print_divider("-", 62, "GRAY")
        except Exception:
            _print_banner_fallback()
    else:
        _print_banner_fallback()
        print(f"Python: {sys.version}")
        print(f"Requirements: {requirements_path}")

    if not os.path.isfile(requirements_path):
        msg = f"ไม่พบไฟล์ requirements.txt ที่ {requirements_path}"
        if HAS_UI and ui_console is not None:
            try:
                ui_console.print_error_box("Requirements not found", msg, "ตรวจสอบว่าไฟล์อยู่ในโฟลเดอร์ src/")
            except Exception:
                print(f"[ERROR] {msg}")
        else:
            print(f"[ERROR] {msg}")
        return 1

    # เช็ค pip มีไหม
    if shutil.which("pip") is None and shutil.which("pip3") is None:
        # ยังพอใช้ python -m pip ได้
        pass

    print()
    success, log_text, elapsed, installed = _run_pip_install(requirements_path)
    print()

    # สรุป
    elapsed_str = f"{elapsed:.1f}s"
    if elapsed >= 60:
        m, s = divmod(int(elapsed), 60)
        elapsed_str = f"{m}m {s}s ({elapsed:.1f}s)"

    if HAS_UI and ui_console is not None:
        try:
            if success:
                pkgs = ui_console.get_install_packages(requirements_path)
                total = len(pkgs)
                details = f"Installed {installed}/{total} packages\nElapsed: {elapsed_str}\n\n{ui_console.c_green('พร้อมใช้งานแล้ว!')}  Run START_BOT.bat / python run_web.py เพื่อเริ่ม Dashboard"
                # ใช้กล่องเขียว
                ui_console.print_success_box("✅ Installation completed!", details)
                # บรรทัดสรุปสีเขียวเด่น
                print()
                print(ui_console.c_green(f"✅ พร้อมใช้งานแล้ว!  ( {installed}/{total} packages, {elapsed_str} )"))
                print(ui_console.c_gray(f"   Next: python run_web.py  หรือดับเบิลคลิก START_BOT.bat"))
            else:
                details = f"Installed {installed} packages, some failed.\nElapsed: {elapsed_str}\n\n{log_text[-800:]}"
                ui_console.print_error_box("Installation failed", details, "ตรวจสอบว่า Python 3.10+ และ internet ปกติ แล้วลองใหม่")
                print()
                print(ui_console.c_red(f"✗ Installation failed  ({elapsed_str})"))
            ui_console.print_divider("-", 62, "GRAY")
        except Exception:
            # fallback plain
            if success:
                print("=" * 62)
                print(f"  [SUCCESS] Installation completed! ({installed} packages, {elapsed_str})")
                print("  You can now start the bot using 'START_BOT.bat' or 'python run_web.py'.")
                print("=" * 62)
            else:
                print("=" * 62)
                print(f"  [ERROR] Installation failed. ({elapsed_str})")
                print(f"  {log_text[-500:]}")
                print("=" * 62)
    else:
        if success:
            print("=" * 62)
            print(f"  [SUCCESS] Installation completed! ({installed} packages, {elapsed_str})")
            print("  You can now start the bot using 'START_BOT.bat' or 'python run_web.py'.")
            print("=" * 62)
        else:
            print("=" * 62)
            print(f"  [ERROR] Installation failed. ({elapsed_str})")
            print(f"  {log_text[-800:]}")
            print("=" * 62)

    # ให้ caller เช็ค exit code ได้ (bat จะดู ERRORLEVEL)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
