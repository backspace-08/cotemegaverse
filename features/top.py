from html import escape

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from config import ARENA_CALIBRATION_MATCHES
from core.callbacks import MenuCB, TopCB
from core.i18n import t
from core.keyboards import top_types_kb
from core.utils import run_db, safe_delete_message
from db.queries import count_ranked_users, get_top_players
from features.arena.leagues import league_for_rank

router = Router()


@router.callback_query(MenuCB.filter(F.action == "top"))
async def choose_top_type(callback: CallbackQuery, bot: Bot, lang: str) -> None:
    await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
    await bot.send_message(
        callback.message.chat.id, t(lang, "Выберите топ:"), reply_markup=top_types_kb(lang)
    )
    await callback.answer()


def _user_link(callback: CallbackQuery, lang: str) -> str:
    name = escape(callback.from_user.first_name or t(lang, "Игрок"))
    if callback.from_user.username:
        return f'<b><a href="https://t.me/{callback.from_user.username}">{name}</a></b>'
    return f"<b>{name}</b>"


async def _render_top(callback: CallbackQuery, bot: Bot, kind: str, lang: str) -> None:
    user_id = callback.from_user.id
    if kind == "points":
        data = await run_db(get_top_players, user_id, 10, "points")
        title = t(lang, "вот топ по очкам сейчас")
        lines = "\n".join(
            t(
                lang,
                "{pos}. {name} - <em><b>{value} pts</b></em>",
                pos=pos,
                name=escape(name or t(lang, "Игрок")),
                value=value,
            )
            for pos, name, value in data["top"]
        )
    else:
        data = await run_db(get_top_players, user_id, 10, "rating", ARENA_CALIBRATION_MATCHES)
        total = await run_db(count_ranked_users)
        title = t(lang, "вот топ по арене сейчас")
        lines = "\n".join(
            f"{pos}. {escape(name or t(lang, 'Игрок'))} - {league_for_rank(pos, total).emoji} "
            f"<em><b>{round(value or 0)}</b></em>"
            for pos, name, value in data["top"]
        )

    position = data.get("user_position", {}).get("position", "-")
    text = t(
        lang,
        "⚡ {user}, {title}:\n➖➖➖➖➖➖\n{lines}\n➖➖➖➖➖➖\n⏺️ Твое место - {position}",
        user=_user_link(callback, lang),
        title=title,
        lines=lines,
        position=position,
    )
    await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
    await bot.send_message(
        callback.message.chat.id,
        text,
        reply_markup=top_types_kb(lang),
        disable_web_page_preview=True,
    )


@router.callback_query(TopCB.filter(F.kind == "points"))
async def show_top_points(callback: CallbackQuery, bot: Bot, lang: str) -> None:
    await _render_top(callback, bot, "points", lang)
    await callback.answer()


@router.callback_query(TopCB.filter(F.kind == "rating"))
async def show_top_rating(callback: CallbackQuery, bot: Bot, lang: str) -> None:
    await _render_top(callback, bot, "rating", lang)
    await callback.answer()
