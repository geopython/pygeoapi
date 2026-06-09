# =================================================================
#
# Authors: Edward Lewis <eddlewis85@gmail.com>
#
# Copyright (c) 2026 Edward Lewis
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
# Test that get_engine() separates SQLAlchemy connection-pool tuning
# options from DBAPI connect_args. This is the contract introduced by
# the configurable-pool change; it needs no live database.
# =================================================================

from unittest import mock

from pygeoapi.provider import sql


@mock.patch.object(sql, 'create_engine')
def test_get_engine_separates_pool_options_from_connect_args(mock_create):
    sql.get_engine.cache_clear()
    sql.get_engine(
        'postgresql+psycopg2', 'h', 5432, 'd', 'u', 'p', None,
        pool_size=2, pool_recycle=300, connect_timeout=10,
    )

    _, kwargs = mock_create.call_args
    # pool keys are applied to the engine (QueuePool), with overrides
    # honoured and unset pool keys falling back to the documented defaults
    assert kwargs['pool_size'] == 2
    assert kwargs['pool_recycle'] == 300
    assert kwargs['max_overflow'] == 10
    assert kwargs['pool_timeout'] == 30
    assert kwargs['pool_pre_ping'] is True
    # genuine DBAPI args are forwarded via connect_args; pool keys are not
    assert kwargs['connect_args'] == {'connect_timeout': 10}
