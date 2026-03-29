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

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class SupportedFormats(Enum):
    JSON = 'json'
    YAML = 'yaml'


@dataclass
class OAPIFormat:
    """
    OpenAPI output format.

    Concrete dataclass implementation that can be mimicked
    downstream.

    :param root: output format, defaults to ``yaml``
    """

    root: SupportedFormats = SupportedFormats.YAML

    def __post_init__(self):
        if isinstance(self.root, SupportedFormats):
            return
        if isinstance(self.root, str):
            try:
                self.root = SupportedFormats(self.root)
            except ValueError:
                raise ValueError(
                    f"Unsupported format: '{self.root}'. "
                    f"Must be one of: "
                    f"{[f.value for f in SupportedFormats]}"
                )
        else:
            raise ValueError(
                f"root must be a string or SupportedFormats, "
                f"got {type(self.root).__name__}"
            )

    def __eq__(self, other):
        if isinstance(other, str):
            return self.root.value == other
        if isinstance(other, SupportedFormats):
            return self.root == other
        if isinstance(other, OAPIFormat):
            return self.root == other.root
        return NotImplemented

    def model_dump(
        self, exclude_none: bool = False
    ) -> Dict[str, Any]:
        """Serialize to dict."""
        return {'root': self.root.value}
