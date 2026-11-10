"""Inline keyboard builders."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import MAX_CHARACTER_LEVEL
from core.callbacks import (
    AdminDonateCB,
    AdminUsersCB,
    CharPageCB,
    DonateCB,
    DonateClaimCB,
    ExchangeCB,
    GachaCB,
    LangCB,
    LevelUpCB,
    MenuCB,
    NoopCB,
    RarityCB,
    ShopCB,
    TopCB,
)
from core.i18n import LANG_LABELS, t
from core.texts import RARITY_EMOJI, RARITY_ORDER, level_cost


def main_menu_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "🏆 Топ"), callback_data=MenuCB(action="top"))
    builder.button(text=t(lang, "🎴 Получить перса"), callback_data=MenuCB(action="gacha"))
    builder.button(text=t(lang, "🎭 Мои персы"), callback_data=MenuCB(action="chars"))
    builder.button(text=t(lang, "👤 Профиль"), callback_data=MenuCB(action="profile"))
    builder.button(text=t(lang, "🔄 Осколки"), callback_data=MenuCB(action="exchange"))
    builder.button(text=t(lang, "💸 Донат"), callback_data=MenuCB(action="donate"))
    builder.button(text=t(lang, "🛒 Магазин"), callback_data=MenuCB(action="shop"))
    builder.button(text=t(lang, "📰 Новости КП"), url="https://t.me/DCOTEFILES")
    builder.button(text=t(lang, "⚔️ Арена"), callback_data=MenuCB(action="arena"))
    builder.adjust(2)
    return builder.as_markup()


def menu_only_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "↩️ В меню"), callback_data=MenuCB(action="main"))
    return builder.as_markup()


def profile_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "🌐 Язык"), callback_data=MenuCB(action="profile_lang"))
    builder.button(text=t(lang, "↩️ В меню"), callback_data=MenuCB(action="main"))
    builder.adjust(1)
    return builder.as_markup()


def language_kb(current: str | None, back: str = "menu") -> InlineKeyboardMarkup:
    """Language picker. `back` decides what the cancel button returns to."""
    builder = InlineKeyboardBuilder()
    for code, label in LANG_LABELS.items():
        mark = "✅ " if code == current else ""
        builder.button(text=f"{mark}{label}", callback_data=LangCB(code=code, back=back))
    if back == "profile":
        builder.button(text=t(current, "↩️ Назад"), callback_data=MenuCB(action="profile"))
    elif back != "start":
        builder.button(text=t(current, "↩️ В меню"), callback_data=MenuCB(action="main"))
    builder.adjust(1)
    return builder.as_markup()


def top_types_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "По очкам 💠"), callback_data=TopCB(kind="points"))
    builder.button(text=t(lang, "По рейтингу 🏆"), callback_data=TopCB(kind="rating"))
    builder.button(text=t(lang, "↩️ В меню"), callback_data=MenuCB(action="main"))
    builder.adjust(1)
    return builder.as_markup()


def spin_menu_kb(has_super: bool, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "🎴 Получить перса"), callback_data=GachaCB(kind="normal"))
    if has_super:
        builder.button(text=t(lang, "🧧 Получить перса"), callback_data=GachaCB(kind="super"))
    builder.button(text=t(lang, "↩️ В меню"), callback_data=MenuCB(action="main"))
    builder.adjust(1)
    return builder.as_markup()


def rarity_menu_kb(
    user_counts: dict, total_counts: dict, has_special: bool, lang: str = "ru"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    labels = {
        "common": "Обычные",
        "rare": "Редкие",
        "epic": "Эпические",
        "mythic": "Мифические",
        "legendary": "Легендарные",
    }
    for rarity, label in labels.items():
        builder.button(
            text=f"{RARITY_EMOJI[rarity]} {t(lang, label)} {user_counts.get(rarity, 0)}/{total_counts.get(rarity, 0)}",
            callback_data=RarityCB(rarity=rarity),
        )
    if has_special:
        builder.button(
            text=f"{RARITY_EMOJI['special']} {t(lang, 'Специальные')} {user_counts.get('special', 0)}",
            callback_data=RarityCB(rarity="special"),
        )
    builder.button(text=t(lang, "↩️ В меню"), callback_data=MenuCB(action="main"))
    builder.adjust(1)
    return builder.as_markup()


def character_nav_kb(
    *,
    char_id: int,
    rarity: str,
    page: int,
    total_pages: int,
    level: int,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    # Row 1: back / page counter / forward (wrap-around "infinite" paging)
    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=CharPageCB(rarity=rarity, page=page - 1).pack()))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=NoopCB().pack()))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=CharPageCB(rarity=rarity, page=page + 1).pack()))
    builder.row(*nav)

    # Row 2: upgrade to next level (specials level up only in the shop)
    if level >= MAX_CHARACTER_LEVEL:
        builder.row(
            InlineKeyboardButton(
                text=t(lang, "👑 Максимальный уровень ({level})", level=MAX_CHARACTER_LEVEL),
                callback_data=NoopCB().pack(),
            )
        )
    elif rarity == "special":
        builder.row(InlineKeyboardButton(text=t(lang, "🛒 Только в магазине"), callback_data=NoopCB().pack()))
    else:
        cost = level_cost(rarity, level)
        builder.row(
            InlineKeyboardButton(
                text=t(lang, "⬆️ Улучшить до Lv.{level} — {cost}🔮", level=level + 1, cost=cost),
                callback_data=LevelUpCB(char_id=char_id, rarity=rarity, page=page).pack(),
            )
        )

    # Rows 3-4: navigation
    builder.row(InlineKeyboardButton(text=t(lang, "↩️ В меню редкостей"), callback_data=MenuCB(action="chars").pack()))
    builder.row(InlineKeyboardButton(text=t(lang, "🏠 В меню"), callback_data=MenuCB(action="main").pack()))
    return builder.as_markup()


def exchange_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    rows = [
        (ExchangeCB(target="spins", count=1), "10🔮 на 1🎴"),
        (ExchangeCB(target="super_spins", count=1), "80🔮 на 1🧧"),
        (ExchangeCB(target="spins", count=5), "50🔮 на 5🎴"),
        (ExchangeCB(target="super_spins", count=5), "400🔮 на 5🧧"),
        (ExchangeCB(target="spins", count=10), "100🔮 на 10🎴"),
        (ExchangeCB(target="super_spins", count=10), "800🔮 на 10🧧"),
        (ExchangeCB(target="spins", count=0), "все🔮 на 🎴"),
        (ExchangeCB(target="super_spins", count=0), "все🔮 на 🧧"),
    ]
    for cb, text in rows:
        builder.button(text=t(lang, text), callback_data=cb)
    builder.button(text=t(lang, "↩️ В меню"), callback_data=MenuCB(action="main"))
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()


def donation_currency_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "🇷🇺 Рубли"), callback_data=DonateCB(action="packs", value="RUB"))
    builder.button(text=t(lang, "🇺🇸 Доллары"), callback_data=DonateCB(action="packs", value="USD"))
    builder.button(text=t(lang, "🇪🇺 Евро"), callback_data=DonateCB(action="packs", value="EUR"))
    builder.button(text=t(lang, "↩️ В меню"), callback_data=MenuCB(action="main"))
    builder.adjust(1)
    return builder.as_markup()


def donation_packs_kb(currency: str, lang: str = "ru") -> InlineKeyboardMarkup:
    from services.donations import fmt_minor, packs

    rows: list[list[InlineKeyboardButton]] = []
    items = sorted(packs(currency).items())
    for start in range(0, len(items), 2):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{shards}🔮 - {fmt_minor(currency, base_minor)}",
                    callback_data=DonateCB(
                        action="pack", value=f"{currency}_{base_minor}"
                    ).pack(),
                )
                for base_minor, shards in items[start:start + 2]
            ]
        )
    rows.append(
        [InlineKeyboardButton(text=t(lang, "⬅️ Назад"), callback_data=MenuCB(action="donate").pack())]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def donation_order_kb(lang: str, order_id: int, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "🌐 Открыть страницу доната"), url=url)],
            [
                InlineKeyboardButton(
                    text=t(lang, "❌ Отменить заявку"),
                    callback_data=DonateCB(action="cancel", value=str(order_id)).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "↩️ В меню"), callback_data=MenuCB(action="main").pack()
                )
            ],
        ]
    )


def donation_claim_kb(donation_id: int, order_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "✅ Это мой платёж"),
                    callback_data=DonateClaimCB(
                        donation_id=donation_id, order_id=order_id
                    ).pack(),
                )
            ]
        ]
    )


def admin_donations_kb(items: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"✅ {item['label']} → {item['suggested']}🔮",
                callback_data=AdminDonateCB(
                    action="credit", donation_id=item["id"]
                ).pack(),
            ),
            InlineKeyboardButton(
                text="🚫",
                callback_data=AdminDonateCB(
                    action="ignore", donation_id=item["id"]
                ).pack(),
            ),
        ]
        for item in items
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


RARITY_LABELS = {
    "common": "Обычные",
    "rare": "Редкие",
    "epic": "Эпические",
    "mythic": "Мифические",
    "legendary": "Легендарные",
    "special": "Специальные",
}


def admin_users_list_kb(
    users: list[dict], page: int, total_pages: int, start: int = 1
) -> InlineKeyboardMarkup:
    """User browser list: numbered by place, with points (same order as the top)."""
    builder = InlineKeyboardBuilder()
    for offset, user in enumerate(users):
        name = user["first_name"] or (f"@{user['username']}" if user["username"] else str(user["user_id"]))
        builder.button(
            text=f"{start + offset}. {name[:40]} — {user.get('points') or 0} 💠",
            callback_data=AdminUsersCB(action="user", user_id=user["user_id"], page=page),
        )
    builder.adjust(1)

    nav = []
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=AdminUsersCB(action="list", page=page - 1).pack()))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=NoopCB().pack()))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=AdminUsersCB(action="list", page=page + 1).pack()))
    builder.row(*nav)
    return builder.as_markup()


def admin_user_kb(user_id: int, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Валюта", callback_data=AdminUsersCB(action="currency", user_id=user_id, page=page))
    builder.button(text="🎴 Дать персонажа", callback_data=AdminUsersCB(action="char", user_id=user_id, page=page))
    builder.button(text="↩️ К списку", callback_data=AdminUsersCB(action="list", page=page))
    builder.adjust(1)
    return builder.as_markup()


def admin_user_currency_kb(user_id: int, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for field, label in (
        ("shards", "🔮 Осколки"),
        ("spins", "🎴 Крутки"),
        ("super_spins", "🧧 Супер-крутки"),
    ):
        builder.button(
            text=label,
            callback_data=AdminUsersCB(action="curpick", user_id=user_id, page=page, field=field),
        )
    builder.button(text="↩️ Назад", callback_data=AdminUsersCB(action="user", user_id=user_id, page=page))
    builder.adjust(1)
    return builder.as_markup()


def admin_char_rarity_kb(
    user_id: int, page: int, user_counts: dict, total_counts: dict
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for rarity in RARITY_ORDER:
        total = total_counts.get(rarity, 0)
        if not total:
            continue
        builder.button(
            text=f"{RARITY_EMOJI[rarity]} {RARITY_LABELS[rarity]} {user_counts.get(rarity, 0)}/{total}",
            callback_data=AdminUsersCB(action="char", user_id=user_id, page=page, rarity=rarity),
        )
    builder.button(text="↩️ Назад", callback_data=AdminUsersCB(action="user", user_id=user_id, page=page))
    builder.adjust(1)
    return builder.as_markup()


def admin_char_kb(
    user_id: int,
    page: int,
    rarity: str,
    char_id: int,
    cpage: int,
    total_pages: int,
    owned: bool,
    level: int,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav = []
    if total_pages > 1:
        nav.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=AdminUsersCB(
                    action="charnav", user_id=user_id, page=page, rarity=rarity, cpage=cpage - 1
                ).pack(),
            )
        )
    nav.append(InlineKeyboardButton(text=f"{cpage + 1}/{total_pages}", callback_data=NoopCB().pack()))
    if total_pages > 1:
        nav.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=AdminUsersCB(
                    action="charnav", user_id=user_id, page=page, rarity=rarity, cpage=cpage + 1
                ).pack(),
            )
        )
    builder.row(*nav)
    if owned and level >= MAX_CHARACTER_LEVEL:
        builder.row(
            InlineKeyboardButton(
                text=f"👑 Максимальный уровень ({MAX_CHARACTER_LEVEL})",
                callback_data=NoopCB().pack(),
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="⬆️ Прокачать персонажа" if owned else "🎁 Дать персонажа",
                callback_data=AdminUsersCB(
                    action="charpick", user_id=user_id, page=page, rarity=rarity, char_id=char_id
                ).pack(),
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="↩️ К редкостям",
            callback_data=AdminUsersCB(action="char", user_id=user_id, page=page).pack(),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="👤 К пользователю",
            callback_data=AdminUsersCB(action="user", user_id=user_id, page=page).pack(),
        )
    )
    return builder.as_markup()


def shop_kb(
    day: int, index: int, total: int, char_id: int, state: str, lang: str = "ru"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav = []
    if total > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=ShopCB(action="nav", day=day, index=index - 1).pack()))
    nav.append(InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data=NoopCB().pack()))
    if total > 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=ShopCB(action="nav", day=day, index=index + 1).pack()))
    builder.row(*nav)

    if state == "buy":
        builder.row(
            InlineKeyboardButton(
                text=t(lang, "🛒 Купить"),
                callback_data=ShopCB(action="buy", day=day, index=index, char_id=char_id).pack(),
            )
        )
    elif state == "purchased":
        builder.row(InlineKeyboardButton(text=t(lang, "✅ Куплено"), callback_data=NoopCB().pack()))
    else:  # maxed
        builder.row(
            InlineKeyboardButton(
                text=t(lang, "👑 Максимальный уровень ({level})", level=MAX_CHARACTER_LEVEL),
                callback_data=NoopCB().pack(),
            )
        )
    builder.row(InlineKeyboardButton(text=t(lang, "↩️ В меню"), callback_data=MenuCB(action="main").pack()))
    return builder.as_markup()


def shop_empty_kb(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "↩️ В меню"), callback_data=MenuCB(action="main"))
    return builder.as_markup()
