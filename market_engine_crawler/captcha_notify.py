"""
CAPTCHA handler for unattended crawler runs.

Strategy:
    1. On CAPTCHA detection, send an email with screenshot.
    2. Wait `WAIT_SECONDS` (default 180) — if user is around, they SSH into the
       Mac and solve it. Crawler then resumes automatically.
    3. If not solved by then, abandon the current target and continue to the
       next one. The item stays in queue / will be retried next cron tick.

Env vars required:
    CRAWLER_NOTIFY_EMAIL_TO     — destination address (your inbox)
    CRAWLER_NOTIFY_EMAIL_FROM   — sender (must match SMTP login)
    CRAWLER_NOTIFY_SMTP_HOST    — e.g. smtp.gmail.com
    CRAWLER_NOTIFY_SMTP_PORT    — 587
    CRAWLER_NOTIFY_SMTP_USER    — SMTP username
    CRAWLER_NOTIFY_SMTP_PASS    — app password (Gmail: create App Password)

Falls back to console-only logging if any env var is missing.
"""
from __future__ import annotations

import asyncio
import os
import smtplib
import socket
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

DEFAULT_WAIT_SECONDS = int(os.getenv("CRAWLER_CAPTCHA_WAIT", "180"))


def _smtp_configured() -> bool:
    keys = ("CRAWLER_NOTIFY_EMAIL_TO", "CRAWLER_NOTIFY_SMTP_HOST",
            "CRAWLER_NOTIFY_SMTP_USER", "CRAWLER_NOTIFY_SMTP_PASS")
    return all(os.getenv(k) for k in keys)


def send_captcha_email(*, job: str, url: str, screenshot_path: str | None) -> bool:
    if not _smtp_configured():
        print("[captcha_notify] SMTP not configured — skipping email")
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = f"[Etsy crawler] CAPTCHA on {job} @ {socket.gethostname()}"
        msg["From"] = os.getenv("CRAWLER_NOTIFY_EMAIL_FROM") or os.getenv("CRAWLER_NOTIFY_SMTP_USER")
        msg["To"] = os.getenv("CRAWLER_NOTIFY_EMAIL_TO")
        body = (
            f"Job: {job}\n"
            f"Host: {socket.gethostname()}\n"
            f"Time: {datetime.now().isoformat(timespec='seconds')}\n"
            f"URL:  {url}\n\n"
            f"SSH vào máy crawler để giải CAPTCHA, hoặc bỏ qua "
            f"— crawler sẽ tự skip sau {DEFAULT_WAIT_SECONDS}s.\n"
        )
        msg.set_content(body)
        if screenshot_path and Path(screenshot_path).exists():
            data = Path(screenshot_path).read_bytes()
            msg.add_attachment(data, maintype="image", subtype="png", filename="captcha.png")

        host = os.getenv("CRAWLER_NOTIFY_SMTP_HOST")
        port = int(os.getenv("CRAWLER_NOTIFY_SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls()
            s.login(os.getenv("CRAWLER_NOTIFY_SMTP_USER"), os.getenv("CRAWLER_NOTIFY_SMTP_PASS"))
            s.send_message(msg)
        print(f"[captcha_notify] email sent to {os.getenv('CRAWLER_NOTIFY_EMAIL_TO')}")
        return True
    except Exception as e:
        print(f"[captcha_notify] email failed: {e}")
        return False


async def wait_for_captcha_clear(page, *, job: str, wait_seconds: int = DEFAULT_WAIT_SECONDS) -> bool:
    """Poll page until CAPTCHA banner disappears or timeout. Returns True if
    cleared, False if timed out (caller should skip current target)."""
    deadline = asyncio.get_event_loop().time() + wait_seconds
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(5)
        try:
            content = (await page.content()).lower()
            if "captcha" not in content and "are you a human" not in content:
                print("[captcha_notify] CAPTCHA appears cleared")
                return True
        except Exception:
            pass
    print(f"[captcha_notify] timeout {wait_seconds}s — skipping target")
    return False


async def handle_captcha(page, job: str) -> bool:
    """Centralized CAPTCHA handler. Emails, waits, returns True if resolved."""
    screenshot = f"/tmp/captcha-{job}-{int(asyncio.get_event_loop().time())}.png"
    try:
        await page.screenshot(path=screenshot, full_page=False)
    except Exception:
        screenshot = None
    send_captcha_email(job=job, url=page.url, screenshot_path=screenshot)
    return await wait_for_captcha_clear(page, job=job)
