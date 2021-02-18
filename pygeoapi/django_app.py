#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def config():
    from pygeoapi.util import yaml_load

    if not os.environ.get('PYGEOAPI_CONFIG'):
        raise RuntimeError('PYGEOAPI_CONFIG environment variable not set')

    with open(os.environ.get('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
        CONFIG = yaml_load(fh)

    return CONFIG


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_pygeoapi.settings')
    django_app_path = Path(os.path.dirname(__file__))
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    CONFIG = config()
    sys.argv = [str(django_app_path / "django_app.py"),
                "runserver",
                f"{CONFIG['server']['bind'].get('host')}:"
                f"{CONFIG['server']['bind'].get('port')}"]
    sys.path.append(str(django_app_path))
    
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
