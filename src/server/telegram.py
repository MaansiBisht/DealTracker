"""Telegram delivery channel — Connect-button pairing, hidden chat_id.

Operator wires a bot once via @BotFather and drops the token in
TELEGRAM_BOT_TOKEN. Inbound updates (the user's "/start <token>" reply)
arrive via Telegram's webhook: on startup the app registers
`{APP_BASE_URL}/api/telegram/webhook` and Telegram POSTs each update to
that endpoint. No background thread, no polling.

Pairing model (per watch):
    1. UI hits POST /api/telegram/start-pairing → mints a one-time
       token, stores it in telegram_pairings.
    2. UI opens https://t.me/<bot_username>?start=<token>.
    3. User taps Start in Telegram → Telegram POSTs "/start <token>"
       to /api/telegram/webhook, which fills chat_id + display_name on
       the row and on the requesting User.
    4. UI polls /api/telegram/pairing/{token} every 2s, picks up the
       chat_id when it lands, submits the watch with it.

Tokens are invisible to the user — they just see a Connect button and
a "connected to <First Name>" confirmation.

Webhook auth: Telegram echoes a configured secret back on every POST
via the `X-Telegram-Bot-Api-Secret-Token` header (Bot API 6.0+). The
route verifies this header before invoking `handle_update`. The secret
lives in TELEGRAM_WEBHOOK_SECRET.

stdlib-only — uses urllib for outbound calls so we don't pull a new
runtime dep just for Telegram.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import delete

from .db import SessionLocal
from .models import TelegramPairing


log = logging.getLogger("dealtracker.telegram")

API_BASE = "https://api.telegram.org/bot{token}/{method}"
PAIR_TOKEN_BYTES = 12
START_RE = re.compile(r"^/start(?:@\w+)?\s+([A-Za-z0-9_-]{6,64})\s*$")

# In-memory dedupe of recently-seen update_ids. Telegram retries the same
# update if the webhook doesn't 2xx fast enough, so we silently drop replays.
# Bounded at 256 entries — Telegram's retry window is seconds, not hours.
_RECENT_UPDATE_IDS: deque[int] = deque(maxlen=256)


def _token() -> Optional[str]:
    t = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    return t or None


def is_configured() -> bool:
    return _token() is not None


def webhook_secret() -> Optional[str]:
    s = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    return s or None


def bot_username() -> Optional[str]:
    cached = getattr(bot_username, "_cached", None)
    if cached:
        return cached
    explicit = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
    if explicit:
        bot_username._cached = explicit  # type: ignore[attr-defined]
        return explicit
    if not is_configured():
        return None
    try:
        me = _call("getMe")
        username = me.get("result", {}).get("username")
        if username:
            bot_username._cached = username  # type: ignore[attr-defined]
            return username
    except Exception as e:
        log.warning("getMe failed: %s", e)
    return None


def _call(method: str, payload: dict[str, Any] | None = None, *, timeout: int = 10) -> dict[str, Any]:
    token = _token()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    url = API_BASE.format(token=token, method=method)
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {"ok": False, "description": f"HTTP {e.code}"}
    if not body.get("ok"):
        raise RuntimeError(f"telegram {method} failed: {body.get('description')}")
    return body


def send_message(chat_id: str, text: str, parse_mode: Optional[str] = "Markdown") -> None:
    """Send a chat message. Pass parse_mode='HTML' (or None for plain) when
    the body contains URLs or other content with Markdown-special characters
    that Telegram's strict parser would choke on.
    """
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    _call("sendMessage", payload)


# ---------- pairing -----------------------------------------------------------

def start_pairing(user_id: Optional[str] = None) -> dict[str, str]:
    """Mint a fresh pair token bound to the requesting user.

    `user_id` is optional only so legacy callers (and the auth-less unit
    tests of the pairing flow) keep working; routes always pass it.
    """
    if not is_configured():
        raise RuntimeError("Telegram bot not configured")

    token = secrets.token_urlsafe(PAIR_TOKEN_BYTES)
    with SessionLocal() as db:
        db.add(TelegramPairing(token=token, user_id=user_id))
        db.commit()

    username = bot_username() or "your_bot"
    return {
        "token": token,
        "deep_link": f"https://t.me/{username}?start={token}",
    }


def pairing_status(token: str) -> dict[str, Any]:
    """Polled by the UI — returns chat_id once the user has tapped Start."""
    with SessionLocal() as db:
        row = db.get(TelegramPairing, token)
        if row is None:
            return {"paired": False, "exists": False, "chat_id": None, "display_name": None}
        return {
            "paired": row.chat_id is not None,
            "exists": True,
            "chat_id": row.chat_id,
            "display_name": row.display_name,
        }


def _attempt_pair(token: str, chat_id: str, display_name: Optional[str]) -> bool:
    """Bind a chat_id to the pairing token AND to the requesting User.

    Returns True only on the *actual* transition from unpaired → paired.
    Returns False when the token is unknown (pruned / never minted) or
    already paired. The caller uses this to suppress duplicate replies
    when Telegram retries.

    If the TelegramPairing row carries a user_id (every pairing minted via
    the auth-gated route does), we also update User.telegram_chat_id and
    User.telegram_display_name so the connection survives across sessions
    and devices.
    """
    from .models import User  # local import to avoid module-level cycle

    with SessionLocal() as db:
        row = db.get(TelegramPairing, token)
        if row is None:
            return False  # unknown / pruned token
        if row.chat_id is not None:
            return False  # already paired — silent replay
        row.chat_id = chat_id
        row.display_name = display_name
        row.paired_at = datetime.now(timezone.utc)
        if row.user_id:
            user = db.get(User, row.user_id)
            if user is not None:
                user.telegram_chat_id = chat_id
                user.telegram_display_name = display_name
        db.commit()
        return True


def prune_pairings(older_than_minutes: int = 60) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    with SessionLocal() as db:
        result = db.execute(
            delete(TelegramPairing).where(TelegramPairing.created_at < cutoff)
        )
        db.commit()
        return result.rowcount or 0


# ---------- webhook -----------------------------------------------------------

def set_webhook(public_base_url: str) -> None:
    """Register the webhook with Telegram. Idempotent — safe to call on every boot.

    `public_base_url` is the externally-reachable HTTPS origin (e.g.
    https://dealtracker.maansi.fyi). Telegram will POST updates to
    `{public_base_url}/api/telegram/webhook`.

    `drop_pending_updates=true` discards any backlog accumulated while the
    webhook was unset — important during the long-poll → webhook cutover so
    we don't replay stale /start messages.
    """
    if not is_configured():
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    secret = webhook_secret()
    if not secret:
        raise RuntimeError("TELEGRAM_WEBHOOK_SECRET is not configured")

    url = f"{public_base_url.rstrip('/')}/api/telegram/webhook"
    _call("setWebhook", {
        "url": url,
        "allowed_updates": ["message"],
        "secret_token": secret,
        "drop_pending_updates": True,
    })
    log.info("telegram webhook registered -> %s", url)


def delete_webhook() -> None:
    """Clear the webhook with Telegram. Only used by ops tooling."""
    if not is_configured():
        return
    try:
        _call("deleteWebhook", {"drop_pending_updates": False})
        log.info("telegram webhook deleted")
    except Exception as e:
        log.warning("deleteWebhook failed: %s", e)


def handle_update(update: dict[str, Any]) -> bool:
    """Process one inbound Telegram update. Returns True if anything was handled.

    Called from the webhook route. Idempotent: replays of the same update_id
    are dropped silently, and _attempt_pair short-circuits on already-paired
    tokens. Safe to invoke from any thread (only DB writes happen here).
    """
    update_id = update.get("update_id")
    if isinstance(update_id, int):
        if update_id in _RECENT_UPDATE_IDS:
            return False
        _RECENT_UPDATE_IDS.append(update_id)

    msg = update.get("message") or {}
    text = (msg.get("text") or "").strip()
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return False

    from_ = msg.get("from") or {}
    first_name = from_.get("first_name") or chat.get("first_name") or "there"
    full_name = " ".join(filter(None, [from_.get("first_name"), from_.get("last_name")])) or first_name

    if not text.startswith("/start"):
        return False

    m = START_RE.match(text)
    if m:
        # /start <token-shape>: pair on the transition, silently drop on
        # replay / pruned / unknown. NEVER fall through to the help reply
        # for a token-shaped /start — that was the dual-message bug where
        # users saw paired + Hi together.
        if _attempt_pair(m.group(1), str(chat_id), full_name):
            _safe_reply(
                chat_id,
                f"✅ paired with *DealTracker*. {first_name}, you'll receive alerts here.",
            )
            return True
        log.info("dropping stale /start <token> from chat %s", chat_id)
        return False

    # Bare /start (no token argument) — user typed it by hand. Show help
    # + their chat_id so they can wire it up manually if they want to
    # bypass the Connect button.
    _safe_reply(
        chat_id,
        f"👋 Hi {first_name}, this is *DealTracker*.\n\n"
        f"Your chat ID is `{chat_id}`.\n\n"
        "To receive alerts here, open the watch form on the website "
        "and tap *Connect Telegram*. If pairing already worked you "
        "can ignore this message.",
    )
    return True


def _safe_reply(chat_id: int | str, text: str) -> None:
    try:
        send_message(str(chat_id), text)
    except Exception as e:
        log.warning("reply to %s failed: %s", chat_id, e)


__all__ = [
    "is_configured",
    "webhook_secret",
    "bot_username",
    "send_message",
    "start_pairing",
    "pairing_status",
    "handle_update",
    "set_webhook",
    "delete_webhook",
    "prune_pairings",
]
