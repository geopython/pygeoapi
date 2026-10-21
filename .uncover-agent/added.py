#          Tom Kralidis <tomkralidis@gmail.com>
# Copyright (c) 2026 Tom Kralidis
from gettext import translation
import logging
from pathlib import Path
from typing import List, Union
LOCALEDIR = Path(__file__).resolve().parent.parent / 'locale'

# Cache gettext translations by string
_gettext_cache = {}


    if isinstance(value, str) and not nested_dicts:
        LOGGER.debug(f'Value {value} is from data, not config')
        return translate_gettext(value, language.language)

    translation_ = value.get(locale2str(language)
                             if hasattr(language, 'language') else language)

    if translation_:
        return translation_
def translate_gettext(value: str, locale_: Locale) -> str:
    """
    :param value: A string value to translate.
    :param language: A locale Babel Locale.

    :returns: A translated string or the original value.
    """

    try:
        value2 = _gettext_cache[locale_][value]
        LOGGER.debug(f'Value {value} is gettext cached')
    except KeyError:
        LOGGER.debug(f'Value {value} is NOT gettext cached')
        if locale_ not in _gettext_cache:
            _gettext_cache[locale_] = {}
        if value not in _gettext_cache[locale_]:
            tr = translation('messages',
                             localedir=LOCALEDIR,
                             languages=[locale_],
                             fallback=True)
            value2 = _gettext_cache[locale_][value] = tr.gettext(value)

    return value2


# Copyright (c) 2026 Tom Kralidis


def test_translate_gettext():
    locale_fr = Locale.parse('fr').language
    locale_es = Locale.parse('es').language

    assert l10n.translate_gettext('Home', locale_fr) == 'Accueil'
    assert l10n.translate_gettext('Home', locale_es) == 'Inicio'