# =================================================================
#
# Authors: Ricardo Garcia Silva <ricardo.garcia.silva@gmail.com>
#
# Copyright (c) 2023 Ricardo Garcia Silva
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
from typing import Optional

import pydantic


class Link(pydantic.BaseModel):
    href: str
    type_: Optional[str] = pydantic.Field(None, alias="type")
    rel: Optional[str] = None
    title: Optional[str] = None
    href_lang: Optional[str] = pydantic.Field(None, alias="hreflang")

    def as_link_header(self) -> str:
        result = f'<{self.href}>'
        fields = (
            'rel',
            'title',
            'type_',
            'href_lang',
        )
        for field_name in fields:
            value = getattr(self, field_name, None)
            if value is not None:
                fragment = f'{self.__fields__[field_name].alias}="{value}"'
                result = '; '.join((result, fragment))
        return result