"""Localization helpers (gettext-style: the Russian text is the message key).

Russian is the default locale. English translations live in
``core.locales.en``; long static blocks (about, prices, leagues, welcome) live
in ``core.locales.long`` and are referenced by ``@name`` keys.

Fallback is always the Russian source string, so a missing translation never
breaks a message - it only shows Russian.
"""

from core.locales import LONG
from core.locales.en import EN

DEFAULT_LANG = "ru"
SUPPORTED = ("ru", "en")

# Shown in the language picker (these labels are intentionally bilingual).
LANG_LABELS = {
    "ru": "🇷🇺 Русский",
    "en": "🇺🇸 English",
}


def normalize(lang: str | None) -> str:
    """Return a supported language code, defaulting to Russian."""
    return lang if lang in SUPPORTED else DEFAULT_LANG


def with_quit(lang: str | None, text: str) -> str:
    """Append the standard "/quit" hint used by every input prompt."""
    return f"{text}\n\n{t(lang, '/quit - отмена.')}"


def t(lang: str | None, key: str, **kwargs) -> str:
    """Translate ``key`` into ``lang`` and format it with ``kwargs``.

    ``key`` is either the Russian source text or an ``@name`` reference to a
    block in :mod:`core.locales.long`.
    """
    lang = normalize(lang)
    if key.startswith("@"):
        text = LONG.get(lang, {}).get(key) or LONG[DEFAULT_LANG].get(key, key)
    elif lang == "en":
        text = EN.get(key, key)
    else:
        text = key
    return text.format(**kwargs) if kwargs else text
