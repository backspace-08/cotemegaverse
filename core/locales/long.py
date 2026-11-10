"""Bilingual long-form blocks, referenced from code as ``t(lang, "@name")``."""

_ABOUT_RU = (
    "<b>❤️ Здоровье</b> - очки жизни персонажа\n"
    "<b>💪 Урон</b> - сила атаки\n\n"
    "<b>Типы персонажей:</b> 🎭 💢 🎯 ⭐\n"
    "🎭 Манипуляторы\n"
    "💢 Силовики\n"
    "🎯 Тактики\n"
    "⭐ Идеалисты\n"
    "Круг силы: 🎭>💢>🎯>⭐>🎭\n"
    "Бьёшь по слабому типу - урон ×1.3, по сильному - ×0.7.\n\n"
    "<b>Как проходит ход</b>\n"
    "⏺ На ход дают очки действий, и потратить нужно <b>все</b>.\n"
    "Одно действие - это что-то одно:\n"
    "🔥 Атака - удар по активному персонажу врага\n"
    "🛡 Защита - щит на следующий ход врага\n"
    "🔸 Бонус - копит действия на <b>твой</b> следующий ход\n"
    "🔁 Смена - поставить другого персонажа\n"
    "ℹ Команды - показать обе колоды\n\n"
    "<b>Сколько очков</b>\n"
    "Первым ходит один игрок с 1 очком, второй - с 2.\n"
    "Дальше: раунды 2–4 - 2 очка, 5–6 - 3, потом 4.\n"
    "🔸 Бонус добавляет до +4 к следующему ходу, но всего не больше 8.\n\n"
    "<b>Атака</b>\n"
    "Бьют только активного врага. Все удары хода летят разом: если враг погиб, "
    "следующий не получает урон в этот же ход.\n\n"
    "<b>Защита</b>\n"
    "🛡 Щиты встречают атаки врага в его следующий ход, гасят их 1 к 1 и сгорают.\n\n"
    "<b>Смена</b>\n"
    "🔁 1 раз за ход и стоит 1 очко. Новый персонаж выходит <b>до</b> твоих атак.\n"
    "Если активный погиб - следующий выходит бесплатно.\n\n"
    "<b>Скрытое</b>\n"
    "Ты знаешь лишь сумму щитов и бонусов врага, но не знаешь, что из чего. "
    "Всё раскрывается, когда срабатывает.\n\n"
    "<b>Игра</b>\n"
    "📁 Колода - 3 персонажа. Бой идёт, пока у одной стороны не кончатся персонажи.\n"
    "⏳ На ход - {timeout} секунд.\n"
    "💬 За полуход каждый игрок может отправить до {comments} сообщений сопернику.\n"
    "🏆 Цель - выбить всех персонажей противника.\n\n"
    "<b>Лиги и награды:</b>\n"
    "В меню «🔱 Лиги»"
)

_ABOUT_EN = (
    "<b>❤️ Health</b> - a character's hit points\n"
    "<b>💪 Damage</b> - attack power\n\n"
    "<b>Character types:</b> 🎭 💢 🎯 ⭐\n"
    "🎭 Manipulators\n"
    "💢 Powerhouses\n"
    "🎯 Tacticians\n"
    "⭐ Idealists\n"
    "Cycle: 🎭>💢>🎯>⭐>🎭\n"
    "Hitting a weaker type deals ×1.3 damage, a stronger one ×0.7.\n\n"
    "<b>How a turn works</b>\n"
    "⏺ Each turn grants action points, and you must spend <b>all</b> of them.\n"
    "One action is exactly one of:\n"
    "🔥 Attack - strike the enemy's active character\n"
    "🛡 Defend - a shield for the enemy's next turn\n"
    "🔸 Bonus - bank actions for <b>your</b> next turn\n"
    "🔁 Switch - bring in another character\n"
    "ℹ Teams - show both decks\n\n"
    "<b>Action points</b>\n"
    "The first player starts with 1 point, the second with 2.\n"
    "Then: rounds 2–4 - 2 points, 5–6 - 3, after that 4.\n"
    "🔸 Bonus adds up to +4 to your next turn, capped at 8 total.\n\n"
    "<b>Attack</b>\n"
    "Only the enemy's active character is hit. All hits of a turn land at once: if the enemy dies, "
    "the next one takes no damage that turn.\n\n"
    "<b>Defense</b>\n"
    "🛡 Shields meet the enemy's attacks on their next turn, absorb them 1 to 1 and burn out.\n\n"
    "<b>Switch</b>\n"
    "🔁 Once per turn and costs 1 point. The new character enters <b>before</b> your attacks.\n"
    "If the active character dies, the next one enters for free.\n\n"
    "<b>Hidden information</b>\n"
    "You only know the total of the enemy's shields and bonuses, not which is which. "
    "Everything is revealed when it triggers.\n\n"
    "<b>Game</b>\n"
    "📁 Deck - 3 characters. The battle lasts until one side runs out of characters.\n"
    "⏳ {timeout} seconds per turn.\n"
    "💬 Per half-turn each player can send up to {comments} messages to the opponent.\n"
    "🏆 Goal - knock out all of the opponent's characters.\n\n"
    "<b>Leagues and rewards:</b>\n"
    "In the «🔱 Leagues» menu"
)

_PRICES_RU = (
    "🧾 <b>Информация о донатах</b>\n"
    "💵 <b>Курс</b>\n\n"
    "<blockquote>80🔮 - 100₽  -\n"
    "300🔮 - 300₽  -\n"
    "600🔮 - 500₽  7$\n"
    "1300🔮 - 1000₽  14$\n"
    "3000🔮 - 2000₽  27$\n"
    "8000🔮 - 5000₽  69$\n"
    "</blockquote>\n\n"
    "💳 Способы оплаты\n"
    "<blockquote>🌍 <b>Международная оплата</b>\n"
    "Оплата через lava долларами\n\n"
    "🇷🇺 <b>Оплата в России</b>\n"
    "Оплата через lava рублями\n"
    "</blockquote>"
)

_PRICES_EN = (
    "🧾 <b>Donation info</b>\n"
    "💵 <b>Rates</b>\n\n"
    "<blockquote>80🔮 - 100₽  -\n"
    "300🔮 - 300₽  -\n"
    "600🔮 - 500₽  7$\n"
    "1300🔮 - 1000₽  14$\n"
    "3000🔮 - 2000₽  27$\n"
    "8000🔮 - 5000₽  69$\n"
    "</blockquote>\n\n"
    "💳 Payment methods\n"
    "<blockquote>🌍 <b>International payment</b>\n"
    "Pay via lava in dollars\n\n"
    "🇷🇺 <b>Payment in Russia</b>\n"
    "Pay via lava in rubles\n"
    "</blockquote>"
)

_LEAGUE_RULES_RU = (
    "Лига считается по месту среди отранжированных игроков (10+ матчей за сезон).\n"
    "За неактивность (3+ дня без боёв) рейтинг каждый день снижается."
)

_LEAGUE_RULES_EN = (
    "Your league is your place among ranked players (10+ matches this season).\n"
    "For inactivity (3+ days without battles) your rating drops every day."
)

_WELCOME_RU = (
    "<b>Добро пожаловать в COTE megaverse!</b>\n\n"
    "Сначала выберите язык. Его можно поменять позже в меню «👤 Профиль»."
)

_WELCOME_EN = (
    "<b>Welcome to COTE megaverse!</b>\n\n"
    "First, choose your language. You can change it later in the «👤 Profile» menu."
)

LONG = {
    "ru": {
        "@about": _ABOUT_RU,
        "@prices": _PRICES_RU,
        "@league_rules": _LEAGUE_RULES_RU,
        "@welcome": _WELCOME_RU,
    },
    "en": {
        "@about": _ABOUT_EN,
        "@prices": _PRICES_EN,
        "@league_rules": _LEAGUE_RULES_EN,
        "@welcome": _WELCOME_EN,
    },
}
