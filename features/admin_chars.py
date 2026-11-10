"""Admin: add / edit characters through the bot (writes art to R2 + updates the catalog).

Requires R2 write credentials (R2_ACCESS_KEY_ID/SECRET/BUCKET/ENDPOINT).
The catalog is the source of truth: we edit ``characters.json`` in R2, then apply
it to the DB via ``seed.apply_catalog`` (no re-fetch, avoids CDN cache).
"""

import asyncio
import re
from datetime import datetime, timezone
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import R2_WRITE_ENABLED
from core.callbacks import AdminCharCB
from core.keyboards import RARITY_LABELS
from core.logger import logger
from core.texts import RARITY_EMOJI, RARITY_ORDER, TYPE_EMOJI
from core.utils import run_db
from features.admin import _quit_if_requested, _with_quit, is_admin
from seed import apply_catalog
from services import r2

router = Router()

GENDER_LABELS = {
    "male": "♂ мужской",
    "female": "♀ женский",
    "plural": "👥 дуо",
    "unknown": "❔ неизвестный",
}

_EXT_CT = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "mp4": "video/mp4",
    "webm": "video/webm",
    "mov": "video/quicktime",
}
_CT_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "video/webm": "webm",
}

_catalog_lock = asyncio.Lock()


class CharForm(StatesGroup):
    add_rarity = State()
    add_media = State()
    add_name_en = State()
    add_name_ru = State()
    add_type = State()
    add_gender = State()
    add_health = State()
    add_attack = State()
    add_confirm = State()
    edit_value = State()
    edit_media = State()


# ── helpers ──

def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return slug or "char"


def _next_id(data: dict) -> int:
    ids = [c["id"] for c in data["characters"] if isinstance(c.get("id"), int)]
    return max(ids, default=0) + 1


def _find(data: dict, name_en: str) -> dict | None:
    low = name_en.lower()
    return next((c for c in data["characters"] if c.get("name_en", "").lower() == low), None)


def _find_all_by_ru(data: dict, name_ru: str) -> list[dict]:
    low = name_ru.strip().lower()
    return [c for c in data["characters"] if str(c.get("name_ru", "")).strip().lower() == low]


def _find_by_id(data: dict, char_id: int) -> dict | None:
    return next((c for c in data["characters"] if c.get("id") == char_id), None)


def _unique_filename(data: dict, slug: str, ext: str, taken: set[str] | None = None) -> str:
    """A filename that has never been used before.

    `taken` must include the bucket's filenames (see `r2.list_filenames`): the
    catalog forgets the art a previous edit replaced, so the catalog alone is
    not enough to tell whether a name is free.

    Replacing art gets a UTC timestamp instead of a version number: files are
    uploaded with a year-long `immutable` Cache-Control, so the CDN and Telegram
    keep serving the old bytes for any URL that was ever used. A counter can be
    rewound (e.g. by deleting a file by hand), a timestamp cannot.
    """
    used = {c.get("filename") for c in data["characters"] if c.get("filename")}
    used |= taken or set()
    base = f"{slug}.{ext}"
    if base not in used:
        return base
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = f"{slug}_{stamp}.{ext}"
    i = 2
    while name in used:
        name = f"{slug}_{stamp}-{i}.{ext}"
        i += 1
    return name


def _media_info(message: Message):
    """(file_id, ext, content_type) for the attached media, or None."""
    if message.document:
        doc = message.document
        ext = doc.file_name.rsplit(".", 1)[1].lower() if doc.file_name and "." in doc.file_name else ""
        content_type = doc.mime_type or _EXT_CT.get(ext, "application/octet-stream")
        return doc.file_id, ext or _CT_EXT.get(content_type, "bin"), content_type
    if message.photo:
        return message.photo[-1].file_id, "jpg", "image/jpeg"
    if message.video:
        return message.video.file_id, "mp4", "video/mp4"
    if message.animation:
        ext = "gif"
        if message.animation.file_name and "." in message.animation.file_name:
            ext = message.animation.file_name.rsplit(".", 1)[1].lower()
        return message.animation.file_id, ext, _EXT_CT.get(ext, "image/gif")
    return None


def _draft_preview(d: dict) -> str:
    return (
        "🆕 <b>Новый персонаж</b>\n"
        f"name_en: <code>{escape(d['name_en'])}</code>\n"
        f"name_ru: {escape(d['name_ru'])}\n"
        f"редкость: {RARITY_EMOJI[d['rarity']]} {RARITY_LABELS[d['rarity']]}\n"
        f"тип: {TYPE_EMOJI.get(d.get('type', 0), '🚫')} {d.get('type', 0)}\n"
        f"пол: {GENDER_LABELS.get(d.get('gender', 'unknown'), d.get('gender'))}\n"
        f"❤️ HP: {d['health']}\n"
        f"💪 ATK: {d['attack']}\n"
        f"файл: <code>{_slug(d['name_en'])}.{d['ext']}</code>"
    )


def _edit_text(entry: dict) -> str:
    return (
        f"✏️ <b>{escape(entry['name_en'])}</b> (id <code>{entry.get('id')}</code>)\n"
        f"name_ru: {escape(entry.get('name_ru', ''))}\n"
        f"редкость: {entry.get('rarity')}\n"
        f"тип: {entry.get('type')} · пол: {entry.get('gender')}\n"
        f"❤️ {entry.get('health')} · 💪 {entry.get('attack')}\n"
        f"файл: <code>{entry.get('filename')}</code>"
    )


# ── keyboards ──

def _rarity_kb():
    builder = InlineKeyboardBuilder()
    for rarity in RARITY_ORDER:
        builder.button(
            text=f"{RARITY_EMOJI[rarity]} {RARITY_LABELS[rarity]}",
            callback_data=AdminCharCB(action="rarity", value=rarity),
        )
    builder.button(text="❌ Отмена", callback_data=AdminCharCB(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def _type_kb():
    builder = InlineKeyboardBuilder()
    for t in (1, 2, 3, 4):
        builder.button(text=f"{TYPE_EMOJI[t]} тип {t}", callback_data=AdminCharCB(action="type", value=str(t)))
    builder.button(text="❌ Отмена", callback_data=AdminCharCB(action="cancel"))
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def _gender_kb():
    builder = InlineKeyboardBuilder()
    for gender, label in GENDER_LABELS.items():
        builder.button(text=label, callback_data=AdminCharCB(action="gender", value=gender))
    builder.button(text="❌ Отмена", callback_data=AdminCharCB(action="cancel"))
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def _confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Создать", callback_data=AdminCharCB(action="confirm", value="yes"))
    builder.button(text="❌ Отмена", callback_data=AdminCharCB(action="confirm", value="no"))
    builder.adjust(2)
    return builder.as_markup()


def _edit_kb():
    builder = InlineKeyboardBuilder()
    for field, label in (
        ("art", "🖼 Арт"),
        ("name", "📝 Имя (ru)"),
        ("type", "🎭 Тип"),
        ("gender", "⚧ Пол"),
        ("health", "❤️ HP"),
        ("attack", "💪 ATK"),
    ):
        builder.button(text=label, callback_data=AdminCharCB(action="editfield", value=field))
    builder.button(text="❌ Закрыть", callback_data=AdminCharCB(action="cancel"))
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def _pick_kb(matches: list[dict]):
    builder = InlineKeyboardBuilder()
    for char in matches:
        builder.button(
            text=f"{RARITY_EMOJI.get(char.get('rarity', ''), '')} {char.get('name_en')} · id {char.get('id')}",
            callback_data=AdminCharCB(action="editpick", value=str(char.get("id"))),
        )
    builder.button(text="❌ Отмена", callback_data=AdminCharCB(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


# ── add flow ──

@router.message(Command("add_char"), is_admin)
async def add_char_start(message: Message, state: FSMContext) -> None:
    if not R2_WRITE_ENABLED:
        await message.answer("❌ Запись в R2 не настроена (R2_ACCESS_KEY_ID / SECRET / BUCKET / ENDPOINT).")
        return
    await state.set_state(CharForm.add_rarity)
    await message.answer("Выберите редкость нового персонажа:", reply_markup=_rarity_kb())


@router.callback_query(AdminCharCB.filter(F.action == "rarity"), is_admin)
async def add_char_rarity(callback: CallbackQuery, callback_data: AdminCharCB, state: FSMContext) -> None:
    await state.update_data(rarity=callback_data.value)
    await state.set_state(CharForm.add_media)
    await callback.message.edit_text(
        f"Редкость: {RARITY_EMOJI[callback_data.value]} {RARITY_LABELS[callback_data.value]}\n\n"
        "Пришлите арт - лучше <b>файлом</b> (Telegram сжимает «фото»). Можно фото/видео/гиф."
    )
    await callback.answer()


@router.message(StateFilter(CharForm.add_media), is_admin)
async def add_char_media(message: Message, state: FSMContext) -> None:
    if await _quit_if_requested(message, state):
        return
    info = _media_info(message)
    if info is None:
        await message.answer(_with_quit("Пришлите изображение/видео/файл."))
        return
    file_id, ext, content_type = info
    await state.update_data(file_id=file_id, ext=ext, content_type=content_type)
    await state.set_state(CharForm.add_name_en)
    await message.answer(
        _with_quit("Введите <b>английское имя</b> (<code>name_en</code>) - основа имени файла.")
    )


@router.message(StateFilter(CharForm.add_name_en), is_admin)
async def add_char_name_en(message: Message, state: FSMContext) -> None:
    if await _quit_if_requested(message, state):
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer(_with_quit("Введите имя текстом."))
        return
    await state.update_data(name_en=name)
    await state.set_state(CharForm.add_name_ru)
    await message.answer(_with_quit("Введите <b>русское имя</b> (<code>name_ru</code>)."))


@router.message(StateFilter(CharForm.add_name_ru), is_admin)
async def add_char_name_ru(message: Message, state: FSMContext) -> None:
    if await _quit_if_requested(message, state):
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer(_with_quit("Введите имя текстом."))
        return
    await state.update_data(name_ru=name)
    await state.set_state(CharForm.add_type)
    await message.answer("Выберите тип:", reply_markup=_type_kb())


@router.callback_query(AdminCharCB.filter(F.action == "type"), is_admin)
async def add_char_type(callback: CallbackQuery, callback_data: AdminCharCB, state: FSMContext) -> None:
    await state.update_data(type=int(callback_data.value))
    await state.set_state(CharForm.add_gender)
    await callback.message.edit_text("Выберите пол:", reply_markup=_gender_kb())
    await callback.answer()


@router.callback_query(AdminCharCB.filter(F.action == "gender"), is_admin)
async def add_char_gender(callback: CallbackQuery, callback_data: AdminCharCB, state: FSMContext) -> None:
    await state.update_data(gender=callback_data.value)
    await state.set_state(CharForm.add_health)
    await callback.message.edit_text(_with_quit("Введите <b>HP</b> (кратно 100, напр. 6000)."))
    await callback.answer()


@router.message(StateFilter(CharForm.add_health), is_admin)
async def add_char_health(message: Message, state: FSMContext) -> None:
    if await _quit_if_requested(message, state):
        return
    try:
        health = int((message.text or "").strip())
    except ValueError:
        await message.answer(_with_quit("Введите целое число (кратно 100)."))
        return
    await state.update_data(health=health)
    await state.set_state(CharForm.add_attack)
    await message.answer(_with_quit("Введите <b>ATK</b> (кратно 100, напр. 2000)."))


@router.message(StateFilter(CharForm.add_attack), is_admin)
async def add_char_attack(message: Message, state: FSMContext) -> None:
    if await _quit_if_requested(message, state):
        return
    try:
        attack = int((message.text or "").strip())
    except ValueError:
        await message.answer(_with_quit("Введите целое число (кратно 100)."))
        return
    await state.update_data(attack=attack)
    await state.set_state(CharForm.add_confirm)
    data = await state.get_data()
    await message.answer(_draft_preview(data), reply_markup=_confirm_kb())


@router.callback_query(AdminCharCB.filter(F.action == "confirm"), is_admin)
async def add_char_confirm(callback: CallbackQuery, callback_data: AdminCharCB, state: FSMContext, bot: Bot) -> None:
    if callback_data.value != "yes":
        await state.clear()
        await callback.message.edit_text("Отменено.")
        await callback.answer()
        return
    data = await state.get_data()
    await callback.answer("Загружаю в R2...")
    try:
        entry = await _create_character(bot, data)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"add_char failed: {exc}")
        await state.clear()
        await callback.message.edit_text(f"❌ Ошибка: {escape(str(exc))}")
        return
    await state.clear()
    await callback.message.edit_text(
        f"✅ Добавлен <b>{escape(entry['name_en'])}</b>\n"
        f"id <code>{entry['id']}</code> · файл <code>{entry['filename']}</code>"
    )


async def _create_character(bot: Bot, data: dict) -> dict:
    async with _catalog_lock:
        catalog = await run_db(r2.load_catalog)
        bucket_names = set(await run_db(r2.list_filenames))
        filename = _unique_filename(catalog, _slug(data["name_en"]), data["ext"], bucket_names)
        relative = f"{data['rarity']}/{filename}"
        buffer = await bot.download(data["file_id"])
        await run_db(r2.put_bytes, relative, buffer.getvalue(), data["content_type"])

        entry = {
            "id": _next_id(catalog),
            "filename": filename,
            "rarity": data["rarity"],
            "name_en": data["name_en"],
            "name_ru": data["name_ru"],
            "type": data.get("type", 0),
            "health": data["health"],
            "attack": data["attack"],
            "gender": data.get("gender", "unknown"),
        }
        catalog["characters"].append(entry)
        await run_db(r2.save_catalog, catalog)
        await run_db(apply_catalog, catalog)
        return entry


# ── edit flow ──

@router.message(Command("edit_char"), is_admin)
async def edit_char_start(message: Message, state: FSMContext) -> None:
    if not R2_WRITE_ENABLED:
        await message.answer("❌ Запись в R2 не настроена.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: <code>/edit_char &lt;русское имя&gt;</code>")
        return
    name = parts[1].strip()
    catalog = await run_db(r2.load_catalog)
    matches = _find_all_by_ru(catalog, name)
    if not matches:
        await message.answer(f"❌ «{escape(name)}» не найден. Введи русское имя как в инвентаре.")
        return
    if len(matches) > 1:
        await message.answer(
            f"Найдено {len(matches)} персонажей с именем «{escape(name)}». Выбери, кого редактировать:",
            reply_markup=_pick_kb(matches),
        )
        return
    entry = matches[0]
    await state.update_data(edit_name=entry["name_en"], edit_label=entry.get("name_ru", entry["name_en"]))
    await message.answer(_edit_text(entry), reply_markup=_edit_kb())


@router.callback_query(AdminCharCB.filter(F.action == "editpick"), is_admin)
async def edit_char_pick(callback: CallbackQuery, callback_data: AdminCharCB, state: FSMContext) -> None:
    try:
        char_id = int(callback_data.value)
    except (TypeError, ValueError):
        await callback.answer("Ошибка выбора", show_alert=True)
        return
    catalog = await run_db(r2.load_catalog)
    entry = _find_by_id(catalog, char_id)
    if entry is None:
        await callback.answer("Персонаж не найден", show_alert=True)
        return
    await state.update_data(edit_name=entry["name_en"], edit_label=entry.get("name_ru", entry["name_en"]))
    await callback.message.edit_text(_edit_text(entry), reply_markup=_edit_kb())
    await callback.answer()


@router.callback_query(AdminCharCB.filter(F.action == "editfield"), is_admin)
async def edit_char_field(callback: CallbackQuery, callback_data: AdminCharCB, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("edit_name"):
        await callback.answer("Начните заново: /edit_char <русское имя>", show_alert=True)
        return
    field = callback_data.value
    await state.update_data(edit_field=field)
    if field == "art":
        await state.set_state(CharForm.edit_media)
        await callback.message.edit_text(_with_quit("Пришлите новый арт (лучше файлом)."))
    else:
        await state.set_state(CharForm.edit_value)
        prompts = {
            "name": "Введите новое русское имя (name_ru).",
            "type": "Введите тип: 1, 2, 3 или 4.",
            "gender": "Введите пол: male / female / plural / unknown.",
            "health": "Введите новый HP (кратно 100).",
            "attack": "Введите новый ATK (кратно 100).",
        }
        await callback.message.edit_text(_with_quit(prompts[field]))
    await callback.answer()


@router.message(StateFilter(CharForm.edit_value), is_admin)
async def edit_char_value(message: Message, state: FSMContext) -> None:
    if await _quit_if_requested(message, state):
        return
    data = await state.get_data()
    name_en, field = data.get("edit_name"), data.get("edit_field")
    raw = (message.text or "").strip()
    if not name_en or not field:
        await state.clear()
        await message.answer("Сессия истекла, начните заново: /edit_char &lt;русское имя&gt;")
        return

    if field == "name":
        update = {"name_ru": raw}
    elif field == "type":
        if raw not in ("1", "2", "3", "4"):
            await message.answer(_with_quit("Тип - 1, 2, 3 или 4."))
            return
        update = {"type": int(raw)}
    elif field == "gender":
        if raw not in GENDER_LABELS:
            await message.answer(_with_quit("Пол: male / female / plural / unknown."))
            return
        update = {"gender": raw}
    elif field in ("health", "attack"):
        try:
            update = {field: int(raw)}
        except ValueError:
            await message.answer(_with_quit("Введите целое число (кратно 100)."))
            return
    else:
        await state.clear()
        await message.answer("Неизвестное поле.")
        return

    try:
        await _update_character(name_en, update)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"edit_char failed: {exc}")
        await message.answer(f"❌ Ошибка: {escape(str(exc))}")
        return
    await state.clear()
    label = data.get("edit_label", name_en)
    await message.answer(f"✅ Обновлено: <b>{escape(label)}</b> → {escape(field)} = {escape(raw)}")


@router.message(StateFilter(CharForm.edit_media), is_admin)
async def edit_char_media(message: Message, state: FSMContext, bot: Bot) -> None:
    if await _quit_if_requested(message, state):
        return
    info = _media_info(message)
    if info is None:
        await message.answer(_with_quit("Пришлите изображение/видео/файл."))
        return
    data = await state.get_data()
    name_en = data.get("edit_name")
    if not name_en:
        await state.clear()
        await message.answer("Сессия истекла, начните заново: /edit_char &lt;русское имя&gt;")
        return
    file_id, ext, content_type = info
    await message.answer("Загружаю новый арт...")
    try:
        entry = await _replace_art(name_en, file_id, ext, content_type, bot)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"edit_char art failed: {exc}")
        await message.answer(f"❌ Ошибка: {escape(str(exc))}")
        return
    await state.clear()
    await message.answer(f"✅ Арт обновлён: <code>{entry['filename']}</code>")


async def _update_character(name_en: str, update: dict) -> dict:
    async with _catalog_lock:
        catalog = await run_db(r2.load_catalog)
        entry = _find(catalog, name_en)
        if entry is None:
            raise RuntimeError("персонаж не найден в каталоге")
        entry.update(update)
        await run_db(r2.save_catalog, catalog)
        await run_db(apply_catalog, catalog)
        return entry


async def _replace_art(name_en: str, file_id: str, ext: str, content_type: str, bot: Bot) -> dict:
    async with _catalog_lock:
        catalog = await run_db(r2.load_catalog)
        entry = _find(catalog, name_en)
        if entry is None:
            raise RuntimeError("персонаж не найден в каталоге")
        bucket_names = set(await run_db(r2.list_filenames))
        filename = _unique_filename(catalog, _slug(entry["name_en"]), ext, bucket_names)
        relative = f"{entry['rarity']}/{filename}"
        buffer = await bot.download(file_id)
        await run_db(r2.put_bytes, relative, buffer.getvalue(), content_type)
        entry["filename"] = filename
        await run_db(r2.save_catalog, catalog)
        await run_db(apply_catalog, catalog)
        return entry


# ── cancel ──

@router.callback_query(AdminCharCB.filter(F.action == "cancel"), is_admin)
async def admin_char_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()
