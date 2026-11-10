import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MODE = os.getenv('MODE', 'production')

BASE_DIR = Path(__file__).parent

# ── Карточки/каталог в Cloudflare R2 (публичный бакет) ──
R2_PUBLIC_BASE_URL = os.getenv('R2_PUBLIC_BASE_URL', '').rstrip('/')
CHARACTERS_URL = os.getenv('CHARACTERS_URL', '')
# Картинки лежат рядом с characters.json; при необходимости переопредели явно.
CARD_IMAGES_BASE_URL = os.getenv('CARD_IMAGES_BASE_URL', '').rstrip('/') or (
    CHARACTERS_URL.rsplit('/', 1)[0] if CHARACTERS_URL else ''
)

# Запись в R2 (S3-совместимый API) - для добавления/правки персонажей через бота.
R2_ACCOUNT_ID = os.getenv('R2_ACCOUNT_ID', '')
R2_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID', '')
R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY', '')
R2_BUCKET = os.getenv('R2_BUCKET', '')
R2_ENDPOINT = os.getenv('R2_ENDPOINT', '').rstrip('/') or (
    f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com" if R2_ACCOUNT_ID else ''
)
R2_PREFIX = os.getenv('R2_PREFIX', 'data/cote').strip('/')
R2_WRITE_ENABLED = bool(R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET and R2_ENDPOINT)


def card_image(relative: str) -> str:
    """Public R2 URL for a card image."""
    if not CARD_IMAGES_BASE_URL:
        raise RuntimeError("CARD_IMAGES_BASE_URL (или CHARACTERS_URL) не настроен")
    return f"{CARD_IMAGES_BASE_URL}/{str(relative).lstrip('/')}"

if MODE == 'local':
    BOT_TOKEN = os.getenv('LOCAL_BOT_TOKEN', '')
    WEBHOOK_URL = ''
else:
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')

ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'game_bot'),
    'user': os.getenv('DB_USER', 'cote_egortop'),
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
}

DATABASE_URL = os.getenv('DATABASE_URL',
    f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")

WEBHOOK_LISTEN = os.getenv('WEBHOOK_LISTEN', '0.0.0.0')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '9080'))

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

NORMAL_SPIN_PROBS = {
    'common': 50,
    'rare': 36.25,
    'epic': 8.5,
    'mythic': 4,
    'legendary': 1.25,
}

SUPER_SPIN_PROBS = {
    'epic': 50,
    'mythic': 37.5,
    'legendary': 12.5,
}

RARITY_POINTS = {
    'common': 100,
    'rare': 200,
    'epic': 500,
    'mythic': 1500,
    'legendary': 3000,
    'special': 0,
}

RARITY_DISPLAY = {
    'common': 'обычная',
    'rare': 'редкая',
    'epic': 'эпическая',
    'mythic': 'мифическая',
    'legendary': 'легендарная',
    'special': 'специальная',
}

RUB_PRICES = {
    100: 80,
    300: 300,
    500: 600,
    1000: 1300,
    2000: 3000,
    5000: 8000,
}

USD_PRICES = {
    7: 600,
    14: 1300,
    27: 3000,
    69: 8000,
}

EUR_PRICES = {
    7: 600,
    14: 1300,
    27: 3000,
    69: 8000,
}

# ── Донаты через DonationAlerts ──
# Юзер платит уникальную сумму: номинал пачки минус небольшой «диапазон».
# Копейки/центы и есть идентификатор заказа.
DONATION_PAGE_URL = os.getenv('DONATION_PAGE_URL', 'https://dalink.to/backspace_08')
DONATION_PRICES = {'RUB': RUB_PRICES, 'USD': USD_PRICES, 'EUR': EUR_PRICES}
# Как эта валюта называется в форме DonationAlerts (её и надо выбрать).
DONATION_DA_CURRENCY = {
    'RUB': '₽ RUB',
    'USD': '$ USD',
    'EUR': '€ EUR',
}
# Диапазон в минорных единицах: обычный и аварийный (клапан при оверфлоу).
DONATION_RANGE = {'RUB': 200, 'USD': 10, 'EUR': 10}
DONATION_RANGE_OVERFLOW = {'RUB': 500, 'USD': 25, 'EUR': 25}
# DALink не принимает суммы ниже этого порога; пачки, у которых диапазон
# «вниз» упирается в порог, получают диапазон «вверх» от номинала.
DONATION_MIN_MINOR = {'RUB': 10000, 'USD': 100, 'EUR': 100}
DONATION_MATCH_HOURS = 48      # сколько сумма закреплена за заказом
DONATION_REUSE_HOURS = 72      # кулдаун перед переиспользованием суммы
DONATION_POLL_SECONDS = int(os.getenv('DONATION_POLL_SECONDS', '10'))

DONATIONALERTS_TOKEN = os.getenv('DONATIONALERTS_TOKEN', '')
DONATIONALERTS_CLIENT_ID = os.getenv('DONATIONALERTS_CLIENT_ID', '15527')
DONATIONALERTS_REDIRECT_URI = os.getenv(
    'DONATIONALERTS_REDIRECT_URI', 'http://localhost:9080/da_callback'
)
DONATIONALERTS_SCOPE = os.getenv('DONATIONALERTS_SCOPE', 'oauth-donation-index')
DONATIONALERTS_CLIENT_SECRET = os.getenv('DONATIONALERTS_CLIENT_SECRET', '')
DONATIONALERTS_REFRESH_TOKEN = os.getenv('DONATIONALERTS_REFRESH_TOKEN', '')

ANIMATED_EXTENSIONS = {'.gif', '.mp4', '.webm'}
SHARD_MAP = {
    'common': 1, 'rare': 3, 'epic': 10,
    'mythic': 20, 'legendary': 100
}

# ── Арена ──
ARENA_TURN_TIMEOUT = int(os.getenv('ARENA_TURN_TIMEOUT', '60'))  # секунд на ход
ARENA_WARN_BEFORE = int(os.getenv('ARENA_WARN_BEFORE', '15'))  # предупреждение за N сек
ARENA_COMMENTS_PER_TURN = int(os.getenv('ARENA_COMMENTS_PER_TURN', '2'))  # сообщений на игрока за полуход
ARENA_CALIBRATION_MATCHES = 10     # матчей до показа рейтинга
ARENA_MIN_MATCHES_FOR_REWARD = 10  # минимум матчей за сезон для награды
ARENA_DECAY_START_DAYS = 3         # простой до начала decay
ARENA_DECAY_PERCENT = 0.01         # % от (rating - center) в день
ARENA_DECAY_MIN = 5                # минимум снижения в день
ARENA_RESET_K = 0.5                # soft reset к центру
ARENA_RESET_RD_FLOOR = 200.0       # минимальный RD при reset
ARENA_RATING_CENTER = 1000         # якорь шкалы Glicko-2
ARENA_SEASON_WEEKS = int(os.getenv('ARENA_SEASON_WEEKS', '3'))  # длина сезона
START_SPINS = int(os.getenv('START_SPINS', '20'))               # стартовые крутки (новичок / после сброса)

# ── Магазин ──
SHOP_MIN_CARDS = int(os.getenv('SHOP_MIN_CARDS', '30'))         # доступ: не меньше N карточек
SHOP_SLOTS = int(os.getenv('SHOP_SLOTS', '3'))                  # лотов в день
SHOP_DISCOUNT = float(os.getenv('SHOP_DISCOUNT', '0.30'))       # скидка на прокачку (кроме спешлов)
SHOP_SPECIAL_COST = int(os.getenv('SHOP_SPECIAL_COST', '400'))  # спешл: фикс. цена за уровень
SHOP_RESET_HOUR_UTC = int(os.getenv('SHOP_RESET_HOUR_UTC', '0'))  # час сброса ротации (UTC)
# Глобальные веса редкостей для дневной ротации (одинаковы для всех).
# Подобрано так, чтобы спешл появлялся ~7 раз за 90 дней.
SHOP_RARITY_WEIGHTS = {
    'common': 400,
    'rare': 260,
    'epic': 165,
    'mythic': 90,
    'legendary': 50,
    'special': 17,
}

# Фразы подтверждения для опасных админ-команд
FULL_RESET_PHRASE = os.getenv('FULL_RESET_PHRASE', 'ПОЛНАЯ_ОТЧИСТКА')
CLEAR_PVP_PHRASE = os.getenv('CLEAR_PVP_PHRASE', 'ОЧИСТИТЬ_ПВП')
CLEAR_PVE_PHRASE = os.getenv('CLEAR_PVE_PHRASE', 'ОЧИСТИТЬ_ПВЕ')
RESET_BOT_PHRASE = os.getenv('RESET_BOT_PHRASE', 'СБРОС_БОТА')
RESET_ARENA_PHRASE = os.getenv('RESET_ARENA_PHRASE', 'СБРОС_АРЕНЫ')
SEASON_END_PHRASE = os.getenv('SEASON_END_PHRASE', 'КОНЕЦ_СЕЗОНА')

# Приватная 1v1 CFR-таблица (не в гите; копируется вручную/на сервере)
CFR_TABLE_PATH = os.getenv(
    'CFR_TABLE_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cote_cfr', '1v1_table.csv'),
)

# PvE / CFR
CFR_ENABLED = os.getenv('CFR_ENABLED', '1').lower() not in ('0', 'false', 'no')
CFR_DEPTH = int(os.getenv('CFR_DEPTH', '3'))
CFR_ITERS = int(os.getenv('CFR_ITERS', '120'))
CFR_CAP = int(os.getenv('CFR_CAP', '6'))
# Max simultaneous solver runs (bounded CPU spikes; leave cores for other services).
CFR_MAX_CONCURRENCY = int(os.getenv('CFR_MAX_CONCURRENCY', '1'))
# Max concurrent PvE matches (0 = unlimited). Bounds memory + sustained load.
CFR_MAX_ACTIVE = int(os.getenv('CFR_MAX_ACTIVE', '0'))

# ── Прокачка персонажей ──
MAX_CHARACTER_LEVEL = 10
# Полная стоимость прокачки карты с 1 до MAX_CHARACTER_LEVEL, в осколках.
CHARACTER_LEVEL_COST = {
    'common': 400,
    'rare': 800,
    'epic': 1350,
    'mythic': 2160,
    'legendary': 3600,
    'special': 3600,
}


LAVA_API_KEY = os.getenv('LAVA_API_KEY', '')
LAVA_WEBHOOK_SECRET = os.getenv('LAVA_WEBHOOK_SECRET', '')
LAVA_OFFER_ID = os.getenv('LAVA_OFFER_ID', '')
LAVA_WH_URL = os.getenv('LAVA_WH_URL', '')
