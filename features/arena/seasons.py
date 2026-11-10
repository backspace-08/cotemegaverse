"""Season lifecycle: payout at season end, soft reset, roll to a new season."""

import asyncio
from datetime import datetime, timezone

from config import (
    ARENA_CALIBRATION_MATCHES,
    ARENA_RATING_CENTER,
    ARENA_RESET_K,
    ARENA_RESET_RD_FLOOR,
)
from core.i18n import t
from core.logger import logger
from core.utils import run_db
from db.queries import (
    add_season_entry,
    close_season,
    ensure_current_season,
    get_user_lang,
    list_ranked_users,
    list_users_rating_matches,
    soft_reset_all_ratings,
    start_new_season,
    update_currency,
)
from features.arena.leagues import UNRANKED, league_for_rank
from features.arena.rating import DEFAULT_VOL


def _utc_naive(ends_at: datetime | None) -> datetime | None:
    if ends_at is None:
        return None
    if ends_at.tzinfo is not None:
        return ends_at.astimezone(timezone.utc).replace(tzinfo=None)
    return ends_at


def seconds_left(ends_at: datetime | None) -> int:
    ends_at = _utc_naive(ends_at)
    if ends_at is None:
        return 0
    delta = ends_at - datetime.now(timezone.utc).replace(tzinfo=None)
    return max(0, int(delta.total_seconds()))


def is_finished(ends_at: datetime | None) -> bool:
    ends_at = _utc_naive(ends_at)
    return ends_at is not None and datetime.now(timezone.utc).replace(tzinfo=None) >= ends_at


async def season_status() -> dict:
    season = await run_db(ensure_current_season)
    return {
        "id": season["id"],
        "ends_at": season["ends_at"],
        "seconds_left": seconds_left(season["ends_at"]),
    }


async def run_season_close(bot) -> dict:
    """Payout to every ranked player, soft-reset them, then open a new season.

    The end-of-season notice goes to *every* user - including those who never
    played - so the leagues and their rewards are at least seen.
    """
    season = await run_db(ensure_current_season)
    ranked = await run_db(list_ranked_users)
    total = len(ranked)
    # snapshot before the reset: the notice shows the season that just ended
    audience = await run_db(list_users_rating_matches)

    results: dict[int, dict] = {}
    for place, entry in enumerate(ranked, start=1):
        user_id = entry["user_id"]
        league = league_for_rank(place, total)
        results[user_id] = {"league": league, "place": place, "rating": round(entry["rating"])}
        try:
            if league.shards:
                await run_db(update_currency, user_id, "shards", league.shards)
            if league.spins:
                await run_db(update_currency, user_id, "spins", league.spins)
            await run_db(
                add_season_entry,
                season["id"], user_id, entry["rating"], league.key, place, league.shards, league.spins,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Season payout error for {user_id}: {e}")
        await asyncio.sleep(0.05)

    # everyone restarts calibration at 0/10 - ranked players and those who
    # never reached 10 matches alike
    reset = await run_db(
        soft_reset_all_ratings,
        float(ARENA_RATING_CENTER),
        ARENA_RESET_K,
        ARENA_RESET_RD_FLOOR,
        DEFAULT_VOL,
    )

    await run_db(close_season, season["id"])
    await run_db(start_new_season)

    notified = await _notify_season_end(bot, results, total, audience)
    logger.info(
        f"Season {season['id']} closed, {total} players paid, "
        f"{reset} ratings soft-reset, {notified} notified"
    )
    return {"count": total, "reset": reset, "notified": notified}


async def _notify_season_end(
    bot, results: dict[int, dict], total: int, audience: list[tuple[int, int]]
) -> int:
    """Season summary for everyone: ranked players get their result, the rest
    a 'Без лиги (калибровка N/10)' line."""
    sent = 0
    for user_id, matches in audience:
        lang = await run_db(get_user_lang, user_id) or "ru"
        summary = results.get(user_id)
        if summary is not None:
            league = summary["league"]
            text = t(
                lang,
                "🏁 Сезон арены окончен!\n"
                "Лига - {league}\n"
                "Место - {place}/{total}\n"
                "📊 Рейтинг - {rating}\n"
                "Награды - 🔮{shards}, 🎴{spins}",
                league=league.title(lang),
                place=summary["place"],
                total=total,
                rating=summary["rating"],
                shards=league.shards,
                spins=league.spins,
            )
        else:
            text = t(
                lang,
                "🏁 Сезон арены окончен!\nЛига - {league}",
                league=(
                    f"{UNRANKED.title(lang)} "
                    f"({t(lang, 'Калибровка').lower()} {matches}/{ARENA_CALIBRATION_MATCHES})"
                ),
            )
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception as e:  # noqa: BLE001
            logger.error(f"Season notice failed for {user_id}: {e}")
        await asyncio.sleep(0.05)
    return sent


async def maybe_close_season(bot) -> bool:
    season = await run_db(ensure_current_season)
    if is_finished(season["ends_at"]):
        await run_season_close(bot)
        return True
    return False
