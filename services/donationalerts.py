"""DonationAlerts API: OAuth, token refresh and donation polling.

DA has no webhooks for donations; the public API exposes a paginated list
(`GET /api/v1/alerts/donations`) behind an OAuth token. We poll page 1 every few
seconds and deduplicate by the donation id, so a restart or a missed tick cannot
lose or double-credit a payment.

Tokens live in the DB (`donation_tokens`), so `/da_auth` can be completed
without redeploying: the poller picks the new token up on its next tick.
"""

import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import aiohttp

from config import (
    ADMIN_ID,
    DONATION_POLL_SECONDS,
    DONATIONALERTS_CLIENT_ID,
    DONATIONALERTS_CLIENT_SECRET,
    DONATIONALERTS_REDIRECT_URI,
    DONATIONALERTS_REFRESH_TOKEN,
    DONATIONALERTS_SCOPE,
    DONATIONALERTS_TOKEN,
)
from core.i18n import t
from core.logger import logger
from core.utils import run_db
from db.models import DonationToken
from db.queries import get_user_data, get_user_lang
from db.session import get_session
from services.donations import fmt_minor, match_donation

API_URL = "https://www.donationalerts.com/api/v1"
AUTHORIZE_URL = "https://www.donationalerts.com/oauth/authorize"
TOKEN_URL = "https://www.donationalerts.com/oauth/token"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ──────────────────────────────────────────────
# Token storage
# ──────────────────────────────────────────────

def load_tokens() -> dict | None:
    with get_session() as session:
        row = session.get(DonationToken, 1)
        if row is None:
            return None
        return {
            "access_token": row.access_token or "",
            "refresh_token": row.refresh_token or "",
            "expires_at": row.expires_at,
            "state": row.state or "",
        }


def save_tokens(
    access_token: str, refresh_token: str | None = None, expires_in: int = 3600
) -> None:
    with get_session() as session:
        row = session.get(DonationToken, 1)
        if row is None:
            row = DonationToken(id=1)
            session.add(row)
        row.access_token = access_token
        if refresh_token:
            row.refresh_token = refresh_token
        row.expires_at = utcnow() + timedelta(seconds=max(60, int(expires_in or 3600) - 120))
        row.state = None


def build_authorize_url() -> str:
    """One-time authorization link (the state is kept in the DB)."""
    state = secrets.token_urlsafe(16)
    with get_session() as session:
        row = session.get(DonationToken, 1)
        if row is None:
            row = DonationToken(id=1)
            session.add(row)
        row.state = state
    query = urlencode(
        {
            "client_id": DONATIONALERTS_CLIENT_ID,
            "redirect_uri": DONATIONALERTS_REDIRECT_URI,
            "response_type": "code",
            "scope": DONATIONALERTS_SCOPE,
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


async def exchange_code(code: str, state: str | None = None) -> tuple[bool, str]:
    """Trade the authorization code for tokens and store them."""
    if not DONATIONALERTS_CLIENT_SECRET:
        return False, "DONATIONALERTS_CLIENT_SECRET не задан в .env"
    stored = await run_db(load_tokens)
    if stored and stored.get("state") and state and stored["state"] != state:
        return False, "Неверный state. Начни заново: /da_auth"

    payload = {
        "grant_type": "authorization_code",
        "client_id": DONATIONALERTS_CLIENT_ID,
        "client_secret": DONATIONALERTS_CLIENT_SECRET,
        "redirect_uri": DONATIONALERTS_REDIRECT_URI,
        "code": code,
    }
    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(TOKEN_URL, data=payload) as resp:
            data = await resp.json(content_type=None)
    if resp.status != 200 or "access_token" not in data:
        return False, f"DonationAlerts ответил {resp.status}: {data}"
    await run_db(
        save_tokens,
        data["access_token"],
        data.get("refresh_token"),
        int(data.get("expires_in") or 3600),
    )
    logger.info("DonationAlerts: authorization completed, tokens stored")
    return True, "✅ Готово - токен сохранён. Эту вкладку можно закрыть."


# ──────────────────────────────────────────────
# API client
# ──────────────────────────────────────────────

class DonationAlertsClient:
    def __init__(
        self,
        token: str = "",
        client_id: str = "",
        client_secret: str = "",
        refresh_token: str = "",
    ) -> None:
        self.token = token
        self.client_id = client_id or DONATIONALERTS_CLIENT_ID
        self.client_secret = client_secret or DONATIONALERTS_CLIENT_SECRET
        self.refresh_token = refresh_token
        self._session: aiohttp.ClientSession | None = None

    async def _http(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=25)
            )
        return self._session

    async def refresh(self) -> bool:
        """Exchange the refresh token for a new access token."""
        if not (self.refresh_token and self.client_id and self.client_secret):
            return False
        session = await self._http()
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }
        async with session.post(TOKEN_URL, data=payload) as resp:
            data = await resp.json(content_type=None)
        if resp.status != 200 or "access_token" not in data:
            logger.error(f"DonationAlerts: token refresh failed ({resp.status}): {data}")
            return False
        self.token = data["access_token"]
        if data.get("refresh_token"):
            self.refresh_token = data["refresh_token"]
        await run_db(
            save_tokens,
            self.token,
            self.refresh_token,
            int(data.get("expires_in") or 3600),
        )
        logger.info("DonationAlerts: access token refreshed")
        return True

    async def _get(self, path: str, params: dict | None = None) -> dict:
        session = await self._http()
        headers = {"Authorization": f"Bearer {self.token}"}
        async with session.get(API_URL + path, params=params, headers=headers) as resp:
            if resp.status == 401 and await self.refresh():
                headers = {"Authorization": f"Bearer {self.token}"}
                async with session.get(API_URL + path, params=params, headers=headers) as retry:
                    data = await retry.json(content_type=None)
                    if retry.status != 200:
                        raise RuntimeError(f"HTTP {retry.status}: {data}")
                    return data
            data = await resp.json(content_type=None)
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}: {data}")
            return data

    async def donations(self, page: int = 1) -> list[dict]:
        data = await self._get("/alerts/donations", {"page": page})
        return data.get("data") or []


def _parse_created(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


async def _send(bot, chat_id: int, text: str, reply_markup=None) -> None:
    try:
        await bot.send_message(chat_id, text, reply_markup=reply_markup)
    except Exception as e:  # noqa: BLE001
        logger.error(f"DonationAlerts: cannot message {chat_id}: {e}")


async def notify_admin_credit(bot, result: dict, donor: str | None = None) -> None:
    """Tell the admin about a credited donation."""
    user = await run_db(get_user_data, result["user_id"])
    if user is None:
        who = str(result["user_id"])
    elif user.username:
        who = f"@{user.username}"
    else:
        who = user.first_name or str(result["user_id"])
    text = (
        f"💸 Донат зачтён: {fmt_minor(result['currency'], result['amount_minor'])} "
        f"→ +{result['shards']}🔮\n"
        f"👤 {who} (id {result['user_id']})\n"
        f"🆔 заявка #{result['order_id']} · {result.get('flag') or 'exact'}"
    )
    if donor:
        text += f"\nПлательщик: {donor}"
    await _send(bot, ADMIN_ID, text)


async def _process(bot, item: dict) -> None:
    from core.keyboards import donation_claim_kb

    try:
        provider_id = int(item["id"])
        amount_minor = int(round(float(item.get("amount") or 0) * 100))
        currency = str(item.get("currency") or "").upper()
    except (KeyError, TypeError, ValueError):
        logger.error(f"DonationAlerts: bad item {item!r}")
        return

    amount = fmt_minor(currency, amount_minor)
    result = await run_db(
        match_donation,
        provider_id,
        amount_minor,
        currency,
        item.get("username"),
        item.get("message"),
        _parse_created(item.get("created_at")),
        item,
    )
    status = result.get("status")

    if status == "matched":
        if result.get("message_id"):
            try:
                await bot.delete_message(result["user_id"], result["message_id"])
            except Exception as e:  # noqa: BLE001
                logger.info(f"DonationAlerts: cannot delete the order message: {e}")
        lang = await run_db(get_user_lang, result["user_id"]) or "ru"
        await _send(
            bot,
            result["user_id"],
            t(lang, "✅ Донат получен: {amount} → +{shards}🔮", amount=amount, shards=result["shards"]),
        )
        await notify_admin_credit(bot, result, item.get("username"))
        logger.info(
            f"DonationAlerts: donation {provider_id} matched to user {result['user_id']} "
            f"({amount}, +{result['shards']} shards, flag={result.get('flag') or 'exact'})"
        )
    elif status == "ambiguous":
        for candidate in result["candidates"]:
            lang = await run_db(get_user_lang, candidate["user_id"]) or "ru"
            await _send(
                bot,
                candidate["user_id"],
                t(
                    lang,
                    "💸 Пришёл платёж на {amount}. Это твой? Подтверди, чтобы зачесть.",
                    amount=amount,
                ),
                donation_claim_kb(result["donation_id"], candidate["order_id"], lang),
            )
        await _send(
            bot,
            ADMIN_ID,
            f"💸 Донат {amount} подходит к нескольким заявкам "
            f"({len(result['candidates'])}). Отправлены пуши на подтверждение.",
        )
    elif status == "manual":
        username = item.get("username") or "аноним"
        message = (item.get("message") or "").strip() or "-"
        await _send(
            bot,
            ADMIN_ID,
            f"💸 Донат {amount} от {username}\n"
            f"Сообщение: {message}\n"
            f"Причина: {result.get('reason')} · заявка не найдена.\n"
            f"Разобрать: /donations",
        )
        logger.info(f"DonationAlerts: donation {provider_id} queued for admin ({result.get('reason')})")


async def _ensure_token(client: DonationAlertsClient) -> bool:
    """Prefer tokens stored via /da_auth; refresh them before they expire."""
    stored = await run_db(load_tokens)
    if stored:
        client.token = stored["access_token"]
        client.refresh_token = stored["refresh_token"]
        expires_at = stored["expires_at"]
        if expires_at and expires_at <= utcnow() + timedelta(minutes=5):
            if await client.refresh():
                return True
        if client.token:
            return True
    if not client.token and client.refresh_token:
        return await client.refresh()
    return bool(client.token)


async def poll_forever(bot) -> None:
    client = DonationAlertsClient(
        token=DONATIONALERTS_TOKEN,
        client_id=DONATIONALERTS_CLIENT_ID,
        client_secret=DONATIONALERTS_CLIENT_SECRET,
        refresh_token=DONATIONALERTS_REFRESH_TOKEN,
    )
    warned = False
    logger.info("DonationAlerts: polling task started")
    while True:
        try:
            if not await _ensure_token(client):
                if not warned:
                    logger.warning(
                        "DonationAlerts: not authorized yet - open /da_auth in the admin bot"
                    )
                    warned = True
                await asyncio.sleep(DONATION_POLL_SECONDS)
                continue
            warned = False
            items = await client.donations(1)
            for item in sorted(items, key=lambda row: int(row.get("id") or 0)):
                await _process(bot, item)
        except Exception as e:  # noqa: BLE001
            logger.error(f"DonationAlerts poll failed: {e}")
        await asyncio.sleep(DONATION_POLL_SECONDS)
