"""DonationAlerts donations: unique amounts, matching and crediting.

The donor pays an exact amount that was reserved for them (pack price minus a
small range of kopecks/cents). The exact amount is the order key; matching is
amount + currency, with a whole-unit fallback when the donor drops the kopecks.

Amounts are reserved for `DONATION_MATCH_HOURS` (so a late payment still lands
on its order) plus a reuse cooldown, so a freed amount can never be matched to
somebody else's payment.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select

from config import (
    DONATION_MATCH_HOURS,
    DONATION_MIN_MINOR,
    DONATION_PRICES,
    DONATION_RANGE,
    DONATION_RANGE_OVERFLOW,
    DONATION_REUSE_HOURS,
)
from db.models import Donation, DonationCredit, DonationOrder, DonationSlot, User
from db.session import get_session

MINOR = 100
PROVIDER = "donationalerts"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def packs(currency: str) -> dict[int, int]:
    """{price in minor units: shards} for a currency."""
    return {int(price) * MINOR: shards for price, shards in DONATION_PRICES[currency].items()}


def currency_symbol(currency: str) -> str:
    return {"RUB": "₽", "USD": "$", "EUR": "€"}.get(currency, currency)


def fmt_minor(currency: str, amount_minor: int) -> str:
    whole, frac = divmod(int(amount_minor), MINOR)
    return f"{whole}.{frac:02d} {currency_symbol(currency)}"


def amount_number(amount_minor: int) -> str:
    whole, frac = divmod(int(amount_minor), MINOR)
    return f"{whole}.{frac:02d}"


def _order_dict(order: DonationOrder) -> dict:
    return {
        "id": order.id,
        "user_id": order.user_id,
        "currency": order.currency,
        "base_minor": order.base_minor,
        "amount_minor": order.amount_minor,
        "shards": order.shards,
        "status": order.status,
        "match_until": order.match_until,
    }


# ──────────────────────────────────────────────
# Orders
# ──────────────────────────────────────────────

def _bands(currency: str, base_minor: int) -> list[tuple[int, int]]:
    """Possible amounts, normal band first then the overflow one.

    Amounts normally go *below* the pack price (the donor pays a little less).
    The smallest pack cannot go below the platform minimum, so it goes above it.
    """
    normal = DONATION_RANGE[currency]
    hard = DONATION_RANGE_OVERFLOW[currency]
    if base_minor - hard < DONATION_MIN_MINOR.get(currency, 0):
        return [
            (base_minor, base_minor + normal),
            (base_minor + normal + 1, base_minor + hard),
        ]
    return [
        (base_minor - normal, base_minor),
        (base_minor - hard, base_minor - normal - 1),
    ]


def _range(currency: str, base_minor: int) -> tuple[int, int]:
    bands = _bands(currency, base_minor)
    return min(band[0] for band in bands), max(band[1] for band in bands)


def _ensure_slots(session, currency: str, base_minor: int) -> None:
    low, high = _range(currency, base_minor)
    existing = set(
        session.execute(
            select(DonationSlot.amount_minor).where(
                DonationSlot.currency == currency, DonationSlot.base_minor == base_minor
            )
        ).scalars()
    )
    for amount in range(low, high + 1):
        if amount not in existing:
            session.add(
                DonationSlot(currency=currency, base_minor=base_minor, amount_minor=amount)
            )
    session.flush()


def _allocate(session, currency: str, base_minor: int) -> int | None:
    """Reserve a random free amount: the normal range first, then the overflow."""
    now = utcnow()
    for low, high in _bands(currency, base_minor):
        if high < low:
            continue
        slot = session.execute(
            select(DonationSlot)
            .where(
                DonationSlot.currency == currency,
                DonationSlot.base_minor == base_minor,
                DonationSlot.amount_minor.between(low, high),
                # Never hand out a whole amount: a donor who drops the kopecks
                # (500.00) must fall into the "base" branch, not hit somebody
                # else's exact order.
                DonationSlot.amount_minor % MINOR != 0,
                or_(
                    DonationSlot.reserved_until.is_(None),
                    DonationSlot.reserved_until < now,
                ),
            )
            .order_by(func.random())
            .limit(1)
            .with_for_update(skip_locked=True)
        ).scalars().first()
        if slot is not None:
            slot.reserved_until = now + timedelta(
                hours=DONATION_MATCH_HOURS + DONATION_REUSE_HOURS
            )
            slot.last_used_at = now
            return int(slot.amount_minor)
    return None


def create_order(user_id: int, currency: str, base_minor: int) -> dict | None:
    """Reuse the user's pending order for this pack, or allocate a new amount."""
    prices = packs(currency)
    if base_minor not in prices:
        return None
    now = utcnow()
    with get_session() as session:
        existing = session.execute(
            select(DonationOrder)
            .where(
                DonationOrder.user_id == user_id,
                DonationOrder.currency == currency,
                DonationOrder.base_minor == base_minor,
                DonationOrder.status == "pending",
                DonationOrder.match_until > now,
            )
            .order_by(DonationOrder.id.desc())
        ).scalars().first()
        if existing is not None:
            low, high = _range(currency, base_minor)
            if low <= existing.amount_minor <= high:
                return _order_dict(existing)
            # The amount is no longer valid (e.g. the platform minimum changed):
            # cancel it and hand out a fresh one.
            existing.status = "cancelled"

        _ensure_slots(session, currency, base_minor)
        amount = _allocate(session, currency, base_minor)
        if amount is None:
            return None
        order = DonationOrder(
            user_id=user_id,
            currency=currency,
            base_minor=base_minor,
            amount_minor=amount,
            shards=prices[base_minor],
            status="pending",
            match_until=now + timedelta(hours=DONATION_MATCH_HOURS),
        )
        session.add(order)
        session.flush()
        return _order_dict(order)


def active_order(user_id: int) -> dict | None:
    now = utcnow()
    with get_session() as session:
        order = session.execute(
            select(DonationOrder)
            .where(
                DonationOrder.user_id == user_id,
                DonationOrder.status == "pending",
                DonationOrder.match_until > now,
            )
            .order_by(DonationOrder.id.desc())
        ).scalars().first()
        return _order_dict(order) if order else None


def cancel_order(user_id: int, order_id: int) -> bool:
    with get_session() as session:
        order = session.get(DonationOrder, order_id)
        if order is None or order.user_id != user_id or order.status != "pending":
            return False
        # The amount stays reserved until its match window ends: a payment that
        # is already on its way must still land on this order.
        order.status = "cancelled"
        return True


# ──────────────────────────────────────────────
# Matching
# ──────────────────────────────────────────────

def _pack_for_amount(currency: str, amount_minor: int) -> int | None:
    """The pack whose range contains a whole-unit amount, if any."""
    for base in packs(currency):
        low, high = _range(currency, base)
        if low <= amount_minor <= high:
            return base
    return None


def suggested_shards(currency: str, amount_minor: int) -> int:
    if currency not in DONATION_PRICES:
        return 0
    prices = packs(currency)
    base = _pack_for_amount(currency, amount_minor) or min(
        prices, key=lambda value: abs(value - amount_minor)
    )
    return prices[base]


def _credit(session, donation: Donation, order: DonationOrder, flag: str = "") -> dict:
    now = utcnow()
    if order.status == "paid":
        donation.status = "manual"
        donation.note = "order already paid"
        return {"status": "manual", "donation_id": donation.id, "reason": "already_paid"}

    user = session.get(User, order.user_id)
    if user is None:
        donation.status = "manual"
        donation.note = "user not found"
        return {"status": "manual", "donation_id": donation.id, "reason": "user"}

    user.shards = (user.shards or 0) + order.shards
    order.status = "paid"
    order.flag = flag
    order.paid_at = now
    order.donation_id = donation.provider_id
    donation.status = "matched"
    donation.order_id = order.id
    session.add(
        DonationCredit(
            donation_id=donation.id,
            order_id=order.id,
            user_id=order.user_id,
            shards=order.shards,
            amount_minor=donation.amount_minor,
            currency=donation.currency,
        )
    )
    return {
        "status": "matched",
        "donation_id": donation.id,
        "user_id": order.user_id,
        "order_id": order.id,
        "shards": order.shards,
        "amount_minor": donation.amount_minor,
        "currency": donation.currency,
        "flag": flag,
    }


def match_donation(
    provider_id: int,
    amount_minor: int,
    currency: str,
    username: str | None = None,
    message: str | None = None,
    created_at: datetime | None = None,
    raw: dict | None = None,
) -> dict:
    """Store one donation event and try to match it to a pending order."""
    currency = (currency or "").upper()
    with get_session() as session:
        duplicate = session.execute(
            select(Donation).where(
                Donation.provider == PROVIDER, Donation.provider_id == provider_id
            )
        ).scalars().first()
        if duplicate is not None:
            return {"status": "duplicate"}

        donation = Donation(
            provider=PROVIDER,
            provider_id=provider_id,
            amount_minor=amount_minor,
            currency=currency,
            username=username,
            message=message,
            created_at=created_at,
            raw=raw,
        )
        session.add(donation)
        session.flush()

        now = utcnow()
        if currency not in DONATION_PRICES:
            donation.status = "manual"
            donation.note = "currency"
            return {"status": "manual", "donation_id": donation.id, "reason": "currency"}

        order = session.execute(
            select(DonationOrder)
            .where(
                DonationOrder.currency == currency,
                DonationOrder.amount_minor == amount_minor,
                DonationOrder.status == "pending",
                DonationOrder.match_until > now,
            )
            .with_for_update()
        ).scalars().first()
        if order is not None:
            return _credit(session, donation, order)

        if amount_minor % MINOR == 0:
            base = _pack_for_amount(currency, amount_minor)
            if base is not None:
                candidates = session.execute(
                    select(DonationOrder)
                    .where(
                        DonationOrder.currency == currency,
                        DonationOrder.base_minor == base,
                        DonationOrder.status == "pending",
                        DonationOrder.match_until > now,
                    )
                    .order_by(DonationOrder.id)
                ).scalars().all()
                if len(candidates) == 1:
                    return _credit(session, donation, candidates[0], flag="base")
                if len(candidates) > 1:
                    donation.status = "ambiguous"
                    donation.note = "base"
                    return {
                        "status": "ambiguous",
                        "donation_id": donation.id,
                        "candidates": [
                            {"user_id": item.user_id, "order_id": item.id}
                            for item in candidates
                        ],
                    }

        donation.status = "manual"
        donation.note = "no_match"
        return {"status": "manual", "donation_id": donation.id, "reason": "no_match"}


def claim_ambiguous(donation_id: int, order_id: int, user_id: int) -> dict:
    """A candidate confirmed the payment; the first claim wins."""
    with get_session() as session:
        donation = session.get(Donation, donation_id)
        order = session.get(DonationOrder, order_id)
        if donation is None or donation.status != "ambiguous":
            return {"status": "taken"}
        if order is None or order.user_id != user_id or order.status != "pending":
            return {"status": "taken"}
        return _credit(session, donation, order, flag="claim")


# ──────────────────────────────────────────────
# Admin queue
# ──────────────────────────────────────────────

def list_unmatched(limit: int = 10) -> list[dict]:
    with get_session() as session:
        rows = session.execute(
            select(Donation)
            .where(Donation.status.in_(("manual", "ambiguous")))
            .order_by(Donation.id.desc())
            .limit(limit)
        ).scalars().all()
        return [
            {
                "id": row.id,
                "provider_id": row.provider_id,
                "amount_minor": row.amount_minor,
                "currency": row.currency,
                "username": row.username,
                "message": row.message,
                "status": row.status,
                "note": row.note,
                "created_at": row.created_at,
                "suggested": suggested_shards(row.currency, row.amount_minor),
            }
            for row in rows
        ]


def admin_credit(donation_id: int, user_id: int, shards: int | None = None) -> dict | None:
    with get_session() as session:
        donation = session.get(Donation, donation_id)
        if donation is None or donation.status in ("matched", "ignored"):
            return None
        user = session.get(User, user_id)
        if user is None:
            return None
        if shards is None:
            shards = suggested_shards(donation.currency, donation.amount_minor)
        user.shards = (user.shards or 0) + int(shards)
        donation.status = "matched"
        donation.note = "manual credit"
        session.add(
            DonationCredit(
                donation_id=donation.id,
                order_id=None,
                user_id=user_id,
                shards=int(shards),
                amount_minor=donation.amount_minor,
                currency=donation.currency,
            )
        )
        return {"user_id": user_id, "shards": int(shards)}


def ignore_donation(donation_id: int) -> bool:
    with get_session() as session:
        donation = session.get(Donation, donation_id)
        if donation is None or donation.status == "matched":
            return False
        donation.status = "ignored"
        return True


def get_donation(donation_id: int) -> dict | None:
    with get_session() as session:
        row = session.get(Donation, donation_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "amount_minor": row.amount_minor,
            "currency": row.currency,
            "username": row.username,
            "message": row.message,
            "status": row.status,
        }
