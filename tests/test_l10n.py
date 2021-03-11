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

from babel import Locale
from pygeoapi import l10n

import pytest


def test_str2locale():
    us_locale = Locale.parse('en_US')
    assert l10n.str2locale('en') == Locale.parse('en')
    assert l10n.str2locale('en_US') == us_locale
    assert l10n.str2locale('en-US') == us_locale
    assert l10n.str2locale('eng_CA') == Locale.parse('en_CA')
    assert l10n.str2locale(' fr-CH ') == Locale.parse('fr_CH')
    assert l10n.str2locale(us_locale) is us_locale

    assert l10n.str2locale(None, True) is None
    assert l10n.str2locale(42, True) is None
    assert l10n.str2locale('is_BS', True) is None

    with pytest.raises(l10n.LocaleError):
        for v in ('', None, 1, 42.0, 'is_BS', 'eng;CAN'):
            l10n.str2locale(v)


def test_locale2str():
    assert l10n.locale2str(Locale.parse('en_US')) == 'en-US'
    assert l10n.locale2str(Locale.parse('fr')) == 'fr'

    with pytest.raises(l10n.LocaleError):
        for v in (None, 1, 42.0, 'is_BS', object()):
            l10n.locale2str(v)  # noqa


def test_bestmatch():
    assert l10n.best_match('de', ('en',)) == Locale('en')
    assert l10n.best_match(None, ['en', 'de']) == Locale('en')  # noqa
    assert l10n.best_match('', ['en', 'de']) == Locale('en')
    assert l10n.best_match('de-DE', ['en', 'de']) == Locale('de')
    assert l10n.best_match('de-DE, en', ['en', 'de']) == Locale('de')
    assert l10n.best_match('de, en', ['en_US', 'de-DE']) == Locale.parse('de_DE')  # noqa

    assert l10n.best_match(Locale('de'), ['nl', 'de']) == Locale('de')

    accept = "fr-CH, fr;q=0.9, en;q=0.8, de;q=0.7, *;q=0.5"
    assert l10n.best_match(accept, ['fr', 'en']) == Locale('fr')
    assert l10n.best_match(accept, ['it', 'de']) == Locale('de')
    assert l10n.best_match(accept, ['fr-BE', 'fr']) == Locale('fr')
    assert l10n.best_match(accept, ['fr-BE', 'fr-FR']) == Locale.parse('fr_BE')
    assert l10n.best_match(accept, ['fr-BE', 'fr-FR']) == Locale.parse('fr_BE')
    assert l10n.best_match(accept, ['it', 'es']) == Locale('it')
    assert l10n.best_match(accept, ['it', 'es']) == Locale('it')
    assert l10n.best_match(accept, ('it', 'es')) == Locale('it')

    with pytest.raises(l10n.LocaleError):
        l10n.best_match(accept, [])
        l10n.best_match(accept, None)
        l10n.best_match(accept, 42)
        l10n.best_match(accept, ['is_BS'])


@pytest.fixture()
def language_struct():
    return {k: Locale.parse(k).display_name for k in (
        'en', 'fr', 'en_US', 'fr_BE', 'alb', 'nl_BE'
    )}


@pytest.fixture()
def nonlanguage_struct():
    return {
        None: 'empty key',
        42: 'numeric key',
        'fla': 'non-language key'
    }


def test_translate(language_struct, nonlanguage_struct):
    assert l10n.translate({}, 'en-US') == {}
    assert l10n.translate(42, 'fr') == 42
    assert l10n.translate(None, 'de') is None

    assert l10n.translate(nonlanguage_struct, 'fr') == nonlanguage_struct
    assert l10n.translate(nonlanguage_struct, 'fla') == 'non-language key'

    assert l10n.translate(language_struct, 'en') == 'English'
    assert l10n.translate(language_struct, 'en-US') == 'English (United States)'  # noqa
    assert l10n.translate(language_struct, 'sq_AL') == Locale.parse('alb').display_name  # noqa
    assert l10n.translate(language_struct, 'fr_CH') == Locale.parse('fr').display_name  # noqa
    assert l10n.translate(language_struct, 'nl') == Locale.parse('nl_BE').display_name  # noqa
    assert l10n.translate(language_struct, 'de') == 'English'

    assert l10n.translate(language_struct, Locale('en')) == 'English'
    assert l10n.translate(language_struct, Locale.parse('en_US')) == 'English (United States)'  # noqa

    with pytest.raises(l10n.LocaleError):
        l10n.translate(language_struct, None)
        l10n.translate(language_struct, 42)


def test_localefromheaders():
    assert l10n.locale_from_headers({}) is None
    assert l10n.locale_from_headers({'Accept-Language': 'de'}) == 'de'
    assert l10n.locale_from_headers({'accept-language': 'en_US'}) == 'en_US'


def test_localefromparams():
    assert l10n.locale_from_params({}) is None
    assert l10n.locale_from_params({'l': 'de'}) == 'de'
    assert l10n.locale_from_params({'language': 'en_US'}) is None
    assert l10n.locale_from_params({'l': 'en_US'}) == 'en_US'


def test_addlocale():
    assert l10n.add_locale('http://a.pi/', None) == 'http://a.pi/'
    assert l10n.add_locale('http://a.pi/', 'en') == 'http://a.pi/?l=en'
    assert l10n.add_locale('http://a.pi', 'de_CH') == 'http://a.pi?l=de-CH'
    assert l10n.add_locale('http://a.pi', 'zz') == 'http://a.pi'
    assert l10n.add_locale('http://a.pi?q=1', 'nl') == 'http://a.pi?q=1&l=nl'
    assert l10n.add_locale('http://a.pi?l=de', 'nl') == 'http://a.pi?l=nl'


def test_getlocales():
    config = {
        'server': {
            'language': ''
        }
    }
    with pytest.raises(l10n.LocaleError):
        l10n.get_locales({})
        l10n.get_locales(config)
        config['server']['language'] = 'zz'
        l10n.get_locales(config)

    config['server']['language'] = 'en-US'
    assert l10n.get_locales(config) == [Locale.parse('en_US')]
    config['server']['language'] = 'de_CH'
    assert l10n.get_locales(config) == [Locale.parse('de_CH')]

    config = {
        'server': {
            'languages': []
        }
    }
    with pytest.raises(l10n.LocaleError):
        l10n.get_locales(config)
        config['server']['languages'] = [None]
    config['server']['languages'] = ['de', 'en-US']
    assert l10n.get_locales(config) == [Locale.parse('de'), Locale.parse('en_US')]  # noqa


def test_getpluginlocale():
    assert l10n.get_plugin_locale({}, 'de') is None
    assert l10n.get_plugin_locale({}, None) is None  # noqa
    assert l10n.get_plugin_locale({}, '') is None
    assert l10n.get_plugin_locale({'languages': ['en']}, None) == Locale('en')  # noqa
    assert l10n.get_plugin_locale({'languages': []}, 'nl') is None
    assert l10n.get_plugin_locale({'languages': ['en']}, 'fr') == Locale('en')
    assert l10n.get_plugin_locale({'languages': ['en', 'de']}, 'de') == Locale('de')  # noqa
