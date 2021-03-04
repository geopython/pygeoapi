# =================================================================
#
# Authors: Sander Schaminee <sander.schaminee@geocat.net>
#
# Copyright (c) 2021 GeoCat BV
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

import logging
from typing import Union
from collections import OrderedDict

from babel import Locale
from babel import UnknownLocaleError as _UnknownLocaleError

LOGGER = logging.getLogger(__name__)


class LocaleError(Exception):
    """ General exception for any kind of locale parsing error. """
    pass


def str2locale(value, silent: bool = False) -> Union[Locale, None]:
    """ Converts a web locale or language tag into a Babel Locale instance.

    .. note::   If `value` already is a Locale, it is returned as-is.

    :param value:   A string containing a (web) locale (e.g. 'fr-CH')
                    or language tag (e.g. 'de').
    :param silent:  If True (default = False), no errors will be raised
                    when parsing failed. Instead, `None` will be returned.
    :returns:       babel.core.Locale or None
    :raises:        LocaleError
    """
    if isinstance(value, Locale):
        return value
    try:
        return Locale.parse(value.strip().replace('-', '_'))
    except (ValueError, AttributeError):
        if not silent:
            raise LocaleError(f"invalid locale '{value}'")
    except _UnknownLocaleError as err:
        if not silent:
            raise LocaleError(err)
    return None


def locale2str(value: Locale) -> str:
    """ Converts a Babel Locale instance into a web locale string.

    :param value:   babel.core.Locale
    :returns:       A string containing a web locale (e.g. 'fr-CH')
                    or language tag (e.g. 'de').
    :raises:        LocaleError
    """
    if not isinstance(value, Locale):
        raise LocaleError(f"'{value}' is not of type {Locale.__name__}")
    return str(value).replace('_', '-')


def best_match(accept_languages, available_locales) -> Locale:
    """ Takes an Accept-Languages string (from header or request query params)
    and finds the best matching locale from a list of available locales.

    This function provides a framework-independent alternative to the
    `best_match()` function available in Flask/Werkzeug.

    If no match can be found for the Accept-Languages,
    the first available locale is returned.

    This function always returns a Babel Locale instance. If you require the
    web locale string, please use the :func:`locale2str` function.
    If you only ever need the language part of the locale, use the `language`
    property of the returned locale.

    .. note::   Any tag in the `accept_languages` string that is an invalid
                or unknown locale is ignored. However, if no
                `available_locales` are specified, a `LocaleError` is raised.

    :param accept_languages:    A Locale or string with one or more languages.
                                This can be as simple as "de" for example,
                                but it's also possible to include a territory
                                (e.g. "en-US" or "fr_BE") or even a complex
                                string with quality values, e.g.
                                "fr-CH, fr;q=0.9, en;q=0.8, de;q=0.7, *;q=0.5".
    :param available_locales:   A list containing the available locales.
                                For example, a pygeoapi provider might only
                                support ["de", "en"].
                                Locales in the list can be specified as strings
                                (e.g. "nl-NL") or `Locale` instances.
    :returns:                   babel.core.Locale
    :raises:                    LocaleError
    """

    def get_match(locale_, available_locales_):
        """ Finds the first match of `locale` in `available_locales_`. """
        if not locale_:
            return None
        territories_ = available_locales_.get(locale_.language, {})
        if locale_.territory in territories_:
            # Full match on language and territory
            return locale_
        if None in territories_:
            # Match on language only (generic, no territory)
            return Locale(locale_.language)
        if territories_:
            # Match on language but another territory (use first)
            return Locale(locale_.language, territory=territories_[0])
        # No match at all
        return None

    if not available_locales:
        raise LocaleError('No available locales specified')

    if isinstance(accept_languages, Locale):
        # If a Babel Locale was used as input, transform back into a string
        accept_languages = locale2str(accept_languages)
    if not isinstance(accept_languages, str):
        # If `accept_languages` is not a string, ignore it
        LOGGER.debug(f"ignoring invalid accept-languages '{accept_languages}'")
        accept_languages = ''

    tags = accept_languages.split(',')
    num_tags = len(tags)
    req_locales = {}
    for i, lang in enumerate(tags):
        q_raw = None
        q_out = None
        if not lang:
            continue

        # Check if complex (i.e. with quality weights)
        try:
            lang, q_raw = (v.strip() for v in lang.split(';'))
        except ValueError:
            # Tuple unpacking failed: tag is not complex (or too complex :))
            pass

        # Validate locale tag
        loc = str2locale(lang, True)
        if not loc:
            LOGGER.debug(f"ignoring invalid accept-language '{lang}'")
            continue

        # Validate quality weight (e.g. "q=0.7")
        if q_raw:
            try:
                q_out = float([v.strip() for v in q_raw.split('=')][1])
            except (ValueError, IndexError):
                # Tuple unpacking failed: not a valid q tag
                pass

        # If there's no actual q, set one based on the language order
        if not q_out:
            q_out = num_tags - i

        # Store locale
        req_locales[q_out] = loc

    # Process supported locales
    prv_locales = OrderedDict()
    for a in available_locales:
        loc = str2locale(a)
        prv_locales.setdefault(loc.language, []).append(loc.territory)

    # Return best match from accepted languages
    for _, loc in sorted(req_locales.items(), reverse=True):
        match = get_match(loc, prv_locales)
        if match:
            LOGGER.debug(f"'{match}' matches requested '{accept_languages}'")
            return match

    # Nothing matched: return the first available locale
    for lang, territories in prv_locales.items():
        match = Locale(lang, territory=territories[0])
        LOGGER.debug(f"no match for requested '{accept_languages}'; "
                     f"using first available language '{match}'")
        return match


def translate(value, language):
    """
    If `value` is a language struct (where its keys are language codes
    and its values are translations for each language), this function tries to
    find and return the translation for the given `language`.

    If the given `value` is not a dict, the original value is returned.
    If the requested language does not exist in the struct,
    the first language value is returned. If there are no valid language keys
    in the struct, the original value is returned as well.

    If `language` is not a string or Locale, a LocaleError is raised.

    :param value:       A value to translate. Typically either a string or
                        a language struct dictionary.
    :param language:    A locale string (e.g. "en-US" or "en") or Babel Locale.
    :returns:           A translated string or the original value.
    :raises:            LocaleError
    """
    if not isinstance(value, dict):
        # Perhaps use a translation service for strings at a later stage?
        # For now just return the value as-is
        return value

    # Validate language key by type (do not check if parsable)
    if not isinstance(language, (str, Locale)):
        raise LocaleError('language is not a str or Locale')

    # First try fast approach: directly fetch expected language key
    translation = value.get(locale2str(language)
                            if hasattr(language, 'language') else language)
    if translation:
        return translation

    # Find valid locale keys in language struct
    # Also maps Locale instances to actual key names
    loc_items = OrderedDict()
    for k in value.keys():
        loc = str2locale(k, True)
        if loc:
            loc_items[loc] = k

    if not loc_items:
        # No valid locale keys found: return as-is
        return value

    # Find best language match and return value by its key
    out_locale = best_match(language, loc_items)
    return value[loc_items[out_locale]]
