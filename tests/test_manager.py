from typing import Dict

import pytest

from pygeoapi.process.manager.base import (
    get_manager,
    UnknownProcessError,
)


@pytest.fixture()
def config() -> Dict:
    return {
        'server': {
            'manager': {
                'name': 'TinyDB',
                'output_dir': '/tmp',
            }
        },
        'resources': {
            'hello-world': {
                'type': 'process',
                'processor': {
                    'name': 'HelloWorld'
                }
            }
        }
    }


def test_get_manager(config):
    manager = get_manager(config)
    assert manager.name == config['server']['manager']['name']
    assert 'hello-world' in manager.processes


def test_get_processor(config):
    manager = get_manager(config)
    process_id = 'hello-world'
    processor = manager.get_processor(process_id)
    assert processor.metadata["id"] == process_id


def test_get_processor_raises_exception(config):
    manager = get_manager(config)
    with pytest.raises(expected_exception=UnknownProcessError):
        manager.get_processor('foo')
