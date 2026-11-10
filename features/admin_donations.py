"""Admin queue for donations that could not be matched automatically."""

from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import DONATIONALERTS_CLIENT_SECRET, DONATIONALERTS_REDIRECT_URI
from core.callbacks import AdminDonateCB
from core.keyboards import admin_donations_kb
from core.utils import run_db
from db.queries import get_user_data
from features.admin import _quit_if_requested, _with_quit, is_admin
from services import donations
from services.donationalerts import build_authorize_url, load_tokens

router = Router()


class DonateAdminForm(StatesGroup):
    credit_user_id = State()


def _view(items: list[dict]):
    lines = ["💸 <b>Неразобранные донаты</b>"]
    prepared = []
    for item in items:
        amount = donations.fmt_minor(item["currency"], item["amount_minor"])
        username = escape(item["username"] or "аноним")
        message = escape((item["message"] or "").strip()[:80] or "-")
        lines.append(
            f"\n<b>#{item['id']}</b> · {amount} · {username}\n"
            f"«{message}»\n"
            f"→ {item['suggested']}🔮 · {item['status']} ({item['note']})"
        )
        prepared.append({**item, "label": f"#{item['id']} {amount}"})
    return "\n".join(lines), admin_donations_kb(prepared)


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
    items = await run_db(donations.list_unmatched)
    if not items:
        await message.answer("💸 Неразобранных донатов нет")
        return
    text, keyboard = _view(items)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(AdminDonateCB.filter(F.action == "credit"), is_admin)
async def credit_start(
    callback: CallbackQuery, callback_data: AdminDonateCB, state: FSMContext
) -> None:
    donation = await run_db(donations.get_donation, callback_data.donation_id)
    if donation is None:
        await callback.answer("Не найдено", show_alert=True)
        return
    await state.set_state(DonateAdminForm.credit_user_id)
    await state.update_data(donation_id=callback_data.donation_id)
    amount = donations.fmt_minor(donation["currency"], donation["amount_minor"])
    await callback.message.answer(
        _with_quit(f"Кому зачесть донат {amount}? Введи tg id.")
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
    if await run_db(get_user_data, user_id) is None:
        await message.answer(_with_quit("❌ Пользователь не найден."))
        return

    data = await state.get_data()
    result = await run_db(donations.admin_credit, data["donation_id"], user_id)
    await state.clear()
    if result is None:
        await message.answer("❌ Донат уже разобран.")
        return

    await message.answer(f"✅ Зачтено: {result['shards']}🔮 → <code>{user_id}</code>")
    try:
        await bot.send_message(
            user_id, f"✅ Начислено {result['shards']}🔮 за донат."
        )
    except Exception:  # noqa: BLE001
        pass


@router.callback_query(AdminDonateCB.filter(F.action == "ignore"), is_admin)
async def ignore_donation(callback: CallbackQuery, callback_data: AdminDonateCB) -> None:
    ok = await run_db(donations.ignore_donation, callback_data.donation_id)
    await callback.answer(
        "🚫 Отклонено" if ok else "Уже разобран", show_alert=not ok
    )
    if ok:
        await callback.message.edit_reply_markup(reply_markup=None)
