"""Shop: daily rotating level-up lots for cards the player already owns.

Each player rolls their own rarities for the day (seeded per user+day) and the
resulting lots - both the card and the rarity - are frozen in `shop_rotation`
on the first view, so nothing shifts until the reset hour. Buying is keyed by
(user, day, char_id) so a lot can't be bought twice.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config import (
    MAX_CHARACTER_LEVEL,
    SHOP_DISCOUNT,
    SHOP_RARITY_WEIGHTS,
    SHOP_RESET_HOUR_UTC,
    SHOP_SLOTS,
    SHOP_SPECIAL_COST,
)
from core.texts import level_cost
from db.models import ShopPurchase, User, UserCharacter
from db.queries import (
    get_owned_characters,
    get_shop_rotation,
    get_user_character,
    save_shop_rotation,
    shop_purchased_char_ids,
)
from db.session import get_session

# highest -> lowest; fallback walks down this list
RARITY_DESC = ["special", "legendary", "mythic", "epic", "rare", "common"]
_RARITY_RANK = {rarity: i for i, rarity in enumerate(RARITY_DESC)}


def shop_day(now: datetime | None = None) -> int:
    """Rotation day as a stable integer (date.toordinal), reset at SHOP_RESET_HOUR_UTC."""
    now = now or datetime.now(timezone.utc)
    shifted = now - timedelta(hours=SHOP_RESET_HOUR_UTC)
    return shifted.date().toordinal()


def seconds_to_reset(now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    shifted = now - timedelta(hours=SHOP_RESET_HOUR_UTC)
    next_reset = (shifted + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(0, int((next_reset - shifted).total_seconds()))


def daily_rarities(user_id: int, day: int) -> list[str]:
    """The player's own rarities for the day (seeded per user+day)."""
    rng = random.Random(f"megaverse-shop:{user_id}:{day}")
    keys = [(rng.random() ** (1.0 / weight), rarity) for rarity, weight in SHOP_RARITY_WEIGHTS.items()]
    keys.sort(reverse=True)
    return [rarity for _, rarity in keys[:SHOP_SLOTS]]


def price_for(rarity: str, level: int) -> int:
    if rarity == "special":
        return SHOP_SPECIAL_COST
    return round(level_cost(rarity, level) * (1 - SHOP_DISCOUNT))


@dataclass
class Lot:
    char_id: int
    rarity: str
    level: int
    price: int
    card: object
    purchased: bool = False
    maxed: bool = False


@dataclass
class BuyResult:
    status: str  # ok | stale | not_found | purchased | insufficient | maxed
    lot: Lot | None = None
    cost: int = 0
    new_level: int = 0
    shards: int = 0


def _pick(by_rarity: dict, wanted: str, user_id: int, day: int, slot: int, exclude=frozenset()):
    """Highest rarity at/below `wanted` the player owns (non-max), then a stable pick.

    `exclude` holds char_ids already used by other slots so the day's lots don't
    repeat the same card.
    """
    for rank in range(_RARITY_RANK[wanted], len(RARITY_DESC)):
        cards = [c for c in by_rarity.get(RARITY_DESC[rank], []) if c.char_id not in exclude]
        if not cards:
            continue
        cards = sorted(cards, key=lambda c: c.char_id)
        idx = random.Random(f"{user_id}:{day}:{slot}:{RARITY_DESC[rank]}").randrange(len(cards))
        return cards[idx]
    return None


def build_lots(user_id: int, day: int) -> list[Lot]:
    rarities = daily_rarities(user_id, day)

    # A frozen card can disappear (full reset / progress wipe): such a slot is
    # dropped here and re-rolled below, instead of silently vanishing from the shop.
    all_cards = get_owned_characters(user_id)
    owned_ids = {c.char_id for c in all_cards}
    frozen = {
        slot: entry
        for slot, entry in get_shop_rotation(user_id, day).items()
        if entry[0] in owned_ids
    }

    # pick (among non-max cards) only the slots not frozen yet, then freeze them
    owned = [c for c in all_cards if c.level < MAX_CHARACTER_LEVEL]
    by_rarity: dict[str, list] = {}
    for card in owned:
        by_rarity.setdefault(card.rarity, []).append(card)

    used = {char_id for char_id, _rarity in frozen.values()}
    new_picks: dict[int, tuple[int, str]] = {}
    for slot, wanted in enumerate(rarities):
        if slot in frozen:
            continue
        card = _pick(by_rarity, wanted, user_id, day, slot, exclude=used)
        if card is not None:
            new_picks[slot] = (card.char_id, card.rarity)
            used.add(card.char_id)
    if new_picks:
        save_shop_rotation(user_id, day, new_picks)
        frozen.update(new_picks)

    purchased = shop_purchased_char_ids(user_id, day)
    lots: list[Lot] = []
    for slot in sorted(frozen):
        char_id, _rolled = frozen[slot]
        card = get_user_character(user_id, char_id)  # may be max now
        if card is None:
            continue
        maxed = card.level >= MAX_CHARACTER_LEVEL
        lots.append(
            Lot(
                char_id=char_id,
                rarity=card.rarity,
                level=card.level,
                price=0 if maxed else price_for(card.rarity, card.level),
                card=card,
                purchased=char_id in purchased,
                maxed=maxed,
            )
        )
    lots.sort(key=lambda lot: _RARITY_RANK[lot.rarity])  # rarest first
    return lots


def buy(user_id: int, day: int, char_id: int) -> BuyResult:
    current = shop_day()
    if day != current:
        return BuyResult(status="stale")

    lot = next((l for l in build_lots(user_id, current) if l.char_id == char_id), None)
    if lot is None:
        return BuyResult(status="not_found")
    if lot.purchased:
        return BuyResult(status="purchased")
    if lot.maxed:
        return BuyResult(status="maxed")

    with get_session() as session:
        user = session.get(User, user_id)
        instance = session.execute(
            select(UserCharacter).where(
                UserCharacter.user_id == user_id, UserCharacter.char_id == char_id
            )
        ).scalar_one_or_none()
        if user is None or instance is None:
            return BuyResult(status="not_found")
        if instance.level >= MAX_CHARACTER_LEVEL:
            return BuyResult(status="maxed")

        cost = price_for(lot.rarity, instance.level)  # from the *current* level
        shards = user.shards or 0
        if shards < cost:
            return BuyResult(status="insufficient", lot=lot, cost=cost, shards=shards)

        session.add(
            ShopPurchase(
                user_id=user_id, day=current, char_id=char_id, level=instance.level + 1, cost=cost
            )
        )
        try:
            session.flush()  # unique (user, day, char_id) - blocks a double buy
        except IntegrityError:
            session.rollback()
            return BuyResult(status="purchased")

        user.shards = shards - cost
        instance.level += 1
        return BuyResult(status="ok", lot=lot, cost=cost, new_level=instance.level, shards=user.shards)
