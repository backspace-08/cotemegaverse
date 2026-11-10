import asyncio

from aiohttp import web

from config import WEBHOOK_LISTEN, WEBHOOK_PORT, WEBHOOK_URL
from core.bot import bot, dp, setup_dispatcher
from core.logger import logger, setup_logging
from db.session import init_db
from web.server import build_app


async def _start_site(app: web.Application) -> web.AppRunner:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBHOOK_LISTEN, WEBHOOK_PORT)
    await site.start()
    logger.info(f"HTTP server listening on {WEBHOOK_LISTEN}:{WEBHOOK_PORT}")
    return runner


async def _season_watcher(bot) -> None:
    from features.arena import cfr_player
    from features.arena.decay import run_decay
    from features.arena.seasons import maybe_close_season

    tick = 0
    while True:
        # The season is checked every tick so a finished season is rolled over
        # (and stops showing "0 min left") within minutes, not within an hour.
        try:
            if await maybe_close_season(bot):
                logger.info("Arena season closed and rolled over")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Season watcher error: {e}")

        if tick % 12 == 0:  # hourly: decay + PvE prune
            try:
                charged = await run_decay(bot)
                if charged:
                    logger.info(f"Arena decay applied to {charged} players")
            except Exception as e:  # noqa: BLE001
                logger.error(f"Decay task error: {e}")
            try:
                pruned = await cfr_player.prune_stale()
                if pruned:
                    logger.info(f"Pruned {pruned} abandoned PvE bot instances")
            except Exception as e:  # noqa: BLE001
                logger.error(f"PvE prune task error: {e}")

        tick += 1
        await asyncio.sleep(300)


async def main() -> None:
    setup_logging()
    init_db()
    setup_dispatcher()

    # Cancel any battles left over from before the restart (no rating change).
    from features.arena.maintenance import reset_active_matches

    try:
        result = await reset_active_matches(bot, notify=True)
        if result["matches"]:
            logger.info(f"Startup: cancelled {result['matches']} arena matches")
    except Exception as e:  # noqa: BLE001
        logger.error(f"Startup arena reset failed: {e}")

    asyncio.create_task(_season_watcher(bot))

    from services.donationalerts import poll_forever

    asyncio.create_task(poll_forever(bot))

    if WEBHOOK_URL:
        logger.info(f"Starting in webhook mode: {WEBHOOK_URL}")
        await bot.set_webhook(WEBHOOK_URL)
        app = build_app(bot, dp, with_telegram_webhook=True)
        await _start_site(app)
        await asyncio.Event().wait()
    else:
        logger.info("Starting in polling mode")
        await bot.delete_webhook()
        app = build_app(bot, dp, with_telegram_webhook=False)
        runner = await _start_site(app)
        try:
            await dp.start_polling(bot)
        finally:
            await runner.cleanup()
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
