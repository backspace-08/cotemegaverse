"""Text layout for the admin donation inbox."""

from html import escape

from services.donations import fmt_minor

REASONS = {
    "no_match": "сумма не совпала с заявками",
    "ambiguous": "сумма не совпала с точной суммой заявки",
    "collision": "несколько заявок с одинаковой суммой",
    "base": "старая заявка без точного совпадения",
    "currency": "валюта не поддерживается",
}


def reason_text(note: str | None) -> str:
    return REASONS.get((note or "").strip(), "нужно разобрать вручную")


def _tag(candidate: dict) -> str:
    if candidate.get("username"):
        return f"@{candidate['username']}"
    return candidate.get("first_name") or "без тега"


def card_text(donation: dict, candidates: list[dict]) -> str:
    amount = fmt_minor(donation["currency"], donation["amount_minor"])
    username = escape(donation.get("username") or "аноним")
    message = escape((donation.get("message") or "").strip() or "-")
    lines = [
        f"💸 <b>#{donation['id']}</b> · {amount}",
        f"{username}: «{message}»",
        f"Причина: {reason_text(donation.get('note'))}",
        "",
    ]
    if candidates:
        lines.append("Кандидаты:")
        for candidate in candidates:
            lines.append(
                f"{escape(_tag(candidate))} "
                f"(id <code>{candidate['user_id']}</code>) - "
                f"заявка #{candidate['order_id']}, "
                f"{fmt_minor(donation['currency'], candidate['amount_minor'])}"
            )
    else:
        lines.append("Кандидатов нет.")
    return "\n".join(lines)


def list_text(items: list[dict], page: int, pages: int, total: int) -> str:
    lines = [f"💸 <b>Неразобранные донаты</b> ({total})"]
    if pages > 1:
        lines.append(f"Страница {page + 1}/{pages}")
    rows = []
    for donation in items:
        amount = fmt_minor(donation["currency"], donation["amount_minor"])
        name = escape(donation.get("username") or "аноним")
        rows.append(f"#{donation['id']:<5} {amount:>10}  {name}")
    lines.append("<pre>" + "\n".join(rows) + "</pre>")
    return "\n".join(lines)


def credited_text(
    currency: str,
    amount_minor: int,
    shards: int,
    username: str | None,
    user_id: int,
    order_id: int | None = None,
) -> str:
    who = (
        f"@{username} (id <code>{user_id}</code>)"
        if username
        else f"id <code>{user_id}</code>"
    )
    text = f"✅ Зачтено: {fmt_minor(currency, amount_minor)} → +{shards}🔮\n👤 {who}"
    if order_id:
        text += f"\nЗаявка #{order_id}"
    return text


def ignored_text(donation: dict) -> str:
    amount = fmt_minor(donation["currency"], donation["amount_minor"])
    return f"🚫 Донат #{donation['id']} · {amount} отклонён"
