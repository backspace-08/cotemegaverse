"""English translations, keyed by the Russian source text.

Missing keys fall back to the Russian source (see ``core.i18n.t``), so this
table can grow incrementally without breaking anything.
"""

EN = {
    # ── Menu / shared UI ──────────────────────────────────────────────
    "🏆 Топ": "🏆 Top",
    "🎴 Получить перса": "🎴 Get a character",
    "🧧 Получить перса": "🧧 Get a character",
    "🎭 Мои персы": "🎭 My characters",
    "👤 Профиль": "👤 Profile",
    "🔄 Осколки": "🔄 Shards",
    "💸 Донат": "💸 Donate",
    "🛒 Магазин": "🛒 Shop",
    "📰 Новости КП": "📰 COTE News",
    "⚔️ Арена": "⚔️ Arena",
    "↩️ В меню": "↩️ Menu",
    "🏠 В меню": "🏠 Menu",
    "⬅️ Назад": "⬅️ Back",
    "↩️ Назад": "↩️ Back",
    "↩️ В меню редкостей": "↩️ Rarities",
    "↩ В меню редкостей": "↩ Rarities",
    "Игрок": "Player",
    "Пусто": "Empty",
    "🥷Имя: {name}\n💠 Очки: {points}\n🔮 Осколки: {shards}":
        "🥷Name: {name}\n💠 Points: {points}\n🔮 Shards: {shards}",
    "Произошла ошибка. Пожалуйста, попробуйте еще раз.": "Something went wrong. Please try again.",
    "⌛ Время действия кнопки истекло. Используйте /menu для нового запроса.":
        "⌛ This button has expired. Use /menu to start again.",

    # ── Rarities ──────────────────────────────────────────────────────
    "Обычные": "Common",
    "Редкие": "Rare",
    "Эпические": "Epic",
    "Мифические": "Mythic",
    "Легендарные": "Legendary",
    "Специальные": "Special",
    "обычная": "common",
    "редкая": "rare",
    "эпическая": "epic",
    "мифическая": "mythic",
    "легендарная": "legendary",
    "специальная": "special",
    "Редкость - {rarity}": "Rarity - {rarity}",

    # ── Leagues ───────────────────────────────────────────────────────
    "Мастер": "Master",
    "Алмазная": "Diamond",
    "Золотая": "Gold",
    "Серебряная": "Silver",
    "Бронзовая": "Bronze",
    "Без лиги": "Unranked",
    "топ {pct}%, место {rank}/{total}": "top {pct}%, place {rank}/{total}",
    "место {rank}/{total}": "place {rank}/{total}",
    "🔱 <b>Лиги</b>": "🔱 <b>Leagues</b>",
    "Ваша лига - {league}": "Your league - {league}",
    "До конца сезона: {time}": "Season ends in: {time}",
    "{n} дн.": "{n} d",
    "{n} ч.": "{n} h",
    "{n} мин.": "{n} min",
    "Лига - награда - место": "League - reward - place",
    "топ 5%": "top 5%",
    "топ 10%": "top 10%",
    "топ 30%": "top 30%",
    "топ 60%": "top 60%",
    "остальные": "the rest",

    # ── Start / onboarding ────────────────────────────────────────────
    "Выберите язык / Choose your language:": "Choose your language / Выберите язык:",
    "Это ваш первый персонаж:": "This is your first character:",
    "Вы уже получили первого персонажа": "You already received your first character",
    "Язык изменён на русский 🇷🇺": "Language set to Russian 🇷🇺",
    "Язык изменён на английский 🇺🇸": "Language set to English 🇺🇸",
    "❌ Неизвестный язык": "❌ Unknown language",

    # ── Top ───────────────────────────────────────────────────────────
    "Выберите топ:": "Choose a ranking:",
    "По очкам 💠": "By points 💠",
    "По рейтингу 🏆": "By rating 🏆",
    "вот топ по очкам сейчас": "points leaderboard",
    "вот топ по арене сейчас": "arena leaderboard",
    "⚡ {user}, {title}:\n➖➖➖➖➖➖\n{lines}\n➖➖➖➖➖➖\n⏺️ Твое место - {position}":
        "⚡ {user}, {title}:\n➖➖➖➖➖➖\n{lines}\n➖➖➖➖➖➖\n⏺️ Your place - {position}",
    "{pos}. {name} - <em><b>{value} pts</b></em>": "{pos}. {name} - <em><b>{value} pts</b></em>",

    # ── Gacha ─────────────────────────────────────────────────────────
    "🎴 Количество круток: {spins} ": "🎴 Spins: {spins} ",
    "\n🧧 Количество супер круток: {super_spins}": "\n🧧 Super spins: {super_spins}",
    "⏳ Подождите ещё {hours}ч {minutes}м": "⏳ Wait {hours}h {minutes}m",
    "У вас недостаточно круток": "You don't have enough spins",
    "Новый персонаж:": "New character:",
    "Повторка:": "Duplicate:",

    # ── Characters ────────────────────────────────────────────────────
    "Выберите редкость:": "Choose a rarity:",
    "У вас нет персонажей этой редкости": "You have no characters of this rarity",
    "Неизвестная редкость": "Unknown rarity",
    "🛒 Спешлы качаются только в магазине": "🛒 Specials level up only in the shop",
    "Недостаточно осколков: нужно {cost}🔮": "Not enough shards: {cost}🔮 needed",
    "Уже максимальный уровень": "Already at max level",
    "Не удалось улучшить персонажа": "Could not upgrade the character",
    "Персонаж не найден": "Character not found",
    "Уровень повышен до {level}/{max}!": "Level up to {level}/{max}!",
    "👑 Максимальный уровень ({level})": "👑 Max level ({level})",
    "🛒 Только в магазине": "🛒 Shop only",
    "⬆️ Улучшить до Lv.{level} - {cost}🔮": "⬆️ Upgrade to Lv.{level} - {cost}🔮",

    # ── Exchange ──────────────────────────────────────────────────────
    "🎴Количество круток: {spins}\n🔮Количество осколков: {shards}\n"
    "🧧Количество супер круток: {super_spins}\n🔄Обменный курс: \n🎴1=🔮10\n🧧1=🔮80\n"
    "Супер крутки - крутки, в которых гарантирован минимум эпический персонаж. "
    "Шанс на легендарного персонажа выше в 10 раз":
        "🎴Spins: {spins}\n🔮Shards: {shards}\n🧧Super spins: {super_spins}\n"
        "🔄Exchange rate: \n🎴1=🔮10\n🧧1=🔮80\n"
        "Super spins guarantee at least an epic character. "
        "The legendary chance is 10 times higher",
    "У вас недостаточно осколков": "You don't have enough shards",
    "🎴{count} {word}": "🎴{count} {word}",
    "🧧{count} супер-{word}": "🧧{count} super-{word}",
    "Теперь у вас\n{gained}\n🔮{shards} {word}": "You now have\n{gained}\n🔮{shards} {word}",
    "10🔮 на 1🎴": "10🔮 for 1🎴",
    "80🔮 на 1🧧": "80🔮 for 1🧧",
    "50🔮 на 5🎴": "50🔮 for 5🎴",
    "400🔮 на 5🧧": "400🔮 for 5🧧",
    "100🔮 на 10🎴": "100🔮 for 10🎴",
    "800🔮 на 10🧧": "800🔮 for 10🧧",
    "все🔮 на 🎴": "all🔮 for 🎴",
    "все🔮 на 🧧": "all🔮 for 🧧",

    # ── Donate ────────────────────────────────────────────────────────
    "📝Пользовательское соглашение": "📝User agreement",
    "Неизвестная валюта": "Unknown currency",
    "Нажмите на сумму для оплаты.": "Tap an amount to pay.",
    "🔄 Создание счёта...": "🔄 Creating an invoice...",
    "Ошибка создания счёта. Попробуйте позже.": "Failed to create an invoice. Try again later.",
    "💳 Оплатить": "💳 Pay",
    "🔮 {shards} осколков за {amount}{currency}\n\nНажмите «Оплатить» для перехода к платёжной системе.":
        "🔮 {shards} shards for {amount}{currency}\n\nTap «Pay» to open the payment system.",
    "🇷🇺 Рубли": "🇷🇺 Rubles",
    "🇺🇸 Доллары": "🇺🇸 Dollars",
    "🇪🇺 Евро": "🇪🇺 Euro",
    "💸 <b>Донат</b>\n\nВыбери валюту. Оплатить нужно ровно в той же валюте, "
    "которую выберешь здесь.":
        "💸 <b>Donate</b>\n\nChoose a currency. You must pay in exactly the same "
        "currency you pick here.",
    "💸 <b>Донат</b> · {currency}\n\nВыбери количество:":
        "💸 <b>Donate</b> · {currency}\n\nChoose the amount:",
    "💳 <b>Платёжная заявка</b>\n\n"
    "{shards}🔮 за <code>{number}</code> {symbol}\n"
    "Действует ещё {left}.\n\n"
    "На странице доната:\n"
    "1) валюта - {currency};\n"
    "2) сумма - <code>{number}</code>.\n\n"
    "⚠️ Другая валюта или сумма - платёж уйдёт на ручную проверку.":
        "💳 <b>Payment order</b>\n\n"
        "{shards}🔮 for <code>{number}</code> {symbol}\n"
        "Valid for another {left}.\n\n"
        "On the donation page:\n"
        "1) currency - {currency};\n"
        "2) amount - <code>{number}</code>.\n\n"
        "⚠️ A different currency or amount goes to manual review.",
    "{hours} ч {minutes} мин": "{hours} h {minutes} min",
    "{minutes} мин": "{minutes} min",
    "Сейчас нет свободных сумм, попробуй через пару минут":
        "No free amounts right now, try again in a couple of minutes",
    "Неизвестный вариант": "Unknown option",
    "Заявка отменена": "Order cancelled",
    "Заявка отменена. Если платёж уже в пути, он всё равно зачтётся.":
        "Order cancelled. If the payment is already on its way, it will still be credited.",
    "Не найдено": "Not found",
    "✅ Зачтено: +{shards}🔮": "✅ Credited: +{shards}🔮",
    "Этот платёж уже разобран": "This payment is already resolved",
    "🌐 Открыть страницу доната": "🌐 Open the donation page",
    "❌ Отменить заявку": "❌ Cancel the order",
    "✅ Это мой платёж": "✅ It's my payment",
    "✅ Донат получен: {amount} → +{shards}🔮": "✅ Donation received: {amount} → +{shards}🔮",
    "💸 Пришёл платёж на {amount}. Это твой? Подтверди, чтобы зачесть.":
        "💸 A payment of {amount} arrived. Is it yours? Confirm to get credited.",
    "↩️ К валютам": "↩️ Currencies",
    "{flag} <b>{currency}</b>\n\n<blockquote>{prices}</blockquote>\n\nНажмите на сумму для оплаты.":
        "{flag} <b>{currency}</b>\n\n<blockquote>{prices}</blockquote>\n\nTap an amount to pay.",

    # ── Shop ──────────────────────────────────────────────────────────
    "🛒 <b>Магазин</b>": "🛒 <b>Shop</b>",
    "💠 Цена: {price}🔮": "💠 Price: {price}🔮",
    "\n🔄 Обновится через {time}": "\n🔄 Refreshes in {time}",
    "{hours}ч {minutes}м": "{hours}h {minutes}m",
    "🛒 Магазин пуст - нет карт для прокачки.": "🛒 The shop is empty - no cards to upgrade.",
    "🔒 Магазин откроется с {count} карточек - осталось ещё {left}":
        "🔒 The shop unlocks at {count} cards - {left} to go",
    "🔄 Магазин обновился": "🔄 Shop refreshed",
    "🔄 <i>Ассортимент обновился.</i>": "🔄 <i>The assortment has been refreshed.</i>",
    "✅ Уже куплено": "✅ Already purchased",
    "👑 Максимальный уровень": "👑 Max level",
    "Лот недоступен": "Lot unavailable",
    "Не удалось купить": "Purchase failed",
    "🛒 Купить": "🛒 Buy",
    "✅ Куплено": "✅ Purchased",

    # ── Profile ───────────────────────────────────────────────────────
    "Профиль не найден": "Profile not found",
    "🥷 Имя: {name}\n💠 Очки: {points}\n🎴 Количество круток: {spins}\n"
    "🔮 Количество осколков: {shards}\n🧧 Количество супер круток: {super_spins}\n"
    "📅 Дата создания аккаунта: {created}\n{league}\n{rating}\n"
    "⚔️ PvP-матчи:\n"
    "🏆 Победы: {wins} | 💀 Поражения: {losses}\n"
    "📊 Винрейт: {winrate}% (всего игр: {games})":
        "🥷 Name: {name}\n💠 Points: {points}\n🎴 Spins: {spins}\n"
        "🔮 Shards: {shards}\n🧧 Super spins: {super_spins}\n"
        "📅 Account created: {created}\n{league}\n{rating}\n"
        "⚔️ PvP matches:\n"
        "🏆 Wins: {wins} | 💀 Losses: {losses}\n"
        "📊 Winrate: {winrate}% (total games: {games})",
    "🎯 Калибровка {matches}/{total}": "🎯 Calibration {matches}/{total}",
    "🏅 Лига - {league}": "🏅 League - {league}",
    "⚔️ Рейтинг - {rating}": "⚔️ Rating - {rating}",
    "🏅 Лига - {league} ({position})": "🏅 League - {league} ({position})",
    "🌐 Язык": "🌐 Language",
    "🎯 Калибровка {matches}/{total} · {league}": "🎯 Calibration {matches}/{total} · {league}",

    # ── Arena: menu / static ──────────────────────────────────────────
    "⚔️ В бой": "⚔️ Fight",
    "🤖 Бой с ботом": "🤖 Fight the bot",
    "🔱 Лиги": "🔱 Leagues",
    "🎴 Колоды\u00A0": "🎴 Decks\u00A0",
    "🧩 Об арене": "🧩 About arena",
    "⚔️ Начать бой": "⚔️ Start battle",
    "❌ Покинуть очередь": "❌ Leave queue",
    "Твоя колода": "Your deck",
    "⚔️ Ваш рейтинг: {rating} {emoji} ({position})":
        "⚔️ Your rating: {rating} {emoji} ({position})",
    "⏳ Если поиск слишком долгий, попробуйте перезайти в него\nИщем соперника...\n\n"
    "🟢 Сейчас в арене: {total} (в поиске: {queued})":
        "⏳ If the search takes too long, try leaving and re-entering it\nLooking for an opponent...\n\n"
        "🟢 In the arena now: {total} (searching: {queued})",

    # ── Arena: queue / matches ────────────────────────────────────────
    "❌ Колода не готова. Выберите 3 карточки": "❌ Deck is not ready. Pick 3 cards",
    "❌ Ваша колода не готова. Выберите 3 карточки": "❌ Your deck is not ready. Pick 3 cards",
    "❌ Вы уже находитесь в битве!": "❌ You are already in a battle!",
    "❌ Вы уже в поиске противника": "❌ You are already searching for an opponent",
    "❌ Вы находитесь в битве или в поиске!": "❌ You are in a battle or searching!",
    "Вы вышли из поиска противника": "You left the matchmaking queue",
    "🤖 PvE временно недоступно": "🤖 PvE is temporarily unavailable",
    "⏳ Сервер занят, попробуйте позже": "⏳ The server is busy, try again later",
    "Соперник": "Opponent",
    "🤖 Бот": "🤖 Bot",
    "Первый ход - вы": "First move - you",
    "Первый ход - противник": "First move - opponent",
    "Первый ход - {who}": "First move - {who}",
    "вы": "you",
    "противник": "opponent",
    "Ход противника": "Opponent's turn",
    "Ваш ход": "Your turn",
    "⏳ Осталось {seconds} секунд на ход!": "⏳ {seconds} seconds left for your turn!",
    "Этот бой уже завершён": "This battle is already over",
    "Сейчас ход противника": "It's the opponent's turn now",
    "Максимально возможный бонус": "Maximum possible bonus",
    "Смена недоступна": "Switch is unavailable",
    "Недоступный персонаж": "Unavailable character",
    "⚠️ За полуход можно отправить не больше {count} сообщений.":
        "⚠️ You can send at most {count} messages per half-turn.",
    "💬 <b>{name}</b>: {text}": "💬 <b>{name}</b>: {text}",

    # ── Arena: results ────────────────────────────────────────────────
    "🏆 Тестовый бой: победа!": "🏆 Test battle: victory!",
    "💀 Тестовый бой: поражение.": "💀 Test battle: defeat.",
    "Вы не успели выбрать действия": "You ran out of time to choose actions",
    "🏆 Вы победили бота!": "🏆 You beat the bot!",
    "💀 Вы проиграли боту.": "💀 You lost to the bot.",
    "🤖 Рейтинг бота: {rating} ({delta:+d})": "🤖 Bot rating: {rating} ({delta:+d})",
    "Калибровка": "Calibration",
    "+{delta} рейтинга 🏆": "+{delta} rating 🏆",
    "-{delta} рейтинга 🏆": "-{delta} rating 🏆",
    "Противник не успел выбрать действия": "The opponent ran out of time to choose actions",
    "Вы победили <b>{name}</b>!{extra}\n{line}": "You defeated <b>{name}</b>!{extra}\n{line}",
    "Вы проиграли <b>{name}</b>!{extra}\n{line}": "You lost to <b>{name}</b>!{extra}\n{line}",
    "🤖 Бот: рейтинг {rating}\n🏆 Победы: {wins} | 💀 Поражения: {losses}\n"
    "📊 Винрейт: {winrate}% (всего игр: {games})":
        "🤖 Bot: rating {rating}\n🏆 Wins: {wins} | 💀 Losses: {losses}\n"
        "📊 Winrate: {winrate}% (total games: {games})",
    "🏆 Победы: {wins} | 💀 Поражения: {losses}\n"
    "📊 Винрейт против бота: {winrate}% (всего игр: {games})":
        "🏆 Wins: {wins} | 💀 Losses: {losses}\n"
        "📊 Winrate vs bot: {winrate}% (total games: {games})",

    # ── Arena: battle rendering ───────────────────────────────────────
    "Урон противника:": "Enemy damage:",
    "Ваш урон:": "Your damage:",
    "Очки действия: {points}": "Action points: {points}",
    "🔥 Атака: {count}": "🔥 Attack: {count}",
    "🛡️ Защита: {count}": "🛡️ Defense: {count}",
    "🔸 Бонус: {count}/4": "🔸 Bonus: {count}/4",
    "Вражеский": "Enemy's",
    "Вражеская": "Enemy's",
    "Вражеские": "Enemy's",
    "Ваш": "Your",
    "Ваша": "Your",
    "Ваши": "Your",
    "Блок! 🛡": "Block! 🛡",
    "Нанесено {damage} урона": "Dealt {damage} damage",
    "У {name} осталось ❤️ {hp}": "{name} has ❤️ {hp} left",
    "{name} {verb} ☠": "{name} {verb} ☠",
    "Ходы противника: {spent} + {bank}🔸": "Enemy actions: {spent} + {bank}🔸",
    "Вступает в бой:": "Enters the battle:",
    "У противника вступает в бой:": "The enemy brings in:",
    "Вы выбрали:": "You chose:",
    "Противник выбрал:": "The opponent chose:",
    "Побежден ☠": "Defeated ☠",
    "Останется ❤️ {hp}": "❤️ {hp} left",
    "🔁 Смена": "🔁 Switch",
    "ℹ Команды": "ℹ Teams",
    "🔥 Атака\u00A0": "🔥 Attack\u00A0",
    "🛡️ Защита\u00A0": "🛡️ Defend\u00A0",
    "🔸 Бонус\u00A0": "🔸 Bonus\u00A0",

    # ── Arena: decks ──────────────────────────────────────────────────
    "✏️ Название": "✏️ Name",
    "🗑️ Очистить": "🗑️ Clear",
    "❌ Выбран\u00A0": "❌ Selected\u00A0",
    "✅ Выбрать\u00A0": "✅ Select\u00A0",
    "/quit - отмена.": "/quit - cancel.",
    "Введите новое название колоды (до 32 символов).":
        "Enter a new deck name (up to 32 characters).",
    "Введите название текстом.": "Enter a name as text.",
    "Введите новое название колоды": "Enter a new deck name",
    "{name} - основная": "{name} - main",
    "Колода": "Deck",
    "Колода {index}": "Deck {index}",
    "Колода 1": "Deck 1",
    "Персонаж уже выбран": "This character is already selected",

    # ── Arena: proactive notifications ───────────────────────────────
    "🏁 Сезон арены окончен!\nЛига - {league}\nМесто - {place}/{total}\n"
    "📊 Рейтинг - {rating}\nНаграды - 🔮{shards}, 🎴{spins}":
        "🏁 Arena season is over!\nLeague - {league}\nPlace - {place}/{total}\n"
        "📊 Rating - {rating}\nRewards - 🔮{shards}, 🎴{spins}",
    "🏁 Сезон арены окончен!\nЛига - {league}": "🏁 Arena season is over!\nLeague - {league}",
    "<b>Арена</b>\n📉 Ваш рейтинг снижен из-за неактивности: {old:.0f} → {new:.0f} (−{delta:.0f}).\n"
    "Сыграйте бой, чтобы остановить снижение.":
        "<b>Arena</b>\n📉 Your rating dropped due to inactivity: {old:.0f} → {new:.0f} (−{delta:.0f}).\n"
        "Play a battle to stop the decay.",
    "⚠️ Бот обновился - текущие бои арены отменены.\n"
    "Рейтинг не изменён, можно начать заново.":
        "⚠️ The bot was updated - current arena battles are cancelled.\n"
        "Ratings were not changed; you can start again.",

    # ── Payments ─────────────────────────────────────────────────────
    "Не удалось получить ссылку на оплату.": "Failed to get the payment link.",
    "✅ Оплата получена!\nНачислено 🔮 {shards} осколков.":
        "✅ Payment received!\n🔮 {shards} shards added.",
}
