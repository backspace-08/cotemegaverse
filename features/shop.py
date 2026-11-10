"""🛒 Shop - daily rotating level-up lots for cards the player owns."""

from html import escape

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from config import MAX_CHARACTER_LEVEL, SHOP_MIN_CARDS
from core.callbacks import MenuCB, ShopCB
from core.i18n import t
from core.keyboards import shop_empty_kb, shop_kb
from core.logger import logger
from core.texts import RARITY_EMOJI, card_name, get_type_char, level_cost, loc_rarity
from core.utils import edit_character_card, run_db, safe_delete_message, send_character_card
from db.queries import count_user_characters
from services import shop
from services.leveling import next_level_stats
from services.locks import user_lock

router = Router()


def _fmt(lang: str, seconds: int) -> str:
    hours, minutes = divmod(seconds // 60, 60)
    return t(lang, "{hours}ч {minutes}м", hours=hours, minutes=minutes)


def _lot_caption(lot: shop.Lot, lang: str = "ru", note: str = "") -> str:
    lines = []
    if note:
        lines.append(note)
    lines.append(t(lang, "🛒 <b>Магазин</b>"))
    lines.append(f"{get_type_char(lot.card.type)} <b>{escape(card_name(lot.card, lang))}</b>")
    lines.append(f"{RARITY_EMOJI.get(lot.rarity, '')} {loc_rarity(lang, lot.rarity)}")
    if lot.maxed:
        lines.append(t(lang, "👑 Максимальный уровень ({level})", level=MAX_CHARACTER_LEVEL))
    elif lot.purchased:
        lines.append(f"👑 Lv.{lot.level}")
    else:
        lines.append(f"👑 Lv.{lot.level} → Lv.{lot.level + 1}")
    nxt = next_level_stats(lot.card) if not (lot.maxed or lot.purchased) else None
    hp = f"{lot.card.health} → {nxt['hp']}" if nxt else f"{lot.card.health}"
    atk = f"{lot.card.attack} → {nxt['attack']}" if nxt else f"{lot.card.attack}"
    lines.append(f"<blockquote>├‣❤️ - {hp}\n├‣💪 - {atk}</blockquote>")
    if not lot.maxed and not lot.purchased:
        price = t(lang, "💠 Цена: {price}🔮", price=lot.price)
        if lot.rarity != "special":
            price += f" <s>{level_cost(lot.rarity, lot.level)}🔮</s>"
        lines.append(price)
    lines.append(t(lang, "\n🔄 Обновится через {time}", time=_fmt(lang, shop.seconds_to_reset())))
    return "\n".join(lines)


async def _render(
    bot: Bot,
    callback: CallbackQuery,
    user_id: int,
    lang: str,
    index: int = 0,
    char_id: int | None = None,
    note: str = "",
) -> None:
    async with user_lock(user_id):
        day = await run_db(shop.shop_day)
        lots = await run_db(shop.build_lots, user_id, day)

    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    if not lots:
        await safe_delete_message(bot, chat_id, message_id)
        await bot.send_message(
            chat_id, t(lang, "🛒 Магазин пуст - нет карт для прокачки."), reply_markup=shop_empty_kb(lang)
        )
        return

    if char_id is not None:
        index = next((i for i, lot in enumerate(lots) if lot.char_id == char_id), 0)
    index %= len(lots)
    lot = lots[index]
    state = "maxed" if lot.maxed else ("purchased" if lot.purchased else "buy")
    markup = shop_kb(day, index, len(lots), lot.char_id, state, lang)
    caption = _lot_caption(lot, lang, note)

    if callback.message.photo or callback.message.animation:
        await edit_character_card(bot, chat_id, message_id, lot.card.image_path, caption, markup)
    else:
        await safe_delete_message(bot, chat_id, message_id)
        await send_character_card(bot, chat_id, lot.card.image_path, caption, markup)


@router.callback_query(MenuCB.filter(F.action == "shop"))
async def show_shop(callback: CallbackQuery, bot: Bot, user_id: int, lang: str) -> None:
    owned = await run_db(count_user_characters, user_id)
    if owned < SHOP_MIN_CARDS:
        await callback.answer(
            t(
                lang,
                "🔒 Магазин откроется с {count} карточек - осталось ещё {left}",
                count=SHOP_MIN_CARDS,
                left=SHOP_MIN_CARDS - owned,
            ),
            show_alert=True,
        )
        return
    await _render(bot, callback, user_id, lang, index=0)
    await callback.answer()


@router.callback_query(ShopCB.filter(F.action == "nav"))
async def shop_nav(
    callback: CallbackQuery, callback_data: ShopCB, bot: Bot, user_id: int, lang: str
) -> None:
    current = await run_db(shop.shop_day)
    if callback_data.day != current:
        await callback.answer(t(lang, "🔄 Магазин обновился"))
        await _render(
            bot, callback, user_id, lang, index=0, note=t(lang, "🔄 <i>Ассортимент обновился.</i>")
        )
        return
    await _render(bot, callback, user_id, lang, index=callback_data.index)
    await callback.answer()


@router.callback_query(ShopCB.filter(F.action == "buy"))
async def shop_buy(
    callback: CallbackQuery, callback_data: ShopCB, bot: Bot, user_id: int, lang: str
) -> None:
    async with user_lock(user_id):
        result = await run_db(shop.buy, user_id, callback_data.day, callback_data.char_id)

    if result.status == "stale":
        await callback.answer(t(lang, "🔄 Магазин обновился"), show_alert=True)
        await _render(
            bot, callback, user_id, lang, index=0, note=t(lang, "🔄 <i>Ассортимент обновился.</i>")
        )
        return

    if result.status == "ok":
        logger.info(f"shop: user={user_id} bought {callback_data.char_id} to Lv.{result.new_level} for {result.cost}")
        await callback.answer(f"✅ Lv.{result.new_level}")
        await _render(bot, callback, user_id, lang, char_id=callback_data.char_id)
        return

    messages = {
        "purchased": t(lang, "✅ Уже куплено"),
        "maxed": t(lang, "👑 Максимальный уровень"),
        "insufficient": t(lang, "Недостаточно осколков: нужно {cost}🔮", cost=result.cost),
        "not_found": t(lang, "Лот недоступен"),
    }
    await callback.answer(messages.get(result.status, t(lang, "Не удалось купить")), show_alert=True)
    await _render(bot, callback, user_id, lang, char_id=callback_data.char_id)
