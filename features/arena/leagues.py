"""Season leagues and rewards.

Leagues are relative: a player's league is their percentile among ranked
players (calibrated, >= 10 games this season). Rewards are paid at season end.
"""

from dataclasses import dataclass

from core.i18n import t


@dataclass(frozen=True)
class League:
    key: str
    name: str
    emoji: str
    top: float  # band upper bound (share of ranked population)
    shards: int
    spins: int

    def title(self, lang: str = "ru") -> str:
        return f"{self.emoji} {t(lang, self.name)}"


MASTER = League("master", "Мастер", "🌟", 0.05, 500, 40)
DIAMOND = League("diamond", "Алмазная", "💎", 0.10, 300, 25)
GOLD = League("gold", "Золотая", "✨", 0.30, 200, 15)
SILVER = League("silver", "Серебряная", "⚪", 0.60, 80, 10)
BRONZE = League("bronze", "Бронзовая", "🔶", 1.00, 30, 5)
UNRANKED = League("unranked", "Без лиги", "⚫", 0.0, 0, 0)

LEAGUES = [MASTER, DIAMOND, GOLD, SILVER, BRONZE]
BY_KEY = {league.key: league for league in (*LEAGUES, UNRANKED)}


def _cuts(total: int) -> list[int]:
    """Rank cut-offs for each league (1-based, inclusive upper rank)."""
    seats = []
    previous = 0
    for league in LEAGUES:
        cut = max(previous + 1, round(league.top * total))
        seats.append(cut)
        previous = cut
    return seats


def league_for_rank(rank: int, total: int) -> League:
    if total <= 0 or rank < 1:
        return UNRANKED
    for league, cut in zip(LEAGUES, _cuts(total)):
        if rank <= cut:
            return league
    return BRONZE


def percentile(rank: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(1, round(rank / total * 100))


def position_text(lang: str, rank: int, total: int, top_min: int = 10) -> str:
    """Human position. Percentiles only make sense with enough players, so for
    a small population we show just the place (e.g. "место 1/1")."""
    if total >= top_min:
        return t(
            lang,
            "топ {pct}%, место {rank}/{total}",
            pct=percentile(rank, total),
            rank=rank,
            total=total,
        )
    return t(lang, "место {rank}/{total}", rank=rank, total=total)


def league_table_text(lang: str = "ru") -> str:
    rows = [
        (MASTER, "топ 5%"),
        (DIAMOND, "топ 10%"),
        (GOLD, "топ 30%"),
        (SILVER, "топ 60%"),
    ]
    lines = [f"<blockquote>{t(lang, 'Лига - награда - место')}"]
    for league, band in rows:
        lines.append(
            f"{league.emoji} {t(lang, league.name)} - {league.shards}🔮, "
            f"{league.spins}🎴 - {t(lang, band)}"
        )
    lines.append(
        f"{BRONZE.emoji} {t(lang, BRONZE.name)} - {BRONZE.shards}🔮, "
        f"{BRONZE.spins}🎴 - {t(lang, 'остальные')}</blockquote>"
    )
    return "\n".join(lines)
