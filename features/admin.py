import asyncio
import random
from html import escape

import aiohttp
from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import (
    ADMIN_ID,
    CFR_MAX_ACTIVE,
    CFR_MAX_CONCURRENCY,
    CLEAR_PVE_PHRASE,
    CLEAR_PVP_PHRASE,
    FULL_RESET_PHRASE,
    RESET_ARENA_PHRASE,
    RESET_BOT_PHRASE,
    SEASON_END_PHRASE,
    START_SPINS,
    card_image,
)
from core.callbacks import AdminUsersCB
from core.keyboards import (
    admin_char_kb,
    admin_char_rarity_kb,
    admin_user_currency_kb,
    admin_user_kb,
    admin_users_list_kb,
)
from core.logger import logger
from core.texts import character_caption
from core.utils import (
    edit_character_card,
    run_db,
    safe_delete_message,
    safe_edit_text,
    send_character_card,
)
from features.arena import cfr_player
from features.arena.metrics import stats as cfr_stats
from features.arena.results import bot_winrate_line
from seed import sync_characters
from db.queries import (
    get_all_user_ids,
    get_character_by_id,
    get_character_catalog,
    get_rarity_counts,
    get_user_character,
    get_user_data,
    get_user_id_by_username,
    get_user_rarity_counts,
    get_users_page,
    grant_character,
    grant_character_or_level,
    reset_all_progress,
    reset_all_ratings,
    reset_bot_stats,
    update_currency,
)
from features.arena.maintenance import reset_active_matches

router = Router()


class AdminForm(StatesGroup):
    get_id_username = State()
    give_char_id = State()
    all_currency_amount = State()
    broadcast_text = State()
    confirm_action = State()
    users_amount = State()
    users_message = State()


def is_admin(event: Message | CallbackQuery) -> bool:
    return event.from_user is not None and event.from_user.id == ADMIN_ID


QUIT_HINT = "/quit - отмена."


def _with_quit(text: str) -> str:
    """Standard ending for every admin prompt that accepts /quit."""
    return f"{text}\n\n{QUIT_HINT}"


async def _quit_if_requested(message: Message, state: FSMContext) -> bool:
    # Accept both "quit" and "/quit" (the prompts tell the admin to type /quit).
    text = (message.text or "").strip().lower().lstrip("/")
    if text == "quit":
        await message.answer("Выход из команды")
        await state.clear()
        return True
    return False


# ──────────────────────────────────────────────
# /users - user browser
# ──────────────────────────────────────────────

USERS_PER_PAGE = 5
_CURRENCY_ICON = {"shards": "🔮", "spins": "🎴", "super_spins": "🧧"}
_CURRENCY_LABEL = {"shards": "осколков", "spins": "круток", "super_spins": "супер-круток"}


def _display_name(data, user_id: int) -> str:
    if data is not None:
        if data.first_name:
            return data.first_name
        if data.username:
            return f"@{data.username}"
    return str(user_id)


async def _users_page_view(page: int):
    data = await run_db(get_users_page, page, USERS_PER_PAGE)
    text = (
        "👥 <b>Пользователи</b> · по очкам 💠\n"
        f"Страница {data['page'] + 1}/{data['total_pages']} · всего {data['total']}"
    )
    start = data["page"] * USERS_PER_PAGE + 1
    return text, admin_users_list_kb(data["items"], data["page"], data["total_pages"], start)


async def _user_view(user_id: int, page: int, note: str = ""):
    data = await run_db(get_user_data, user_id)
    if data is None:
        page_data = await run_db(get_users_page, page, USERS_PER_PAGE)
        start = page_data["page"] * USERS_PER_PAGE + 1
        return (
            "❌ Пользователь не найден",
            admin_users_list_kb(
                page_data["items"], page_data["page"], page_data["total_pages"], start
            ),
        )
    username = f"@{data.username}" if data.username else "-"
    created = data.created_at.strftime("%d.%m.%Y") if data.created_at else "-"
    text = (
        f"👤 <b>{escape(data.first_name or 'Игрок')}</b>\n"
        f"🔗 {escape(username)}\n"
        f"🆔 <code>{data.user_id}</code>\n"
        f"🔮 Осколки: {data.shards}\n"
        f"🎴 Крутки: {data.spins}\n"
        f"🧧 Супер-крутки: {data.super_spins}\n"
        f"📅 Регистрация: {created}"
    )
    if note:
        text += f"\n\n{note}"
    return text, admin_user_kb(user_id, page)


async def _render_text(bot: Bot, callback: CallbackQuery, text: str, kb) -> None:
    """Edit the current text message in place; fall back to resend if it's media."""
    msg = callback.message
    if msg.text is not None:
        await safe_edit_text(bot, msg.chat.id, msg.message_id, text, kb)
    else:
        await safe_delete_message(bot, msg.chat.id, msg.message_id)
        await bot.send_message(msg.chat.id, text, reply_markup=kb)


async def _render_admin_char(bot: Bot, callback: CallbackQuery, user_id: int, page: int, rarity: str, cpage: int) -> bool:
    catalog = await run_db(get_character_catalog, rarity, user_id)
    if not catalog:
        return False
    cpage %= len(catalog)
    entry = catalog[cpage]
    card = entry["card"]
    owned = entry["owned"]
    level = entry["level"]
    kb = admin_char_kb(user_id, page, rarity, card.char_id, cpage, len(catalog), owned, level)
    title = f"✅ Есть у игрока · Lv.{level}" if owned else "🆕 Нет у игрока"
    caption = character_caption(card, title=title)
    msg = callback.message
    if msg.photo or msg.animation:
        await edit_character_card(bot, msg.chat.id, msg.message_id, card.image_path, caption, kb)
    else:
        await safe_delete_message(bot, msg.chat.id, msg.message_id)
        await send_character_card(bot, msg.chat.id, card.image_path, caption, kb)
    return True


@router.message(Command("users"), is_admin)
async def users_start(message: Message) -> None:
    text, kb = await _users_page_view(0)
    await message.answer(text, reply_markup=kb)


@router.callback_query(AdminUsersCB.filter(F.action == "list"), is_admin)
async def users_list(callback: CallbackQuery, callback_data: AdminUsersCB, bot: Bot) -> None:
    text, kb = await _users_page_view(callback_data.page)
    await _render_text(bot, callback, text, kb)
    await callback.answer()


@router.callback_query(AdminUsersCB.filter(F.action == "user"), is_admin)
async def users_view(callback: CallbackQuery, callback_data: AdminUsersCB, bot: Bot) -> None:
    text, kb = await _user_view(callback_data.user_id, callback_data.page)
    await _render_text(bot, callback, text, kb)
    await callback.answer()


@router.callback_query(AdminUsersCB.filter(F.action == "currency"), is_admin)
async def users_currency(callback: CallbackQuery, callback_data: AdminUsersCB, bot: Bot) -> None:
    data = await run_db(get_user_data, callback_data.user_id)
    text = (
        f"💰 Валюта для <b>{escape(_display_name(data, callback_data.user_id))}</b> "
        f"(id <code>{callback_data.user_id}</code>)"
    )
    await _render_text(
        bot, callback, text, admin_user_currency_kb(callback_data.user_id, callback_data.page)
    )
    await callback.answer()


@router.callback_query(AdminUsersCB.filter(F.action == "curpick"), is_admin)
async def users_curpick(
    callback: CallbackQuery, callback_data: AdminUsersCB, state: FSMContext, bot: Bot
) -> None:
    if callback_data.field not in _CURRENCY_ICON:
        await callback.answer("Неизвестная валюта", show_alert=True)
        return
    data = await run_db(get_user_data, callback_data.user_id)
    await state.set_state(AdminForm.users_amount)
    await state.update_data(
        target_user_id=callback_data.user_id, field=callback_data.field, page=callback_data.page
    )
    await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
    await bot.send_message(
        ADMIN_ID,
        _with_quit(
            f"Введите количество {_CURRENCY_LABEL[callback_data.field]} для "
            f"{_display_name(data, callback_data.user_id)} (id <code>{callback_data.user_id}</code>)"
        ),
    )
    await callback.answer()


@router.message(StateFilter(AdminForm.users_amount), is_admin)
async def users_amount(message: Message, state: FSMContext) -> None:
    if await _quit_if_requested(message, state):
        return
    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer(_with_quit("❌ Введите целое число."))
        return
    await state.update_data(amount=int(text))
    await state.set_state(AdminForm.users_message)
    await message.answer(_with_quit("Введите сообщение игроку (или «нет», чтобы без него)."))


@router.message(StateFilter(AdminForm.users_message), is_admin)
async def users_message_finish(message: Message, state: FSMContext, bot: Bot) -> None:
    if await _quit_if_requested(message, state):
        return
    text = (message.text or "").strip()
    note = "" if text.lower() in ("нет", "none", "-") else text
    data = await state.get_data()
    await state.clear()

    user_id = int(data["target_user_id"])
    field = data["field"]
    amount = int(data["amount"])
    page = int(data.get("page", 0))

    await run_db(update_currency, user_id, field, amount)
    icon = _CURRENCY_ICON[field]

    try:
        msg = f"🎁 На ваш аккаунт поступило {amount} {icon}"
        if note:
            msg += f"\n{note}"
        await bot.send_message(user_id, msg)
    except Exception as e:  # noqa: BLE001
        logger.error(f"users: не удалось уведомить {user_id}: {e}")

    note_line = f"✅ Начислено {amount} {icon}"
    if note:
        note_line += f"\n💬 {escape(note)}"
    view_text, kb = await _user_view(user_id, page, note=note_line)
    await message.answer(view_text, reply_markup=kb)


@router.callback_query(AdminUsersCB.filter(F.action == "char"), is_admin)
async def users_char(callback: CallbackQuery, callback_data: AdminUsersCB, bot: Bot) -> None:
    if not callback_data.rarity:
        total_counts = await run_db(get_rarity_counts)
        user_counts = await run_db(get_user_rarity_counts, callback_data.user_id)
        text = f"🎴 Выберите редкость для id <code>{callback_data.user_id}</code>"
        await _render_text(
            bot,
            callback,
            text,
            admin_char_rarity_kb(
                callback_data.user_id, callback_data.page, user_counts, total_counts
            ),
        )
        await callback.answer()
        return

    ok = await _render_admin_char(
        bot, callback, callback_data.user_id, callback_data.page, callback_data.rarity, 0
    )
    if not ok:
        await callback.answer("Нет персонажей этой редкости", show_alert=True)
        return
    await callback.answer()


@router.callback_query(AdminUsersCB.filter(F.action == "charnav"), is_admin)
async def users_char_nav(callback: CallbackQuery, callback_data: AdminUsersCB, bot: Bot) -> None:
    ok = await _render_admin_char(
        bot,
        callback,
        callback_data.user_id,
        callback_data.page,
        callback_data.rarity,
        callback_data.cpage,
    )
    if not ok:
        await callback.answer("Нет персонажей", show_alert=True)
        return
    await callback.answer()


@router.callback_query(AdminUsersCB.filter(F.action == "charpick"), is_admin)
async def users_char_pick(callback: CallbackQuery, callback_data: AdminUsersCB, bot: Bot) -> None:
    base = await run_db(get_character_by_id, callback_data.char_id)
    if base is None:
        await callback.answer("Персонаж не найден", show_alert=True)
        return

    status, level = await run_db(
        grant_character_or_level, callback_data.user_id, callback_data.char_id
    )

    if status == "max":
        await callback.answer("У персонажа уже максимальный уровень", show_alert=True)
    else:
        card = await run_db(get_user_character, callback_data.user_id, callback_data.char_id) or base
        title = "🎁 Вам выдан персонаж:" if status == "new" else "🎁 Ваш персонаж улучшен:"
        try:
            await send_character_card(
                bot, callback_data.user_id, card.image_path, character_caption(card, title=title)
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"users: не удалось уведомить {callback_data.user_id}: {e}")
        await callback.answer("✅ Выдан" if status == "new" else f"✅ Уровень повышен до {level}")

    await _render_admin_char(
        bot,
        callback,
        callback_data.user_id,
        callback_data.page,
        callback_data.rarity,
        callback_data.cpage,
    )


# ──────────────────────────────────────────────
# /get_id
# ──────────────────────────────────────────────

@router.message(Command("get_id"), is_admin)
async def get_id_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminForm.get_id_username)
    await message.answer(_with_quit("Введите @ пользователя:"))


@router.message(StateFilter(AdminForm.get_id_username), is_admin)
async def get_id_process(message: Message, state: FSMContext) -> None:
    if await _quit_if_requested(message, state):
        return
    username = (message.text or "").strip().lstrip("@")
    user_id = await run_db(get_user_id_by_username, username)
    await state.clear()
    await message.answer(
        f"🆔 <code>{user_id}</code>" if user_id else "❌ Пользователь не найден"
    )


# ──────────────────────────────────────────────
# /user <id> - open a player card (same view as the /users browser)
# ──────────────────────────────────────────────

@router.message(Command("user"), is_admin)
async def user_card(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    raw = parts[1].strip() if len(parts) > 1 else ""
    if not raw.isdigit():
        await message.answer("Использование: <code>/user &lt;id&gt;</code>")
        return
    text, kb = await _user_view(int(raw), 0)
    await message.answer(text, reply_markup=kb)


# ──────────────────────────────────────────────
# /give_char
# ──────────────────────────────────────────────

@router.message(Command("give_char"), is_admin)
async def give_char_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminForm.give_char_id)
    await message.answer(_with_quit("Введите ID персонажа из БД:"))


@router.message(StateFilter(AdminForm.give_char_id), is_admin)
async def give_char_process(message: Message, state: FSMContext, bot: Bot) -> None:
    if await _quit_if_requested(message, state):
        return
    try:
        char_id = int((message.text or "").strip())
    except ValueError:
        await message.answer(_with_quit("❌ ID должен быть числом."))
        return

    card = await run_db(get_character_by_id, char_id)
    if card is None:
        await message.answer(_with_quit("❌ Персонаж с таким ID не найден."))
        return

    await state.clear()
    await send_character_card(
        bot, message.chat.id, card.image_path, character_caption(card, title="🎴 Выдан персонаж:")
    )
    await run_db(grant_character, message.from_user.id, char_id)


# ──────────────────────────────────────────────
# /admin_commands
# ──────────────────────────────────────────────

ADMIN_COMMANDS_TEXT = (
    "<b>🛠 Админ-команды</b>\n"
    "/admin_commands - этот список\n"
    "/get_id - узнать ID по @username\n"
    "/sync_chars - синк каталога персонажей из R2 + проверка артов\n"
    "/add_char - добавить персонажа (арт + статы) прямо через бота\n"
    "/edit_char &lt;имя&gt; - изменить арт/имя/статы/тип/пол персонажа (по русскому имени)\n"
    "/users - браузер игроков: карточки, выдача валюты и персонажей\n"
    "/user &lt;id&gt; - окно конкретного игрока (то же, что в браузере)\n"
    "/donations - неразобранные донаты (ручной зачёт/отклонение)\n"
    "/da_auth - авторизовать DonationAlerts (токен для API)\n"
    "/da_status - состояние токена DonationAlerts\n"
    "/give_char - выдать себе персонажа по ID из БД\n"
    "/give_all - выдать валюту ВСЕМ (например «500» = осколки, «500 spins», «500 super_spins»)\n"
    "/broadcast - отправить сообщение всем игрокам\n"
    "/clear_pvp - отменить все текущие PvP-бои (рейтинг не меняется)\n"
    "/clear_pve - отменить все текущие PvE-бои (рейтинг не меняется)\n"
    "/reset_bot - сброс рейтинга/переменных бота + отмена PvE-боёв\n"
    "/reset_arena - хард-ресет рейтинга всех игроков + отмена PvP-боёв\n"
    "/season_end - закрыть сезон арены: награды + soft reset + новый сезон\n"
    "/full_reset - полная отчистка прогресса всех игроков\n"
    "/cfr_stats - нагрузка CFR, рейтинг и винрейт бота\n"
    "/cfr_selftest - проверка CFR против случайной политики\n"
    "/test_battle - тестовый бой против AI (рейтинги не затрагиваются)\n"
    "Все опасные команды требуют ввода фразы подтверждения."
)


# ──────────────────────────────────────────────
# /sync_chars - pull the catalog from R2 + verify card art
# ──────────────────────────────────────────────

async def _check_card_images(entries: list[dict]) -> list[dict]:
    """GET each card URL (1 byte) and return the ones that aren't reachable."""
    failures: list[dict] = []
    timeout = aiohttp.ClientTimeout(total=15)
    headers = {"User-Agent": "megaverse-bot/1.0", "Range": "bytes=0-0"}
    sem = asyncio.Semaphore(12)

    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async def check(entry: dict) -> None:
            async with sem:
                try:
                    async with session.get(entry["url"]) as response:
                        if response.status not in (200, 206):
                            failures.append({**entry, "reason": f"HTTP {response.status}"})
                except Exception as exc:  # noqa: BLE001
                    failures.append({**entry, "reason": type(exc).__name__})

        await asyncio.gather(*(check(entry) for entry in entries))
    return failures


@router.message(Command("sync_chars"), is_admin)
async def sync_chars_cmd(message: Message) -> None:
    await message.answer("🔄 Синхронизирую каталог из R2 и проверяю арты...")
    try:
        summary = await run_db(sync_characters)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"sync_chars failed: {exc}")
        await message.answer(f"❌ Не удалось синхронизировать каталог: {exc}")
        return

    entries: list[dict] = []
    malformed: list[str] = []
    for char in summary["characters"]:
        filename, rarity = char.get("filename"), char.get("rarity")
        name = char.get("name_en", "?")
        if not filename or not rarity:
            malformed.append(f"• {name} - нет filename/rarity")
            continue
        path = f"{rarity}/{filename}"
        entries.append({"name": name, "path": path, "url": card_image(path)})

    failures = await _check_card_images(entries)

    lines = [f"✅ Синк: {summary['total']} персонажей, удалено устаревших: {summary['removed']}"]
    if malformed:
        lines.append(f"\n⚠️ Кривые записи в JSON: {len(malformed)}")
        lines += malformed[:15]
        if len(malformed) > 15:
            lines.append(f"… и ещё {len(malformed) - 15}")
    if failures:
        lines.append(f"\n🖼 Битые/отсутствующие арты: {len(failures)}/{len(entries)}")
        for fail in failures[:20]:
            lines.append(f"• {fail['name']} - {fail['path']} ({fail['reason']})")
        if len(failures) > 20:
            lines.append(f"… и ещё {len(failures) - 20}")
    else:
        lines.append(f"\n🖼 Все арты на месте ({len(entries)} шт).")
    await message.answer("\n".join(lines))


@router.message(Command("admin_commands"), is_admin)
async def admin_commands(message: Message) -> None:
    await message.answer(ADMIN_COMMANDS_TEXT)


# ──────────────────────────────────────────────
# /give_all
# ──────────────────────────────────────────────

@router.message(Command("give_all"), is_admin)
async def give_all_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminForm.all_currency_amount)
    await message.answer(
        _with_quit(
            "Введите сумму и валюту:\n"
            "«500» - осколки (по умолчанию)\n"
            "«500 spins» - крутки\n"
            "«500 super_spins» - супер-крутки"
        )
    )


@router.message(StateFilter(AdminForm.all_currency_amount), is_admin)
async def give_all_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    if await _quit_if_requested(message, state):
        return
    parts = (message.text or "").split()
    currency = parts[1] if len(parts) > 1 else "shards"
    if currency not in ("shards", "spins", "super_spins"):
        await message.answer(_with_quit("❌ Валюта: shards / spins / super_spins"))
        return
    try:
        amount = int(parts[0])
    except (ValueError, IndexError):
        await message.answer(_with_quit("❌ Введите целое число, например «500 spins»"))
        return

    await state.clear()
    icon = {"shards": "🔮", "spins": "🎴", "super_spins": "🧧"}[currency]
    user_ids = await run_db(get_all_user_ids)
    sent = 0
    for uid in user_ids:
        try:
            await run_db(update_currency, uid, currency, amount)
            await bot.send_message(uid, f"🎁 Вам начислено {amount} {icon}")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:  # noqa: BLE001
            logger.error(f"give_all: не удалось начислить {uid}: {e}")
    await message.answer(f"✅ Начислено {amount} {icon} всем ({sent}/{len(user_ids)})")


# ──────────────────────────────────────────────
# /broadcast
# ──────────────────────────────────────────────

@router.message(Command("broadcast"), is_admin)
async def broadcast_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminForm.broadcast_text)
    await message.answer(
        _with_quit("Отправьте сообщение рассылки - текст и/или прикреплённые изображения.")
    )


@router.message(StateFilter(AdminForm.broadcast_text), is_admin)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if await _quit_if_requested(message, state):
        return
    has_media = bool(
        message.photo or message.video or message.document or message.animation
        or message.audio or message.voice or message.sticker
    )
    if not has_media and not (message.text or message.caption or "").strip():
        await message.answer(_with_quit("❌ Пришлите текст и/или изображение."))
        return

    await state.clear()
    user_ids = await run_db(get_all_user_ids)
    sent = 0
    for uid in user_ids:
        try:
            # copy_message keeps the text, formatting and attached media (photo)
            await bot.copy_message(
                chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:  # noqa: BLE001
            logger.error(f"broadcast: не удалось отправить {uid}: {e}")
    await message.answer(f"✅ Рассылка завершена: {sent}/{len(user_ids)}")


# ──────────────────────────────────────────────
# Опасные команды с подтверждением фразой
# ──────────────────────────────────────────────

async def _ask_confirm(message: Message, state: FSMContext, action: str, phrase: str, prompt: str) -> None:
    await state.set_state(AdminForm.confirm_action)
    await state.update_data(action=action, phrase=phrase)
    await message.answer(
        _with_quit(f"{prompt}\n\nНапишите <b>{phrase}</b> для подтверждения.")
    )


@router.message(Command("clear_pvp"), is_admin)
async def clear_pvp_start(message: Message, state: FSMContext) -> None:
    await _ask_confirm(
        message, state, "clear_pvp", CLEAR_PVP_PHRASE,
        "⚠️ Отменить все текущие PvP-бои? Рейтинг не изменится.",
    )


@router.message(Command("clear_pve"), is_admin)
async def clear_pve_start(message: Message, state: FSMContext) -> None:
    await _ask_confirm(
        message, state, "clear_pve", CLEAR_PVE_PHRASE,
        "⚠️ Отменить все текущие PvE-бои? Рейтинг не изменится.",
    )


@router.message(Command("reset_bot"), is_admin)
async def reset_bot_start(message: Message, state: FSMContext) -> None:
    await _ask_confirm(
        message, state, "reset_bot", RESET_BOT_PHRASE,
        "⚠️ Сброс бота: рейтинг/rd/vol/победы + отмена всех PvE-боёв.",
    )


@router.message(Command("reset_arena"), is_admin)
async def reset_arena_start(message: Message, state: FSMContext) -> None:
    await _ask_confirm(
        message, state, "reset_arena", RESET_ARENA_PHRASE,
        "⚠️ Хард-ресет арены: рейтинг ВСЕХ игроков → 1000 "
        "(rd/vol/матчи/победы сброшены) + отмена всех PvP-боёв.",
    )


@router.message(Command("season_end"), is_admin)
async def season_end_start(message: Message, state: FSMContext) -> None:
    await _ask_confirm(
        message, state, "season_end", SEASON_END_PHRASE,
        "🏁 Закрыть сезон: награды, soft-reset и новый сезон.",
    )


@router.message(Command("full_reset"), is_admin)
async def full_reset_start(message: Message, state: FSMContext) -> None:
    await _ask_confirm(
        message, state, "full_reset", FULL_RESET_PHRASE,
        "⚠️ Полная отчистка: очки, рейтинг, осколки, крутки, персонажи, инвентарь, "
        f"колоды и статус арены.\nАккаунты останутся. Круток будет {START_SPINS}.",
    )


@router.message(StateFilter(AdminForm.confirm_action), is_admin)
async def confirm_action(message: Message, state: FSMContext, bot: Bot) -> None:
    if await _quit_if_requested(message, state):
        return
    data = await state.get_data()
    action = data.get("action")
    phrase = data.get("phrase", "")
    if (message.text or "").strip() != phrase:
        await state.clear()
        await message.answer("❌ Отменено: фраза подтверждения не совпала")
        return
    await state.clear()

    if action == "clear_pvp":
        res = await reset_active_matches(bot, only="pvp")
        await message.answer(f"✅ PvP-бои отменены: {res['matches']}, уведомлено: {res['notified']}")
    elif action == "clear_pve":
        res = await reset_active_matches(bot, only="pve")
        await message.answer(f"✅ PvE-бои отменены: {res['matches']}, уведомлено: {res['notified']}")
    elif action == "reset_bot":
        await run_db(reset_bot_stats)
        res = await reset_active_matches(bot, only="pve")
        await message.answer(
            f"✅ Бот сброшен (рейтинг 1000). PvE-бои отменены: {res['matches']}, уведомлено: {res['notified']}"
        )
    elif action == "reset_arena":
        users = await run_db(reset_all_ratings)
        res = await reset_active_matches(bot, only="pvp")
        await message.answer(
            f"✅ Арена сброшена: рейтинг обнулён у {users} игроков, "
            f"PvP-бои отменены: {res['matches']}, уведомлено: {res['notified']}"
        )
    elif action == "season_end":
        from features.arena.seasons import run_season_close

        await message.answer("🏁 Закрываю сезон: награды, soft-reset, новый сезон...")
        try:
            result = await run_season_close(bot)
            await message.answer(f"✅ Сезон закрыт. Награждено игроков: {result['count']}")
        except Exception as e:  # noqa: BLE001
            await message.answer(f"❌ Ошибка: {e}")
    elif action == "full_reset":
        count = await run_db(reset_all_progress)
        await message.answer(f"✅ Полная отчистка выполнена. Аккаунтов обнулено: {count}")
    else:
        await message.answer("❓ Неизвестное действие")


# ──────────────────────────────────────────────
# /cfr_stats
# ──────────────────────────────────────────────

@router.message(Command("cfr_stats"), is_admin)
async def show_cfr_stats(message: Message) -> None:
    limits = (
        f"\nЛимиты: решений одновременно ≤ {CFR_MAX_CONCURRENCY or '∞'}, "
        f"активных PvE ≤ {CFR_MAX_ACTIVE or '∞'}"
    )
    bot_line = await run_db(bot_winrate_line)
    await message.answer(cfr_stats.report(active_matches=cfr_player.active_count()) + bot_line + limits)


@router.message(Command("cfr_selftest"), is_admin)
async def run_cfr_selftest(message: Message) -> None:
    if not cfr_player.CFR_AVAILABLE:
        await message.answer("🤖 CFR недоступен (нет _cote_cfr/таблицы)")
        return
    await message.answer("🤖 Self-test: CFR против random, 5 игр...")
    from features.arena.selftest import run_games

    result = await asyncio.to_thread(run_games, 5, random.randrange(1 << 30))
    await message.answer(
        f"CFR vs random: {result['wins']}/{result['games']} побед, "
        f"в среднем {result['avg_turns']:.0f} ходов"
    )



