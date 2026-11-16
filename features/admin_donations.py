"""Admin inbox for donations that could not be matched automatically."""

from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from config import DONATIONALERTS_CLIENT_SECRET, DONATIONALERTS_REDIRECT_URI
from core.callbacks import AdminDonateCB, AdminDonatePickCB
from core.keyboards import (
    admin_donation_card_kb,
    admin_donation_result_kb,
    admin_donations_list_kb,
)
from core.utils import run_db
from db.queries import get_user_data
from features.admin import _quit_if_requested, _with_quit, is_admin
from services import donations
from services.donation_ui import card_text, credited_text, ignored_text, list_text
from services.donationalerts import build_authorize_url, load_tokens

router = Router()

DONATIONS_PER_PAGE = 5


class DonateAdminForm(StatesGroup):
    credit_user_id = State()


async def _list_view(page: int) -> tuple[str, InlineKeyboardMarkup | None]:
    total = await run_db(donations.count_unmatched)
    pages = max(1, (total + DONATIONS_PER_PAGE - 1) // DONATIONS_PER_PAGE)
    page = max(0, min(page, pages - 1))
    items = await run_db(
        donations.list_unmatched, DONATIONS_PER_PAGE, page * DONATIONS_PER_PAGE
    )
    if not items:
        return "💸 Неразобранных донатов нет", None
    return (
        list_text(items, page, pages, total),
        admin_donations_list_kb(items, page, pages),
    )


async def _card_view(
    donation_id: int, page: int
) -> tuple[str, InlineKeyboardMarkup] | None:
    donation = await run_db(donations.get_donation, donation_id)
    if donation is None:
        return None
    candidates = await run_db(donations.donation_candidates, donation_id)
    return (
        card_text(donation, candidates),
        admin_donation_card_kb(donation_id, candidates, page),
    )


async def _edit(callback: CallbackQuery, text: str, keyboard) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:  # noqa: BLE001
        pass


async def _notify_user(bot: Bot, user_id: int, shards: int) -> None:
    try:
        await bot.send_message(user_id, f"✅ Начислено {shards}🔮 за донат.")
    except Exception:  # noqa: BLE001
        pass


@router.message(Command("da_auth"), is_admin)
async def da_auth(message: Message) -> None:
    if not DONATIONALERTS_CLIENT_SECRET:
        await message.answer(
            "❌ Задай <code>DONATIONALERTS_CLIENT_SECRET</code> в .env "
            "(ключ API приложения 15527) и перезапусти бота."
        )
        return
    url = await run_db(build_authorize_url)
    await message.answer(
        "🔐 <b>Авторизация DonationAlerts</b>\n\n"
        f"1. Открой ссылку и разреши доступ:\n{url}\n\n"
        f"2. После подтверждения вернёшься на "
        f"<code>{escape(DONATIONALERTS_REDIRECT_URI)}</code> - токен сохранится сам.\n\n"
        "Этот адрес должен быть указан в настройках OAuth-приложения на DA."
    )


@router.message(Command("da_status"), is_admin)
async def da_status(message: Message) -> None:
    info = await run_db(load_tokens)
    if not info:
        await message.answer("🔐 Токенов нет. Начни с /da_auth.")
        return
    expires = info["expires_at"].strftime("%d.%m %H:%M") if info["expires_at"] else "-"
    await message.answer(
        "🔐 <b>DonationAlerts</b>\n"
        f"Access: {'есть' if info['access_token'] else 'нет'}\n"
        f"Refresh: {'есть' if info['refresh_token'] else 'нет'}\n"
        f"Обновится после: {expires} UTC"
    )


@router.message(Command("donations"), is_admin)
async def list_donations(message: Message) -> None:
    text, keyboard = await _list_view(0)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(AdminDonateCB.filter(F.action.in_({"list", "page"})), is_admin)
async def show_list(callback: CallbackQuery, callback_data: AdminDonateCB) -> None:
    text, keyboard = await _list_view(callback_data.page)
    await _edit(callback, text, keyboard)
    await callback.answer()


@router.callback_query(AdminDonateCB.filter(F.action == "open"), is_admin)
async def open_card(callback: CallbackQuery, callback_data: AdminDonateCB) -> None:
    view = await _card_view(callback_data.donation_id, callback_data.page)
    if view is None:
        await callback.answer("Уже разобран", show_alert=True)
        text, keyboard = await _list_view(callback_data.page)
        await _edit(callback, text, keyboard)
        return
    text, keyboard = view
    await _edit(callback, text, keyboard)
    await callback.answer()


@router.callback_query(AdminDonatePickCB.filter(), is_admin)
async def credit_candidate(
    callback: CallbackQuery, callback_data: AdminDonatePickCB, bot: Bot
) -> None:
    result = await run_db(
        donations.admin_credit_order,
        callback_data.donation_id,
        callback_data.order_id,
        callback_data.user_id,
    )
    if result is None or result.get("status") != "matched":
        await callback.answer("Донат уже разобран", show_alert=True)
        return
    user = await run_db(get_user_data, result["user_id"])
    text = credited_text(
        result["currency"],
        result["amount_minor"],
        result["shards"],
        user.username if user else None,
        result["user_id"],
        result["order_id"],
    )
    await _edit(callback, text, admin_donation_result_kb(callback_data.page))
    await callback.answer(f"✅ {result['shards']}🔮")
    await _notify_user(bot, result["user_id"], result["shards"])


@router.callback_query(AdminDonateCB.filter(F.action == "ignore"), is_admin)
async def ignore_donation(
    callback: CallbackQuery, callback_data: AdminDonateCB
) -> None:
    donation = await run_db(donations.get_donation, callback_data.donation_id)
    ok = await run_db(donations.ignore_donation, callback_data.donation_id)
    if donation is None or not ok:
        await callback.answer("Уже разобран", show_alert=True)
        return
    await _edit(
        callback, ignored_text(donation), admin_donation_result_kb(callback_data.page)
    )
    await callback.answer("🚫")


@router.callback_query(AdminDonateCB.filter(F.action == "manual"), is_admin)
async def manual_start(
    callback: CallbackQuery, callback_data: AdminDonateCB, state: FSMContext
) -> None:
    donation = await run_db(donations.get_donation, callback_data.donation_id)
    if donation is None:
        await callback.answer("Уже разобран", show_alert=True)
        return
    await state.set_state(DonateAdminForm.credit_user_id)
    await state.update_data(
        donation_id=callback_data.donation_id,
        page=callback_data.page,
        card_chat=callback.message.chat.id,
        card_message=callback.message.message_id,
    )
    amount = donations.fmt_minor(donation["currency"], donation["amount_minor"])
    await callback.message.answer(
        _with_quit(
            f"Кому зачесть донат #{donation['id']} · {amount}? Введи tg id."
        )
    )
    await callback.answer()


@router.message(StateFilter(DonateAdminForm.credit_user_id), is_admin)
async def credit_finish(message: Message, state: FSMContext, bot: Bot) -> None:
    if await _quit_if_requested(message, state):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer(_with_quit("❌ ID должен быть числом."))
        return
    user_id = int(raw)
    user = await run_db(get_user_data, user_id)
    if user is None:
        await message.answer(_with_quit("❌ Пользователь не найден."))
        return

    data = await state.get_data()
    donation = await run_db(donations.get_donation, data["donation_id"])
    result = await run_db(donations.admin_credit, data["donation_id"], user_id)
    await state.clear()
    if donation is None or result is None:
        await message.answer("❌ Донат уже разобран.")
        return

    text = credited_text(
        donation["currency"],
        donation["amount_minor"],
        result["shards"],
        user.username if user else None,
        user_id,
    )
    try:
        await bot.edit_message_text(
            text,
            chat_id=data["card_chat"],
            message_id=data["card_message"],
            reply_markup=admin_donation_result_kb(data["page"]),
        )
    except Exception:  # noqa: BLE001
        await message.answer(text, reply_markup=admin_donation_result_kb(data["page"]))
    await _notify_user(bot, user_id, result["shards"])
