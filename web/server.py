from html import escape

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import LAVA_WH_URL, LAVA_WEBHOOK_SECRET
from core.logger import logger
from services.payments import process_lava_webhook

_LAVA_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><title>Lava Webhook</title></head>
<body style="font-family:sans-serif;padding:2em">
<h1>Lava Webhook</h1>
<p>Webhook URL: <b>{url}</b></p>
<p>Статус: <span style="color:green">✓ активен</span></p>
</body>
</html>"""


async def _health(_request: web.Request) -> web.Response:
    return web.Response(text="OK")


def _page(title: str, text: str) -> str:
    return (
        "<!doctype html><meta charset='utf-8'>"
        "<body style='font-family:system-ui;padding:2em;max-width:640px'>"
        f"<h3>{escape(title)}</h3><p>{escape(text)}</p></body>"
    )


async def _da_callback(request: web.Request) -> web.Response:
    """DonationAlerts OAuth redirect: exchange ?code for tokens."""
    from services.donationalerts import exchange_code

    if request.query.get("error"):
        return web.Response(
            text=_page("DonationAlerts", f"Отказ: {request.query['error']}"),
            content_type="text/html",
        )
    code = request.query.get("code")
    if not code:
        return web.Response(
            status=400,
            text=_page("DonationAlerts", "В ссылке нет code — начни заново: /da_auth"),
            content_type="text/html",
        )
    ok, message = await exchange_code(code, request.query.get("state"))
    return web.Response(
        status=200 if ok else 400,
        text=_page("DonationAlerts", message),
        content_type="text/html",
    )


async def _lava_webhook(request: web.Request) -> web.Response:
    if request.method == "GET":
        return web.Response(
            text=_LAVA_PAGE.format(url=LAVA_WH_URL),
            content_type="text/html",
        )

    if request.headers.get("X-Api-Key", "") != LAVA_WEBHOOK_SECRET:
        return web.Response(status=403, text="Forbidden")

    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        return web.Response(status=400, text="Bad Request")

    if not data:
        return web.Response(status=400, text="Bad Request")

    try:
        status = await process_lava_webhook(data, request.app["bot"])
    except Exception as e:  # noqa: BLE001
        logger.error(f"Lava webhook error: {e}")
        # 500 lets Lava retry the notification instead of dropping a paid invoice.
        return web.Response(status=500, text="Error")
    return web.Response(text=status)


def build_app(bot: Bot, dp: Dispatcher, with_telegram_webhook: bool) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_get("/health", _health)
    app.router.add_get("/da_callback", _da_callback)
    app.router.add_route("*", "/lava_webhook", _lava_webhook)

    if with_telegram_webhook:
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
        setup_application(app, dp, bot=bot)

    return app
