"""Donations via DonationAlerts: a unique amount identifies the payer.

The user picks a currency and a shard pack; the bot reserves an exact amount for
them ("500₽ pack" becomes e.g. 498.37 ₽) for 48 hours. The payment is matched by
amount + currency, so the instructions must be followed literally.
"""

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from config import DONATION_DA_CURRENCY, DONATION_PAGE_URL
from core.callbacks import DonateCB, DonateClaimCB, MenuCB
from core.i18n import t
from core.keyboards import donation_currency_kb, donation_order_kb, donation_packs_kb
from core.logger import logger
from core.utils import run_db, safe_delete_message
from services import donations

router = Router()

CURRENCY_LABEL = {"RUB": "🇷🇺 Рубли", "USD": "🇺🇸 Доллары", "EUR": "🇪🇺 Евро"}


def _time_left(until, lang: str) -> str:
    seconds = max(0, int((until - donations.utcnow()).total_seconds()))
    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60
    if hours:
        return t(lang, "{hours} ч {minutes} мин", hours=hours, minutes=minutes)
    return t(lang, "{minutes} мин", minutes=minutes)


def _order_text(order: dict, lang: str) -> str:
    number = donations.amount_number(order["amount_minor"])
    return t(
        lang,
        "💳 <b>Платёжная заявка</b>\n\n"
        "{shards}🔮 за <code>{number}</code> {symbol}\n"
        "Действует ещё {left}.\n\n"
        "На странице доната:\n"
        "1) валюта - {currency};\n"
        "2) сумма - <code>{number}</code>.\n\n"
        "⚠️ Другая валюта или сумма - платёж уйдёт на ручную проверку.",
        shards=order["shards"],
        number=number,
        symbol=donations.currency_symbol(order["currency"]),
        left=_time_left(order["match_until"], lang),
        currency=DONATION_DA_CURRENCY.get(order["currency"], order["currency"]),
    )


@router.callback_query(MenuCB.filter(F.action == "donate"))
async def show_donate_menu(callback: CallbackQuery, bot: Bot, lang: str) -> None:
    await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
    await bot.send_message(
        callback.message.chat.id,
        t(
            lang,
            "💸 <b>Донат</b>\n\n"
            "Выбери валюту. Оплатить нужно ровно в той же валюте, "
            "которую выберешь здесь.",
        ),
        reply_markup=donation_currency_kb(lang),
    )
    await callback.answer()


@router.callback_query(DonateCB.filter(F.action == "packs"))
async def show_packs(
    callback: CallbackQuery, callback_data: DonateCB, lang: str
) -> None:
    currency = callback_data.value
    if currency not in CURRENCY_LABEL:
        await callback.answer(t(lang, "Неизвестная валюта"), show_alert=True)
        return
    await callback.message.edit_text(
        t(
            lang,
            "💸 <b>Донат</b> · {currency}\n\nВыбери количество:",
            currency=t(lang, CURRENCY_LABEL[currency]),
        ),
        reply_markup=donation_packs_kb(currency, lang),
    )
    await callback.answer()


@router.callback_query(DonateCB.filter(F.action == "pack"))
async def create_pack(
    callback: CallbackQuery, callback_data: DonateCB, bot: Bot, user_id: int, lang: str
) -> None:
    try:
        currency, base = callback_data.value.split("_")
        base_minor = int(base)
    except ValueError:
        await callback.answer(t(lang, "Неизвестный вариант"), show_alert=True)
        return

    order = await run_db(donations.create_order, user_id, currency, base_minor)
    if order is None:
        await callback.answer(
            t(lang, "Сейчас нет свободных сумм, попробуй через пару минут"),
            show_alert=True,
        )
        return

    logger.info(
        f"donate: user={user_id} order={order['id']} "
        f"{order['shards']} shards for {donations.fmt_minor(currency, order['amount_minor'])}"
    )
    await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
    sent = await bot.send_message(
        callback.message.chat.id,
        _order_text(order, lang),
        reply_markup=donation_order_kb(lang, order["id"], DONATION_PAGE_URL),
    )
    await run_db(donations.set_order_message, order["id"], sent.message_id)
    await callback.answer()


@router.callback_query(DonateCB.filter(F.action == "cancel"))
async def cancel_order(
    callback: CallbackQuery, callback_data: DonateCB, bot: Bot, user_id: int, lang: str
) -> None:
    try:
        order_id = int(callback_data.value)
    except ValueError:
        await callback.answer()
        return
    cancelled = await run_db(donations.cancel_order, user_id, order_id)
    await callback.answer(
        t(lang, "Заявка отменена" if cancelled else "Не найдено"),
        show_alert=not cancelled,
    )
    if not cancelled:
        return
    await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
    await bot.send_message(
        callback.message.chat.id,
        t(lang, "Заявка отменена. Если платёж уже в пути, он всё равно зачтётся."),
    )


@router.callback_query(DonateClaimCB.filter())
async def claim_payment(
    callback: CallbackQuery, callback_data: DonateClaimCB, bot: Bot, user_id: int, lang: str
) -> None:
    result = await run_db(
        donations.claim_ambiguous,
        callback_data.donation_id,
        callback_data.order_id,
        user_id,
    )
    if result.get("status") == "matched":
        if result.get("message_id"):
            try:
                await bot.delete_message(user_id, result["message_id"])
            except Exception:  # noqa: BLE001
                pass
        from services.donationalerts import notify_admin_credit

        await notify_admin_credit(bot, result)
        await callback.answer(
            t(lang, "✅ Зачтено: +{shards}🔮", shards=result["shards"]), show_alert=True
        )
    else:
        await callback.answer(t(lang, "Этот платёж уже разобран"), show_alert=True)
