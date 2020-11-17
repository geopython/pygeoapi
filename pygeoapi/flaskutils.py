# =================================================================
#
# Authors: Ricardo Garcia Silva <ricardo.garcia.silva@gmail.com>
#
# Copyright (c) 2020 Ricardo Garcia Silva
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

"""Custom flask utilities"""

import typing

from flask import Request
from werkzeug.datastructures import (
    ImmutableMultiDict,
    iteritems,
    iter_multi_items,
    iterlists,
    MultiDict,
)


class RequestQueryParamsImmutableMultiDict(ImmutableMultiDict):
    """An ImmutableMultiDict that converts its keys to lowercase

    This is useful when used to parse URL query parameters, which can usually
    be specified with whatever casing.

    Implementation is based on werkzeug's ImmutableMultiDict and it simply
    converts any incoming keys to lower case before calling the parent class'
    logic.

    """

    def __init__(self, mapping: typing.Optional[typing.Mapping] = None):
        if isinstance(mapping, MultiDict):
            dict.__init__(
                self,
                ((k.lower(), l[:]) for k, l in iterlists(mapping))
            )
        elif isinstance(mapping, dict):
            tmp = {}
            for key, value in iteritems(mapping):
                if isinstance(value, (tuple, list)):
                    if len(value) == 0:
                        continue
                    value = list(value)
                else:
                    value = [value]
                tmp[key.lower()] = value
            dict.__init__(self, tmp)
        else:
            tmp = {}
            for key, value in mapping or ():
                tmp.setdefault(key.lower(), []).append(value)
            dict.__init__(self, tmp)

    def __setitem__(self, key: str, value):
        return super().__setitem__(key.lower(), value)

    def add(self, key: str, value):
        return super().add(key.lower(), value)

    def setlist(self, key: str, new_list):
        return super().setlist(key.lower(), new_list)

    def setdefault(self, key: str, default: typing.Optional[typing.Any] = ...):
        return super().setdefault(key.lower(), default)

    def setlistdefault(
            self,
            key: str,
            default_list: typing.Optional[typing.Any] = ...
    ):
        return super().setlistdefault(key.lower(), default_list)

    def update(self, other_dict):
        for key, value in iter_multi_items(other_dict):
            MultiDict.add(self, key.lower(), value)


class PygeoapiFlaskRequest(Request):
    """A Flask Request subclass to be used by pygeoapi

    This allows customizing Flask's request object

    """

    parameter_storage_class = RequestQueryParamsImmutableMultiDict
