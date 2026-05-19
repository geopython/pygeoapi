# =================================================================
# Tests for configurable SQLAlchemy connection-pool options on the
# SQL provider. These exercise store_db_parameters() directly and do
# not require a live database, so they run in standard CI.
# =================================================================

import pytest

from pygeoapi.provider.sql import store_db_parameters


class _Dummy:
    """Minimal stand-in for a provider/manager instance."""
    default_port = 5432


CONN = {'host': 'h', 'dbname': 'd', 'user': 'u', 'password': 'p'}


def test_pool_options_defaults_preserve_current_behaviour():
    obj = _Dummy()
    store_db_parameters(obj, dict(CONN), {})
    pool = dict(obj.db_pool_options)
    # Defaults must match pre-existing effective behaviour:
    # pool_pre_ping was hardcoded True; pool_recycle was unset (-1).
    assert pool['pool_size'] == 5
    assert pool['max_overflow'] == 10
    assert pool['pool_timeout'] == 30
    assert pool['pool_pre_ping'] is True
    assert pool['pool_recycle'] == -1


def test_pool_options_are_overridable_and_typed():
    obj = _Dummy()
    store_db_parameters(
        obj, dict(CONN),
        {'pool_size': 2, 'max_overflow': 3, 'pool_recycle': 300},
    )
    pool = dict(obj.db_pool_options)
    assert pool['pool_size'] == 2 and isinstance(pool['pool_size'], int)
    assert pool['max_overflow'] == 3
    assert pool['pool_recycle'] == 300
    # untouched keys keep defaults
    assert pool['pool_timeout'] == 30
    assert pool['pool_pre_ping'] is True


def test_pool_options_not_leaked_to_dbapi_connect_args():
    obj = _Dummy()
    store_db_parameters(
        obj, dict(CONN),
        {'connect_timeout': 10, 'pool_size': 2, 'pool_recycle': 300},
    )
    for k in ('pool_size', 'max_overflow', 'pool_recycle',
              'pool_timeout', 'pool_pre_ping'):
        assert k not in obj.db_options
    # genuine DBAPI connect args still pass through
    assert obj.db_options['connect_timeout'] == 10


def test_dict_valued_options_still_filtered():
    obj = _Dummy()
    store_db_parameters(
        obj, dict(CONN),
        {'pool_size': 2, 'zoom': {'min': 0, 'max': 22}},
    )
    assert 'zoom' not in obj.db_options
    assert dict(obj.db_pool_options)['pool_size'] == 2


def test_pool_options_hashable_and_deterministic():
    a, b = _Dummy(), _Dummy()
    store_db_parameters(a, dict(CONN), {'pool_size': 2})
    store_db_parameters(b, dict(CONN), {'pool_size': 2})
    # identical config -> identical key -> shared engine via functools.cache
    assert a.db_pool_options == b.db_pool_options
    assert hash(a.db_pool_options) == hash(b.db_pool_options)

    c = _Dummy()
    store_db_parameters(c, dict(CONN), {'pool_size': 9})
    # differing pool config -> distinct key (separate engine, by design)
    assert c.db_pool_options != a.db_pool_options


def test_pool_options_coexist_with_search_path():
    obj = _Dummy()
    store_db_parameters(
        obj, dict(CONN),
        {'search_path': ['published', 'public'], 'pool_size': 4},
    )
    assert obj.db_search_path == ('published', 'public')
    assert dict(obj.db_pool_options)['pool_size'] == 4


@pytest.mark.parametrize('bad', [{'pool_size': 'two'}])
def test_non_integer_pool_value_raises(bad):
    # type coercion surfaces bad config loudly rather than silently
    with pytest.raises(ValueError):
        store_db_parameters(_Dummy(), dict(CONN), bad)
