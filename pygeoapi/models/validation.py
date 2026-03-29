# =================================================================
#
# Authors: Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2026 Francesco Bartoli
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

"""
Validation utilities for dataclass models.

Provides runtime type checking that matches validation
behaviour, using standard library only.
"""

from dataclasses import fields as dc_fields
from typing import Any, get_type_hints


def validate_type(dc_instance: Any) -> None:
    """
    Validate field types on a dataclass instance.

    Checks each field value against its declared type,
    matching pydantic's runtime type validation behaviour.
    Supports Optional[T], List[T], and plain types.

    :param dc_instance: dataclass instance to validate

    :raises ValueError: if a field value has the wrong type
    """
    hints = get_type_hints(dc_instance.__class__)
    for f in dc_fields(dc_instance):
        value = getattr(dc_instance, f.name)
        expected = hints[f.name]

        # Extract inner type from Optional[T]
        origin = getattr(expected, '__origin__', None)
        args = getattr(expected, '__args__', ())

        is_optional = (
            origin is type(None)  # noqa: E721
            or (origin is not None
                and type(None) in args)
        )

        if is_optional and value is None:
            continue

        # Unwrap Optional to get the inner type
        if is_optional and args:
            inner_types = [
                a for a in args if a is not type(None)
            ]
            if len(inner_types) == 1:
                expected = inner_types[0]
                origin = getattr(
                    expected, '__origin__', None
                )
                args = getattr(expected, '__args__', ())

        # Check List[T]
        if origin is list:
            if not isinstance(value, list):
                raise ValueError(
                    f"{f.name} must be a list, "
                    f"got {type(value).__name__}"
                )
        # Check plain types (str, int, float, bool, Enum)
        elif origin is None:
            if isinstance(expected, type):
                # bool is subclass of int, check bool first
                if expected is bool:
                    if not isinstance(value, bool):
                        raise ValueError(
                            f"{f.name} must be a bool, "
                            f"got {type(value).__name__}"
                        )
                elif expected is int:
                    if isinstance(value, bool) \
                            or not isinstance(value, int):
                        raise ValueError(
                            f"{f.name} must be an int, "
                            f"got {type(value).__name__}"
                        )
                elif not isinstance(value, expected):
                    raise ValueError(
                        f"{f.name} must be a "
                        f"{expected.__name__}, "
                        f"got {type(value).__name__}"
                    )
