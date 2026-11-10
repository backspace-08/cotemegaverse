"""Arena maintenance: cancel active matches without touching ratings.

Used on startup (after a deploy/restart) and by the admin cleanup commands.
"""

from core.i18n import t
from core.logger import logger
from features.arena import cfr_player
from features.arena.store import clear_matches


async def reset_active_matches(bot=None, only: str | None = None, notify: bool = True) -> dict:
    """Delete active matches (only: 'pvp' | 'pve' | None) and clean up state."""
    from features.arena import handlers  # local import to avoid a cycle

    removed = await clear_matches(only)
    handlers.cancel_timers([match["match_id"] for match in removed])
    cfr_player.drop_players([match["match_id"] for match in removed if match["vs_bot"]])

    notified: set[int] = set()
    if notify and bot is not None:
        for match in removed:
            for uid in (match["player1"], match["player2"]):
                if uid and uid != 0 and uid not in notified:
                    try:
                        from db.queries import get_user_lang

                        lang = await get_user_lang(uid) or "ru"
                        await bot.send_message(
                            uid,
                            t(
                                lang,
                                "⚠️ Бот обновился - текущие бои арены отменены.\n"
                                "Рейтинг не изменён, можно начать заново.",
                            ),
                        )
                    except Exception as e:  # noqa: BLE001
                        logger.error(f"Arena cancel notify failed for {uid}: {e}")
                    notified.add(uid)

    logger.info(f"Arena matches cleared: {len(removed)} (only={only}), notified={len(notified)}")
    return {"matches": len(removed), "notified": len(notified)}
