from html import escape

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from config import ARENA_CALIBRATION_MATCHES
from core.callbacks import MenuCB
from core.i18n import t
from core.keyboards import language_kb, profile_kb
from core.utils import run_db, safe_delete_message
from db.queries import count_ranked_users, get_user_data, get_user_rank
from features.arena.leagues import UNRANKED, league_for_rank, position_text

router = Router()


@router.callback_query(MenuCB.filter(F.action == "profile"))
async def show_profile(callback: CallbackQuery, bot: Bot, user_id: int, lang: str) -> None:
    data = await run_db(get_user_data, user_id)
    if data is None:
        await callback.answer(t(lang, "Профиль не найден"), show_alert=True)
        return

    created_at = data.created_at.strftime("%d.%m.%Y") if data.created_at else "-"
    name = data.first_name or data.username or t(lang, "Игрок")
    if data.rating_matches < ARENA_CALIBRATION_MATCHES:
        rating_line = t(
            lang,
            "🎯 Калибровка {matches}/{total}",
            matches=data.rating_matches,
            total=ARENA_CALIBRATION_MATCHES,
        )
        league_line = t(lang, "🏅 Лига - {league}", league=UNRANKED.title(lang))
    else:
        total = await run_db(count_ranked_users)
        rank = await run_db(get_user_rank, user_id)
        league = league_for_rank(rank, total)
        rating_line = t(lang, "⚔️ Рейтинг - {rating}", rating=round(data.rating))
        league_line = t(
            lang,
            "🏅 Лига - {league} ({position})",
            league=league.title(lang),
            position=position_text(lang, rank, total),
        )

    games = data.arena_wins + data.arena_losses
    winrate = (data.arena_wins / games * 100.0) if games else 0.0

    text = t(
        lang,
        "🥷 Имя: {name}\n"
        "💠 Очки: {points}\n"
        "🎴 Количество круток: {spins}\n"
        "🔮 Количество осколков: {shards}\n"
        "🧧 Количество супер круток: {super_spins}\n"
        "📅 Дата создания аккаунта: {created}\n"
        "{league}\n"
        "{rating}\n"
        "⚔️ PvP-матчи:\n"
        "🏆 Победы: {wins} | 💀 Поражения: {losses}\n"
        "📊 Винрейт: {winrate}% (всего игр: {games})",
        name=escape(name),
        points=data.points,
        spins=data.spins,
        shards=data.shards,
        super_spins=data.super_spins,
        created=created_at,
        league=league_line,
        rating=rating_line,
        wins=data.arena_wins,
        losses=data.arena_losses,
        winrate=f"{winrate:.0f}",
        games=games,
    )
    await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
    await bot.send_message(callback.message.chat.id, text, reply_markup=profile_kb(lang))
    await callback.answer()


@router.callback_query(MenuCB.filter(F.action == "profile_lang"))
async def show_profile_language(callback: CallbackQuery, user_id: int, lang: str) -> None:
    await callback.message.edit_text(
        t(lang, "Выберите язык / Choose your language:"),
        reply_markup=language_kb(lang, back="profile"),
    )
    await callback.answer()
