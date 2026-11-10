"""Synchronous data-access layer. Every function opens its own session."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy import update as sql_update

from core.i18n import t
from config import (
    ARENA_CALIBRATION_MATCHES,
    ARENA_RATING_CENTER,
    ARENA_SEASON_WEEKS,
    MAX_CHARACTER_LEVEL,
    START_SPINS,
    card_image,
)
from db.models import (
    ArenaBot,
    ArenaDeck,
    ArenaSeason,
    Character,
    Inventory,
    PendingPayment,
    SeasonEntry,
    ProcessedPayment,
    ShopPurchase,
    ShopRotation,
    User,
    UserCharacter,
    compute_stats,
)
from db.session import get_session


@dataclass
class UserData:
    user_id: int
    username: str | None
    first_name: str | None
    language: str | None
    points: int
    shards: int
    spins: int
    super_spins: int
    rating: float
    rating_matches: int
    arena_wins: int
    arena_losses: int
    pve_wins: int
    pve_losses: int
    created_at: datetime | None
    last_button_press: datetime | None


@dataclass
class CharacterBase:
    """A character's immutable base data (no level applied)."""

    char_id: int
    name: str
    name_ru: str
    name_en: str
    rarity: str
    type: int
    gender: str
    base_hp: int
    base_attack: int
    image_path: str


@dataclass
class CharacterCard:
    char_id: int
    char_name: str
    translation: str
    rarity: str
    type: int
    image_path: str
    health: int
    attack: int
    level: int = 1
    gender: str = "unknown"
    base_hp: int = 0
    base_attack: int = 0


def _to_user_data(user: User) -> UserData:
    return UserData(
        user_id=user.user_id,
        username=user.username,
        first_name=user.first_name,
        language=user.language,
        points=user.points or 0,
        shards=user.shards or 0,
        spins=user.spins or 0,
        super_spins=user.super_spins or 0,
        rating=user.rating or 1000.0,
        rating_matches=user.rating_matches or 0,
        arena_wins=user.arena_wins or 0,
        arena_losses=user.arena_losses or 0,
        pve_wins=user.pve_wins or 0,
        pve_losses=user.pve_losses or 0,
        created_at=user.created_at,
        last_button_press=user.last_button_press,
    )


# ──────────────────────────────────────────────
# USERS
# ──────────────────────────────────────────────

def ensure_user(user_id: int, username: str | None = None, first_name: str | None = None) -> str | None:
    """Create/refresh the user and return their language (None = not chosen)."""
    with get_session() as session:
        user = session.get(User, user_id)
        if not user:
            session.add(User(user_id=user_id, username=username, first_name=first_name))
            return None
        if username is not None and user.username != username:
            user.username = username
        if first_name is not None and user.first_name != first_name:
            user.first_name = first_name
        return user.language


def get_user_lang(user_id: int) -> str | None:
    with get_session() as session:
        return session.execute(
            select(User.language).where(User.user_id == user_id)
        ).scalar_one_or_none()


def set_user_language(user_id: int, language: str) -> None:
    with get_session() as session:
        session.execute(
            sql_update(User).where(User.user_id == user_id).values(language=language)
        )


def get_user_data(user_id: int) -> UserData | None:
    with get_session() as session:
        user = session.get(User, user_id)
        return _to_user_data(user) if user else None


def get_all_user_ids() -> list[int]:
    with get_session() as session:
        return list(session.execute(select(User.user_id)).scalars().all())


def get_username(user_id: int) -> str | None:
    with get_session() as session:
        return session.execute(
            select(User.username).where(User.user_id == user_id)
        ).scalar_one_or_none()


def get_user_id_by_username(username: str) -> int | None:
    with get_session() as session:
        return session.execute(
            select(User.user_id).where(User.username == username)
        ).scalar_one_or_none()


def apply_arena_reset(user_id: int, spins: int, shards: int) -> None:
    with get_session() as session:
        session.execute(
            sql_update(User)
            .where(User.user_id == user_id)
            .values(spins=User.spins + spins, shards=User.shards + shards)
        )


def get_currency(user_id: int, column: str) -> int:
    with get_session() as session:
        value = session.execute(
            select(getattr(User, column)).where(User.user_id == user_id)
        ).scalar()
        return value or 0


def update_currency(user_id: int, column: str, amount: int) -> int:
    with get_session() as session:
        user = session.get(User, user_id)
        if not user:
            return 0
        new_value = (getattr(user, column) or 0) + amount
        if column in ("spins", "super_spins", "shards") and new_value < 0:
            new_value = 0
        setattr(user, column, new_value)
        return new_value


def can_press_button(user_id: int, cooldown_hours: int = 2) -> tuple[bool, timedelta | None]:
    with get_session() as session:
        user = session.get(User, user_id)
        if not user or not user.last_button_press:
            return True, None
        last_press = user.last_button_press
        if last_press.tzinfo is None:
            last_press = last_press.replace(tzinfo=timezone.utc)
        next_press = last_press + timedelta(hours=cooldown_hours)
        now = datetime.now(timezone.utc)
        if now >= next_press:
            return True, None
        return False, next_press - now


def touch_last_button_press(user_id: int) -> None:
    with get_session() as session:
        user = session.get(User, user_id)
        if user:
            user.last_button_press = datetime.now(timezone.utc).replace(tzinfo=None)


# ──────────────────────────────────────────────
# CHARACTERS
# ──────────────────────────────────────────────

def is_user_has_characters(user_id: int) -> bool:
    with get_session() as session:
        stmt = select(UserCharacter.id).where(UserCharacter.user_id == user_id).limit(1)
        return session.execute(stmt).first() is not None


def count_user_characters(user_id: int, rarity: str | None = None) -> int:
    with get_session() as session:
        stmt = (
            select(func.count())
            .select_from(UserCharacter)
            .join(Character, Character.char_id == UserCharacter.char_id)
            .where(UserCharacter.user_id == user_id)
        )
        if rarity:
            stmt = stmt.where(Character.rarity == rarity)
        return session.execute(stmt).scalar() or 0


def get_rarity_counts() -> dict[str, int]:
    with get_session() as session:
        rows = session.execute(
            select(Character.rarity, func.count(Character.char_id)).group_by(Character.rarity)
        ).all()
        return {rarity: count for rarity, count in rows}


def get_user_rarity_counts(user_id: int) -> dict[str, int]:
    with get_session() as session:
        rows = session.execute(
            select(Character.rarity, func.count(Character.char_id))
            .join(UserCharacter, UserCharacter.char_id == Character.char_id)
            .where(UserCharacter.user_id == user_id)
            .group_by(Character.rarity)
        ).all()
        return {rarity: count for rarity, count in rows}


def _card_from_row(row, level: int) -> CharacterCard:
    stats = compute_stats(row.base_hp, row.base_attack, row.rarity, level)
    return CharacterCard(
        char_id=row.char_id,
        char_name=row.char_name,
        translation=row.translation,
        rarity=row.rarity,
        type=int(row.type or 0),
        gender=row.gender or "unknown",
        image_path=card_image(row.image_path),
        health=stats["hp"],
        attack=stats["attack"],
        level=level,
        base_hp=int(row.base_hp or 0),
        base_attack=int(row.base_attack or 0),
    )


def get_owned_characters(user_id: int, rarity: str | None = None) -> list[CharacterCard]:
    with get_session() as session:
        stmt = (
            select(Character, UserCharacter.level)
            .join(UserCharacter, UserCharacter.char_id == Character.char_id)
            .where(UserCharacter.user_id == user_id)
            .order_by(UserCharacter.level.desc(), Character.char_name)
        )
        if rarity:
            stmt = stmt.where(Character.rarity == rarity)
        return [_card_from_row(char, level) for char, level in session.execute(stmt).all()]


def get_character_catalog(rarity: str, user_id: int) -> list[dict]:
    """All characters of a rarity, annotated with whether/how `user_id` owns them.

    Each entry: {"card": CharacterCard (at the owned level, else level 1),
    "owned": bool, "level": int}.
    """
    with get_session() as session:
        rows = session.execute(
            select(Character, UserCharacter.level)
            .outerjoin(
                UserCharacter,
                and_(
                    UserCharacter.char_id == Character.char_id,
                    UserCharacter.user_id == user_id,
                ),
            )
            .where(Character.rarity == rarity)
            .order_by(Character.char_id)
        ).all()
    return [
        {"card": _card_from_row(char, level or 1), "owned": level is not None, "level": level or 1}
        for char, level in rows
    ]


def get_user_character(user_id: int, char_id: int) -> CharacterCard | None:
    with get_session() as session:
        row = session.execute(
            select(Character, UserCharacter.level)
            .join(UserCharacter, UserCharacter.char_id == Character.char_id)
            .where(UserCharacter.user_id == user_id, Character.char_id == char_id)
        ).first()
        return _card_from_row(row[0], row[1]) if row else None


def user_owns_character(user_id: int, char_id: int) -> bool:
    with get_session() as session:
        stmt = (
            select(UserCharacter.id)
            .where(UserCharacter.user_id == user_id, UserCharacter.char_id == char_id)
            .limit(1)
        )
        return session.execute(stmt).first() is not None


def grant_character(user_id: int, char_id: int, level: int = 1) -> bool:
    """Grant a character to the user. Returns True if it was new."""
    with get_session() as session:
        exists = session.execute(
            select(UserCharacter.id)
            .where(UserCharacter.user_id == user_id, UserCharacter.char_id == char_id)
            .limit(1)
        ).first()
        if exists:
            return False
        session.add(UserCharacter(user_id=user_id, char_id=char_id, level=level))
        return True


def grant_character_or_level(user_id: int, char_id: int) -> tuple[str, int]:
    """Give the character, or raise its level if the user already owns it.

    Returns (status, level) where status is 'new' | 'upgraded' | 'max'.
    """
    with get_session() as session:
        instance = session.execute(
            select(UserCharacter).where(
                UserCharacter.user_id == user_id,
                UserCharacter.char_id == char_id,
            )
        ).scalar_one_or_none()
        if instance is None:
            session.add(UserCharacter(user_id=user_id, char_id=char_id, level=1))
            return ("new", 1)
        if instance.level >= MAX_CHARACTER_LEVEL:
            return ("max", instance.level)
        instance.level += 1
        return ("upgraded", instance.level)


def get_all_character_bases() -> list[CharacterBase]:
    with get_session() as session:
        chars = session.execute(select(Character)).scalars().all()
        return [
            CharacterBase(
                char_id=c.char_id,
                name=c.translation or c.char_name,
                name_ru=c.translation or c.char_name,
                name_en=c.char_name or c.translation,
                rarity=c.rarity,
                type=int(c.type or 0),
                gender=c.gender or "unknown",
                base_hp=int(c.base_hp or 0),
                base_attack=int(c.base_attack or 0),
                image_path=card_image(c.image_path),
            )
            for c in chars
        ]


def get_character_by_id(char_id: int) -> CharacterCard | None:
    with get_session() as session:
        char = session.get(Character, char_id)
        return _card_from_row(char, level=1) if char else None


def roll_random_character(rarity: str) -> CharacterCard | None:
    with get_session() as session:
        char = session.execute(
            select(Character).where(Character.rarity == rarity).order_by(func.random()).limit(1)
        ).scalar_one_or_none()
        return _card_from_row(char, level=1) if char else None


# ──────────────────────────────────────────────
# ARENA DECK / RATING
# ──────────────────────────────────────────────

MAX_ARENA_DECKS = 3
DEFAULT_DECK_NAME = "Колода"
_DECK_SLOT_COLUMNS = {1: "char_1", 2: "char_2", 3: "char_3"}


def _deck_dict(deck: ArenaDeck) -> dict:
    return {
        "deck_index": deck.deck_index,
        "name": deck.name,
        "is_main": bool(deck.is_main),
        "char_ids": [deck.char_1, deck.char_2, deck.char_3],
    }


def get_decks(user_id: int) -> list[dict]:
    with get_session() as session:
        rows = session.execute(
            select(ArenaDeck).where(ArenaDeck.user_id == user_id).order_by(ArenaDeck.deck_index)
        ).scalars().all()
        return [_deck_dict(row) for row in rows]


def get_deck(user_id: int, deck_index: int) -> dict | None:
    with get_session() as session:
        deck = session.get(ArenaDeck, (user_id, deck_index))
        return _deck_dict(deck) if deck else None


def ensure_default_deck(user_id: int, lang: str = "ru") -> None:
    with get_session() as session:
        exists = session.execute(
            select(ArenaDeck.deck_index).where(ArenaDeck.user_id == user_id).limit(1)
        ).first()
        if exists is None:
            name = f"{t(lang, 'Колода')} 1"
            session.add(ArenaDeck(user_id=user_id, deck_index=0, name=name, is_main=True))


def get_main_deck(user_id: int, lang: str = "ru") -> dict | None:
    decks = get_decks(user_id)
    if not decks:
        ensure_default_deck(user_id, lang)
        decks = get_decks(user_id)
    return next((deck for deck in decks if deck["is_main"]), decks[0] if decks else None)


def get_arena_deck_ids(user_id: int) -> list[int | None]:
    """The MAIN deck's 3 slots (char_id or None), used by matchmaking/battle."""
    deck = get_main_deck(user_id)
    return list(deck["char_ids"]) if deck else [None, None, None]


def ensure_decks(user_id: int, lang: str = "ru") -> None:
    """Make sure the user has all MAX_ARENA_DECKS decks (deck 0 is the main)."""
    with get_session() as session:
        existing = set(
            session.execute(select(ArenaDeck.deck_index).where(ArenaDeck.user_id == user_id)).scalars().all()
        )
        for index in range(MAX_ARENA_DECKS):
            if index in existing:
                continue
            session.add(
                ArenaDeck(
                    user_id=user_id,
                    deck_index=index,
                    name=t(lang, "Колода {index}", index=index + 1),
                    is_main=(index == 0 and not existing),
                )
            )


def rename_deck(user_id: int, deck_index: int, name: str, lang: str = "ru") -> None:
    name = (name or "").strip()[:32] or t(lang, DEFAULT_DECK_NAME)
    with get_session() as session:
        session.execute(
            sql_update(ArenaDeck)
            .where(ArenaDeck.user_id == user_id, ArenaDeck.deck_index == deck_index)
            .values(name=name)
        )


def set_deck_main(user_id: int, deck_index: int) -> None:
    with get_session() as session:
        session.execute(sql_update(ArenaDeck).where(ArenaDeck.user_id == user_id).values(is_main=False))
        session.execute(
            sql_update(ArenaDeck)
            .where(ArenaDeck.user_id == user_id, ArenaDeck.deck_index == deck_index)
            .values(is_main=True)
        )


def set_deck_slot(user_id: int, deck_index: int, slot: int, char_id: int) -> None:
    column = _DECK_SLOT_COLUMNS.get(slot)
    if column is None:
        return
    with get_session() as session:
        session.execute(
            sql_update(ArenaDeck)
            .where(ArenaDeck.user_id == user_id, ArenaDeck.deck_index == deck_index)
            .values(**{column: char_id})
        )


def clear_deck(user_id: int, deck_index: int) -> None:
    with get_session() as session:
        session.execute(
            sql_update(ArenaDeck)
            .where(ArenaDeck.user_id == user_id, ArenaDeck.deck_index == deck_index)
            .values(char_1=None, char_2=None, char_3=None)
        )


def get_rating(user_id: int) -> tuple[float, float, float, int]:
    """Return (rating, rd, vol, matches)."""
    with get_session() as session:
        row = session.execute(
            select(User.rating, User.rd, User.vol, User.rating_matches).where(User.user_id == user_id)
        ).first()
    if not row:
        return 1000.0, 350.0, 0.06, 0
    return row[0] or 1000.0, row[1] or 350.0, row[2] or 0.06, row[3] or 0


def save_rating(user_id: int, rating: float, rd: float, vol: float) -> None:
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None:
            return
        user.rating = rating
        user.rd = rd
        user.vol = vol
        user.rating_matches = (user.rating_matches or 0) + 1
        user.last_match_at = datetime.now(timezone.utc).replace(tzinfo=None)


def increment_arena_result(user_id: int, won: bool) -> None:
    column = User.arena_wins if won else User.arena_losses
    with get_session() as session:
        session.execute(
            sql_update(User)
            .where(User.user_id == user_id)
            .values(**{column.key: func.coalesce(column, 0) + 1})
        )


def increment_pve_result(user_id: int, won: bool) -> None:
    column = User.pve_wins if won else User.pve_losses
    with get_session() as session:
        session.execute(
            sql_update(User)
            .where(User.user_id == user_id)
            .values(**{column.key: func.coalesce(column, 0) + 1})
        )


def get_bot_stats() -> dict:
    with get_session() as session:
        bot = session.get(ArenaBot, 1)
        if bot is None:
            bot = ArenaBot(id=1)
            session.add(bot)
            session.flush()
        return {
            "rating": bot.rating or 1000.0,
            "rd": bot.rd or 350.0,
            "vol": bot.vol or 0.06,
            "wins": bot.wins or 0,
            "losses": bot.losses or 0,
        }


def save_bot_stats(rating: float, rd: float, vol: float, won: bool) -> None:
    with get_session() as session:
        bot = session.get(ArenaBot, 1)
        if bot is None:
            bot = ArenaBot(id=1)
            session.add(bot)
        bot.rating = rating
        bot.rd = rd
        bot.vol = vol
        if won:
            bot.wins = (bot.wins or 0) + 1
        else:
            bot.losses = (bot.losses or 0) + 1


def reset_bot_stats() -> None:
    """Reset the PvE bot's own rating/record to defaults."""
    with get_session() as session:
        bot = session.get(ArenaBot, 1)
        if bot is None:
            bot = ArenaBot(id=1)
            session.add(bot)
        bot.rating = ARENA_RATING_CENTER
        bot.rd = 350.0
        bot.vol = 0.06
        bot.wins = 0
        bot.losses = 0


def reset_all_ratings() -> int:
    """Hard reset every user's arena rating (PvP ladder). Returns users reset."""
    with get_session() as session:
        result = session.execute(
            sql_update(User).values(
                rating=ARENA_RATING_CENTER,
                rd=350.0,
                vol=0.06,
                rating_matches=0,
                last_match_at=None,
                last_decay_at=None,
                arena_wins=0,
                arena_losses=0,
            )
        )
        return result.rowcount or 0


def is_deck_ready(user_id: int) -> bool:
    return all(get_arena_deck_ids(user_id))


# ──────────────────────────────────────────────
# TOP
# ──────────────────────────────────────────────

def get_top_players(
    user_id: int | None = None, limit: int = 10, order_col: str = "points", min_matches: int = 0
) -> dict:
    col = getattr(User, order_col)
    with get_session() as session:
        base = select(
            User.user_id,
            func.coalesce(func.nullif(User.first_name, ""), User.username).label("name"),
            col.label("value"),
        )
        if min_matches:
            base = base.where(User.rating_matches >= min_matches)
        ranked = base.add_columns(
            func.row_number().over(order_by=col.desc()).label("pos")
        ).subquery()

        top = session.execute(
            select(ranked.c.pos, ranked.c.name, ranked.c.value)
            .where(ranked.c.pos <= limit)
            .order_by(ranked.c.pos)
        ).all()
        result = {"top": [(r.pos, r.name, r.value) for r in top]}
        if user_id is not None:
            row = session.execute(
                select(ranked.c.pos, ranked.c.name, ranked.c.value).where(ranked.c.user_id == user_id)
            ).first()
            if row:
                result["user_position"] = {"position": row.pos, "name": row.name, "points": row.value}
        return result


def get_users_page(page: int = 0, limit: int = 5, order_col: str = "points") -> dict:
    """A page of users sorted by `order_col` (desc), with wrap-around paging.

    Defaults to points so the admin browser lists players by the same order as
    the points leaderboard.
    """
    col = getattr(User, order_col)
    with get_session() as session:
        total = session.execute(select(func.count()).select_from(User)).scalar() or 0
        total_pages = max(1, (total + limit - 1) // limit)
        page = page % total_pages
        rows = session.execute(
            select(User.user_id, User.username, User.first_name, col)
            .order_by(col.desc().nulls_last(), User.user_id)
            .offset(page * limit)
            .limit(limit)
        ).all()
    return {
        "page": page,
        "total": total,
        "total_pages": total_pages,
        "items": [
            {"user_id": r[0], "username": r[1], "first_name": r[2], "points": int(r[3] or 0)}
            for r in rows
        ],
    }


# ──────────────────────────────────────────────
# SEASONS / LEAGUES
# ──────────────────────────────────────────────

def count_ranked_users() -> int:
    with get_session() as session:
        return session.execute(
            select(func.count()).select_from(User).where(User.rating_matches >= ARENA_CALIBRATION_MATCHES)
        ).scalar() or 0


def get_user_rank(user_id: int) -> int:
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None:
            return 0
        above = session.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.rating_matches >= ARENA_CALIBRATION_MATCHES,
                or_(
                    User.rating > user.rating,
                    and_(User.rating == user.rating, User.arena_wins > (user.arena_wins or 0)),
                ),
            )
        ).scalar() or 0
        return above + 1


def list_users_rating_matches() -> list[tuple[int, int]]:
    """(user_id, rating_matches) for every user - used by season-end notices."""
    with get_session() as session:
        rows = session.execute(select(User.user_id, User.rating_matches)).all()
    return [(r[0], int(r[1] or 0)) for r in rows]


def list_ranked_users() -> list[dict]:
    with get_session() as session:
        rows = session.execute(
            select(User.user_id, User.rating, User.rd, User.vol, User.arena_wins, User.arena_losses)
            .where(User.rating_matches >= ARENA_CALIBRATION_MATCHES)
            .order_by(User.rating.desc(), User.arena_wins.desc())
        ).all()
    return [
        {
            "user_id": r[0],
            "rating": r[1] or 1000.0,
            "rd": r[2] or 350.0,
            "vol": r[3] or 0.06,
            "wins": r[4] or 0,
            "losses": r[5] or 0,
        }
        for r in rows
    ]


def soft_reset_all_ratings(center: float, k: float, rd_floor: float, vol: float) -> int:
    """Soft-reset every player's rating and restart calibration at 0/10.

    Runs as a single UPDATE so the new season starts for everyone at once -
    including players who never finished calibration.
    """
    with get_session() as session:
        result = session.execute(
            sql_update(User).values(
                rating=center + (func.coalesce(User.rating, center) - center) * k,
                rd=func.least(350.0, func.greatest(func.coalesce(User.rd, 350.0), rd_floor)),
                vol=vol,
                rating_matches=0,
            )
        )
        return result.rowcount or 0


def decayed_rating(
    rating: float, days: int, center: float, percent: float, min_amount: int, floor: float
) -> float:
    """Rating after `days` of inactivity decay. Applies below the center too."""
    per_day = max(min_amount, round(percent * max(0.0, rating - center)))
    return max(float(floor), rating - per_day * days)


def apply_rating_decay(
    center: float, start_days: int, percent: float, min_amount: int, floor: float
) -> list[tuple[int, float, float]]:
    """Lose rating for inactivity. Calibrated players, any current rating.

    Idempotent via `last_decay_at`: charges only whole days since the later of
    (last match + start_days) and the previous decay run.

    Returns a list of (user_id, old_rating, new_rating) for players whose rating
    actually changed.
    """
    charged: list[tuple[int, float, float]] = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with get_session() as session:
        users = session.execute(
            select(User).where(
                User.rating_matches >= ARENA_CALIBRATION_MATCHES,
                User.last_match_at.isnot(None),
            )
        ).scalars().all()
        for user in users:
            last_match = user.last_match_at
            if last_match.tzinfo is not None:
                last_match = last_match.astimezone(timezone.utc).replace(tzinfo=None)
            idle_start = last_match + timedelta(days=start_days)
            if now < idle_start:
                continue
            anchor = idle_start
            if user.last_decay_at is not None and user.last_decay_at > anchor:
                anchor = user.last_decay_at
            days = (now - anchor).days
            if days <= 0:
                continue

            rating = user.rating or center
            new_rating = decayed_rating(rating, days, center, percent, min_amount, floor)
            user.last_decay_at = now
            if new_rating == rating:
                continue
            user.rating = new_rating
            charged.append((user.user_id, float(rating), float(new_rating)))
    return charged


def ensure_current_season() -> dict:
    with get_session() as session:
        season = session.execute(
            select(ArenaSeason).where(ArenaSeason.status == "active").order_by(ArenaSeason.id.desc())
        ).scalars().first()
        if season is None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            season = ArenaSeason(
                started_at=now,
                ends_at=now + timedelta(weeks=ARENA_SEASON_WEEKS),
                status="active",
            )
            session.add(season)
            session.flush()
        return {"id": season.id, "started_at": season.started_at, "ends_at": season.ends_at}


def start_new_season() -> dict:
    with get_session() as session:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        season = ArenaSeason(
            started_at=now,
            ends_at=now + timedelta(weeks=ARENA_SEASON_WEEKS),
            status="active",
        )
        session.add(season)
        session.flush()
        return {"id": season.id, "started_at": season.started_at, "ends_at": season.ends_at}


def close_season(season_id: int) -> None:
    with get_session() as session:
        season = session.get(ArenaSeason, season_id)
        if season:
            season.status = "closed"


def add_season_entry(
    season_id: int, user_id: int, rating: float, tier: str, place: int, shards: int, spins: int
) -> None:
    with get_session() as session:
        session.add(
            SeasonEntry(
                season_id=season_id,
                user_id=user_id,
                rating=rating,
                tier=tier,
                place=place,
                shards=shards,
                spins=spins,
            )
        )


def reset_all_progress() -> int:
    """Wipe all progression for every user (keeps accounts/registration).

    Resets points, rating, shards, spins; clears owned characters, inventory
    and arena decks; resets arena stats and bot stats; clears season history.
    """
    with get_session() as session:
        result = session.execute(
            sql_update(User).values(
                points=0,
                rating=ARENA_RATING_CENTER,
                rd=350.0,
                vol=0.06,
                rating_matches=0,
                arena_wins=0,
                arena_losses=0,
                pve_wins=0,
                pve_losses=0,
                shards=0,
                spins=START_SPINS,
                super_spins=0,
                last_match_at=None,
                last_button_press=None,
            )
        )
        users = result.rowcount or 0
        session.execute(delete(UserCharacter))
        session.execute(delete(Inventory))
        session.execute(delete(ArenaDeck))
        session.execute(delete(SeasonEntry))
        bot = session.get(ArenaBot, 1)
        if bot is not None:
            bot.rating = ARENA_RATING_CENTER
            bot.rd = 350.0
            bot.vol = 0.06
            bot.wins = 0
            bot.losses = 0
    return users


# ──────────────────────────────────────────────
# PAYMENTS
# ──────────────────────────────────────────────

def is_payment_processed(operation_id: str) -> bool:
    with get_session() as session:
        return session.get(ProcessedPayment, operation_id) is not None


def mark_payment_processed(
    operation_id: str,
    user_id: int,
    amount: float,
    item_type: str,
    item_count: int,
    label: str,
) -> None:
    with get_session() as session:
        session.merge(
            ProcessedPayment(
                operation_id=operation_id,
                user_id=user_id,
                amount=amount,
                item_type=item_type,
                item_count=item_count,
                label=label,
            )
        )


def save_pending_payment(invoice_id: str, user_id: int, shards: int, currency: str, amount: float) -> None:
    with get_session() as session:
        session.merge(
            PendingPayment(
                invoice_id=invoice_id,
                user_id=user_id,
                shards=shards,
                currency=currency,
                amount=amount,
            )
        )


def get_pending_payment(invoice_id: str) -> dict | None:
    with get_session() as session:
        row = session.get(PendingPayment, invoice_id)
        if row is None:
            return None
        return {
            "user_id": row.user_id,
            "shards": row.shards or 0,
            "currency": row.currency,
            "amount": float(row.amount or 0),
        }


def delete_pending_payment(invoice_id: str) -> None:
    with get_session() as session:
        row = session.get(PendingPayment, invoice_id)
        if row is not None:
            session.delete(row)


def get_shop_rotation(user_id: int, day: int) -> dict[int, tuple[int, str | None]]:
    """Frozen lots of the day: slot -> (char_id, rolled rarity)."""
    with get_session() as session:
        rows = session.execute(
            select(ShopRotation.slot, ShopRotation.char_id, ShopRotation.rarity).where(
                ShopRotation.user_id == user_id, ShopRotation.day == day
            )
        ).all()
        return {slot: (char_id, rarity) for slot, char_id, rarity in rows}


def save_shop_rotation(user_id: int, day: int, picks: dict[int, tuple[int, str]]) -> None:
    """Freeze the given slots (upsert).

    Callers only pass slots that are not frozen yet, so replacing an existing
    row only happens for a stale entry (the frozen card is no longer owned).
    """
    if not picks:
        return
    with get_session() as session:
        session.execute(
            delete(ShopRotation).where(
                ShopRotation.user_id == user_id,
                ShopRotation.day == day,
                ShopRotation.slot.in_(list(picks)),
            )
        )
        for slot, (char_id, rarity) in picks.items():
            session.add(
                ShopRotation(user_id=user_id, day=day, slot=slot, char_id=char_id, rarity=rarity)
            )


def shop_purchased_char_ids(user_id: int, day: int) -> set[int]:
    with get_session() as session:
        rows = session.execute(
            select(ShopPurchase.char_id).where(
                ShopPurchase.user_id == user_id, ShopPurchase.day == day
            )
        ).scalars().all()
        return set(rows)


def finalize_payment(operation_id: str, user_id: int, amount: float, shards: int, label: str) -> str:
    """Atomically credit shards and record the operation. Returns status."""
    with get_session() as session:
        if session.get(ProcessedPayment, operation_id) is not None:
            return "duplicate"
        user = session.get(User, user_id)
        if user is None:
            return "no_user"
        user.shards = (user.shards or 0) + max(0, shards)
        session.add(
            ProcessedPayment(
                operation_id=operation_id,
                user_id=user_id,
                amount=amount,
                item_type="shards",
                item_count=shards,
                label=label,
            )
        )
        return "ok"
