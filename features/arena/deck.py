"""Arena decks: up to 3 named decks, one is the main (active) - switched inline."""

from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from core.callbacks import ArenaCB, DeckCB, DeckPageCB, DeckPickCB, DeckRarityCB
from core.i18n import t, with_quit
from core.texts import RARITY_ORDER, card_name, character_caption, get_type_char
from core.utils import edit_character_card, run_db, safe_delete_message, send_character_card
from db.queries import (
    clear_deck,
    ensure_decks,
    get_deck,
    get_decks,
    get_main_deck,
    get_owned_characters,
    get_rarity_counts,
    get_user_character,
    get_user_rarity_counts,
    rename_deck,
    set_deck_main,
    set_deck_slot,
)
from features.arena.keyboards import deck_kb, deck_pick_kb, deck_rarity_kb
from features.arena.matchmaking import is_queued
from features.arena.store import MatchStore

router = Router()


class DeckForm(StatesGroup):
    new_name = State()


async def is_user_busy(user_id: int) -> bool:
    if await is_queued(user_id):
        return True
    return await MatchStore().load_for_user(user_id) is not None


async def _show_text(bot: Bot, chat_id: int, message_id: int | None, text: str, markup) -> None:
    if message_id:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup)
            return
        except TelegramBadRequest:
            await safe_delete_message(bot, chat_id, message_id)
    await bot.send_message(chat_id, text, reply_markup=markup)


async def _deck_labels(user_id: int, char_ids: list, lang: str) -> list:
    labels = []
    for char_id in char_ids:
        if char_id is None:
            labels.append(None)
            continue
        card = await run_db(get_user_character, user_id, char_id)
        labels.append(f"{get_type_char(card.type)} {card_name(card, lang)}" if card else t(lang, "Пусто"))
    return labels


async def render_deck(
    bot: Bot, chat_id: int, user_id: int, deck_index: int, message_id: int | None, lang: str = "ru"
) -> None:
    await run_db(ensure_decks, user_id, lang)
    decks = await run_db(get_decks, user_id)
    deck = next((d for d in decks if d["deck_index"] == deck_index), decks[0])
    labels = await _deck_labels(user_id, deck["char_ids"], lang)
    body = [f"{i} - {t(lang, 'Пусто') if label is None else label}" for i, label in enumerate(labels, start=1)]
    text = f"📁<b>{escape(deck['name'])}</b>:\n<blockquote>" + "\n".join(body) + "</blockquote>"
    markup = deck_kb(deck["char_ids"], deck["deck_index"], deck["is_main"], len(decks), lang)
    await _show_text(bot, chat_id, message_id, text, markup)


@router.callback_query(ArenaCB.filter(F.action == "decks"))
async def open_decks(callback: CallbackQuery, bot: Bot, user_id: int, lang: str) -> None:
    if await is_user_busy(user_id):
        await callback.answer(t(lang, "❌ Вы находитесь в битве или в поиске!"), show_alert=True)
        return
    await run_db(ensure_decks, user_id, lang)
    main = await run_db(get_main_deck, user_id, lang)
    await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
    await render_deck(
        bot, callback.message.chat.id, user_id, main["deck_index"] if main else 0, None, lang
    )
    await callback.answer()


@router.callback_query(DeckCB.filter(F.action == "nav"))
async def deck_nav(
    callback: CallbackQuery, callback_data: DeckCB, bot: Bot, user_id: int, lang: str
) -> None:
    await render_deck(
        bot, callback.message.chat.id, user_id, callback_data.deck, callback.message.message_id, lang
    )
    await callback.answer()


@router.callback_query(DeckCB.filter(F.action == "star"))
async def deck_star(
    callback: CallbackQuery, callback_data: DeckCB, bot: Bot, user_id: int, lang: str
) -> None:
    await run_db(set_deck_main, user_id, callback_data.deck)
    deck = await run_db(get_deck, user_id, callback_data.deck)
    await render_deck(
        bot, callback.message.chat.id, user_id, callback_data.deck, callback.message.message_id, lang
    )
    await callback.answer(
        t(lang, "{name} - основная", name=deck["name"] if deck else t(lang, "Колода"))
    )


@router.callback_query(DeckCB.filter(F.action == "rename"))
async def deck_rename(
    callback: CallbackQuery, callback_data: DeckCB, state: FSMContext, lang: str
) -> None:
    await state.set_state(DeckForm.new_name)
    await state.update_data(
        rename_deck=callback_data.deck,
        prompt_message_id=callback.message.message_id,
        lang=lang,
    )
    await callback.message.edit_text(
        with_quit(lang, t(lang, "Введите новое название колоды (до 32 символов)."))
    )
    await callback.answer()


@router.message(StateFilter(DeckForm.new_name))
async def deck_rename_name(message: Message, state: FSMContext, bot: Bot, user_id: int, lang: str) -> None:
    data = await state.get_data()
    deck_index = data.get("rename_deck", 0)
    prompt_message_id = data.get("prompt_message_id")
    text = (message.text or "").strip()
    if text.lower().lstrip("/") == "quit":
        await state.clear()
        await render_deck(bot, message.chat.id, user_id, deck_index, prompt_message_id, lang)
        return
    if not text:
        await message.answer(with_quit(lang, t(lang, "Введите название текстом.")))
        return
    await run_db(rename_deck, user_id, deck_index, text, lang)
    await state.clear()
    await render_deck(bot, message.chat.id, user_id, deck_index, prompt_message_id, lang)


@router.callback_query(DeckCB.filter(F.action == "clear"))
async def deck_clear(
    callback: CallbackQuery, callback_data: DeckCB, bot: Bot, user_id: int, lang: str
) -> None:
    await run_db(clear_deck, user_id, callback_data.deck)
    await render_deck(
        bot, callback.message.chat.id, user_id, callback_data.deck, callback.message.message_id, lang
    )
    await callback.answer()


@router.callback_query(DeckCB.filter(F.action == "back"))
async def deck_back(
    callback: CallbackQuery, callback_data: DeckCB, bot: Bot, user_id: int, lang: str
) -> None:
    await render_deck(
        bot, callback.message.chat.id, user_id, callback_data.deck, callback.message.message_id, lang
    )
    await callback.answer()


@router.callback_query(DeckCB.filter(F.action == "slot"))
async def deck_slot(
    callback: CallbackQuery, callback_data: DeckCB, bot: Bot, user_id: int, lang: str
) -> None:
    user_counts = await run_db(get_user_rarity_counts, user_id)
    total_counts = await run_db(get_rarity_counts)
    await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
    await bot.send_message(
        callback.message.chat.id,
        t(lang, "Выберите редкость:"),
        reply_markup=deck_rarity_kb(
            callback_data.slot, user_counts, total_counts,
            has_special=bool(user_counts.get("special")), deck=callback_data.deck, lang=lang,
        ),
    )
    await callback.answer()


async def _pick_page(
    callback: CallbackQuery,
    bot: Bot,
    user_id: int,
    rarity: str,
    slot: int,
    page: int,
    deck: int,
    edit: bool,
    lang: str,
) -> None:
    characters = await run_db(get_owned_characters, user_id, rarity)
    if not characters:
        await callback.answer(t(lang, "У вас нет персонажей этой редкости"))
        return
    page %= len(characters)
    card = characters[page]
    deck_data = await run_db(get_deck, user_id, deck)
    chosen = deck_data is not None and card.char_id in deck_data["char_ids"]
    markup = deck_pick_kb(
        char_id=card.char_id, rarity=rarity, slot=slot, page=page,
        total_pages=len(characters), chosen=chosen, deck=deck, lang=lang,
    )
    caption = character_caption(card, lang)

    if edit:
        await edit_character_card(
            bot, callback.message.chat.id, callback.message.message_id, card.image_path, caption, markup
        )
    else:
        await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
        await send_character_card(bot, callback.message.chat.id, card.image_path, caption, markup)
    await callback.answer()


@router.callback_query(DeckRarityCB.filter())
async def deck_rarity(
    callback: CallbackQuery, callback_data: DeckRarityCB, bot: Bot, user_id: int, lang: str
) -> None:
    if callback_data.rarity not in RARITY_ORDER:
        await callback.answer(t(lang, "Неизвестная редкость"))
        return
    await _pick_page(
        callback, bot, user_id, callback_data.rarity, callback_data.slot, 0, callback_data.deck,
        edit=False, lang=lang,
    )


@router.callback_query(DeckPageCB.filter())
async def deck_page(
    callback: CallbackQuery, callback_data: DeckPageCB, bot: Bot, user_id: int, lang: str
) -> None:
    await _pick_page(
        callback, bot, user_id, callback_data.rarity, callback_data.slot, callback_data.page,
        callback_data.deck, edit=True, lang=lang,
    )


@router.callback_query(DeckPickCB.filter())
async def deck_pick(
    callback: CallbackQuery, callback_data: DeckPickCB, bot: Bot, user_id: int, lang: str
) -> None:
    deck = await run_db(get_deck, user_id, callback_data.deck)
    if deck is not None and callback_data.char_id in deck["char_ids"]:
        await callback.answer(t(lang, "Персонаж уже выбран"), show_alert=True)
        return
    await run_db(set_deck_slot, user_id, callback_data.deck, callback_data.slot, callback_data.char_id)
    await safe_delete_message(bot, callback.message.chat.id, callback.message.message_id)
    await render_deck(bot, callback.message.chat.id, user_id, callback_data.deck, None, lang)
    await callback.answer()
