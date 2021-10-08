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
import pytest

from pygeoapi import l10n
from pygeoapi.util import yaml_load

from .util import get_test_file_path


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
        'id_field': 'id',  # Note: Babel parses this as "Indonesian"!
        None: 'empty key',
        42: 'numeric key',
        'fla': 'non-language key'
    }


def test_translate(language_struct, nonlanguage_struct):
    assert l10n.translate({}, 'en-US') == {}
    assert l10n.translate(42, 'fr') == 42
    assert l10n.translate(None, 'de') is None
    assert l10n.translate(['list item'], Locale('en')) == ['list item']
    assert l10n.translate({'nested dict': {'en': 1, 'fr': 2}}, 'en') == {'nested dict': {'en': 1, 'fr': 2}}  # noqa

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
        l10n.translate(language_struct, None)  # noqa
        l10n.translate(language_struct, 42)    # noqa


def test_localefromheaders():
    assert l10n.locale_from_headers({}) is None
    assert l10n.locale_from_headers({'Accept-Language': 'de'}) == 'de'
    assert l10n.locale_from_headers({'accept-language': 'en_US'}) == 'en_US'


def test_localefromparams():
    assert l10n.locale_from_params({}) is None
    assert l10n.locale_from_params({'lang': 'de'}) == 'de'
    assert l10n.locale_from_params({'language': 'en_US'}) is None
    assert l10n.locale_from_params({'lang': 'en_US'}) == 'en_US'


def test_addlocale():
    assert l10n.add_locale('http://a.pi/', None) == 'http://a.pi/'
    assert l10n.add_locale('http://a.pi/', 'en') == 'http://a.pi/?lang=en'
    assert l10n.add_locale('http://a.pi', 'de_CH') == 'http://a.pi?lang=de-CH'
    assert l10n.add_locale('http://a.pi', 'zz') == 'http://a.pi'
    assert l10n.add_locale('http://a.pi?q=1', 'nl') == 'http://a.pi?q=1&lang=nl'  # noqa
    assert l10n.add_locale('http://a.pi?lang=de', 'nl') == 'http://a.pi?lang=nl'  # noqa


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
    config['server']['language'] = ['de', 'en-US']  # noqa
    assert l10n.get_locales(config) == [Locale.parse('de'), Locale.parse('en_US')]  # noqa

    config = {
        'server': {
            'languages': []
        }
    }
    with pytest.raises(l10n.LocaleError):
        l10n.get_locales(config)

    config['server']['languages'] = [None]
    with pytest.raises(l10n.LocaleError):
        l10n.get_locales(config)

    config['server']['languages'] = ['de', 'en-US']
    assert l10n.get_locales(config) == [Locale.parse('de'), Locale.parse('en_US')]  # noqa


def test_getpluginlocale():
    assert l10n.get_plugin_locale({}, 'de') is None
    assert l10n.get_plugin_locale({}, None) is None  # noqa
    assert l10n.get_plugin_locale({}, '') is None
    assert l10n.get_plugin_locale({'language': 'de'}, 'en') == Locale('de')
    assert l10n.get_plugin_locale({'language': None}, 'en') is None
    assert l10n.get_plugin_locale({'languages': ['en']}, None) == Locale('en')  # noqa
    assert l10n.get_plugin_locale({'languages': []}, 'nl') is None
    assert l10n.get_plugin_locale({'languages': ['en']}, 'fr') == Locale('en')
    assert l10n.get_plugin_locale({'languages': ['en', 'de']}, 'de') == Locale('de')  # noqa
    assert l10n.get_plugin_locale({'languages': ['en', 'de']}, None) == Locale('en')  # noqa


def test_setresponselanguage():
    # the following should not raise (only logs warning)
    l10n.set_response_language(None, None)  # noqa

    headers = {}
    with pytest.raises(l10n.LocaleError):
        l10n.set_response_language(headers, None)  # noqa
        l10n.set_response_language(headers, None, None)  # noqa
        l10n.set_response_language(headers, None, 'rubbish')  # noqa

    l10n.set_response_language(headers, Locale('en'))
    assert headers['Content-Language'] == 'en'

    l10n.set_response_language(headers, Locale('de'))
    assert headers['Content-Language'] == 'de'

    l10n.set_response_language(headers, Locale('de'), Locale('en', 'US'))
    assert headers['Content-Language'] == 'de, en-US'

    l10n.set_response_language(headers, Locale('en'), Locale('en'))
    assert headers['Content-Language'] == 'en'


@pytest.fixture()
def config():
    with open(get_test_file_path('pygeoapi-test-config.yml')) as fh:
        return yaml_load(fh)


@pytest.fixture()
def locale_():
    return Locale.parse('en_US')


def test_translatedict(config, locale_):
    cfg = l10n.translate_struct(config, locale_, True)
    assert cfg['metadata']['identification']['title'] == 'pygeoapi default instance'  # noqa
    assert cfg['metadata']['identification']['keywords'] == ['geospatial', 'data', 'api']  # noqa

    # test full equality (must come from cache)
    cfg2 = l10n.translate_struct(config, locale_, True)
    assert cfg is cfg2

    # missing locale_ should return the same dict
    assert l10n.translate_struct(config, None) is config  # noqa

    # missing or empty dict should return an empty dict
    assert l10n.translate_struct(None, locale_) == {}  # noqa

    # test custom dict (translate from level 0, do not cache)
    test_dict = {
        'level0': {
            'en': 'test value',
            'fr': 'valeur de test'
        }
    }
    tr_dict = l10n.translate_struct(test_dict, locale_)
    assert tr_dict['level0'] == 'test value'
    tr_dict2 = l10n.translate_struct(test_dict, locale_)
    assert tr_dict == tr_dict2
    assert tr_dict is not tr_dict2

    # test mixed structure
    test_input = [
        {'test': {
            'en': 'test value',
            'fr': 'valeur de test'
        }},
        'some string',
        {'item1': 1},
        {'item2a': [
            'list_item1',
            'list_item2',
            {
                'en': 'list value',
                'fr': 'valeur de liste'
            }
        ],
         'item2b': {
            'en': 'test value',
            'fr': 'valeur de test'
        }}
    ]
    test_output = [
        {'test': 'test value'},
        'some string',
        {'item1': 1},
        {'item2a': [
            'list_item1',
            'list_item2',
            'list value'
        ],
         'item2b': 'test value'
        }
    ]
    assert l10n.translate_struct(test_input, locale_) == test_output
