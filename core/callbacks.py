"""Typed callback-data factories shared across features."""
from aiogram.filters.callback_data import CallbackData


class MenuCB(CallbackData, prefix="menu"):
    action: str  # main | top | gacha | chars | profile | exchange | donate | arena


class TopCB(CallbackData, prefix="top"):
    kind: str  # points | rating


class GachaCB(CallbackData, prefix="gacha"):
    kind: str  # normal | super


class RarityCB(CallbackData, prefix="rarity"):
    rarity: str


class CharPageCB(CallbackData, prefix="page"):
    rarity: str
    page: int


class LevelUpCB(CallbackData, prefix="lvl"):
    char_id: int
    rarity: str
    page: int


class ExchangeCB(CallbackData, prefix="exch"):
    target: str  # spins | super_spins
    count: int  # 0 means "all"


class DonateCB(CallbackData, prefix="don"):
    action: str  # packs | pack | cancel
    value: str = ""  # currency code, or "<CUR>:<base_minor>", or an order id


class DonateClaimCB(CallbackData, prefix="dcl"):
    donation_id: int
    order_id: int


class AdminDonateCB(CallbackData, prefix="adn"):
    action: str  # credit | ignore
    donation_id: int


class AdminUsersCB(CallbackData, prefix="ausr"):
    action: str  # list | user | currency | curpick | char | charnav | charpick
    user_id: int = 0
    page: int = 0  # users list page
    cpage: int = 0  # character page within a rarity
    field: str = ""  # shards | spins | super_spins
    rarity: str = ""
    char_id: int = 0


class AdminCharCB(CallbackData, prefix="achar"):
    action: str  # rarity | type | gender | confirm | cancel | editfield
    value: str = ""


class ShopCB(CallbackData, prefix="shop"):
    action: str  # nav | buy
    day: int = 0
    index: int = 0
    char_id: int = 0


class LangCB(CallbackData, prefix="lang"):
    code: str  # ru | en
    back: str = "menu"  # start | profile | menu


class NoopCB(CallbackData, prefix="noop"):
    pass


# ── Арена ──

class ArenaCB(CallbackData, prefix="ar"):
    action: str  # menu | deck | leagues | about | queue | leave


class DeckCB(CallbackData, prefix="adk"):
    action: str  # slot | clear | rename | nav | star | back
    slot: int = 0
    deck: int = 0


class DeckRarityCB(CallbackData, prefix="adr"):
    rarity: str
    slot: int
    deck: int = 0


class DeckPageCB(CallbackData, prefix="adp"):
    rarity: str
    slot: int
    page: int
    deck: int = 0


class DeckPickCB(CallbackData, prefix="adx"):
    char_id: int
    rarity: str
    slot: int
    page: int
    deck: int = 0


class BattleCB(CallbackData, prefix="ab"):
    action: str  # attack | defend | bonus | switch | switchto | teams | back
    value: int = 0
    token: str = ""
