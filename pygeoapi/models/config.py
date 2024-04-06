# ****************************** -*-
# flake8: noqa
# =================================================================
#
# Authors: Sander Schaminee <sander.schaminee@geocat.net>
#          Francesco Bartoli <xbartolone@gmail.com>
#
# Copyright (c) 2023 Sander Schaminee
# Copyright (c) 2024 Francesco Bartoli
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

from pydantic import BaseModel, Field


class APIRules(BaseModel):
    """ Pydantic model for API design rules that must be adhered to. """
    api_version: str = Field(regex=r'^\d+\.\d+\..+$',
                             description="Semantic API version number.")
    url_prefix: str = Field(
        "",
        description="If set, pygeoapi routes will be prepended with the "
                    "given URL path prefix (e.g. '/v1'). "
                    "Defaults to an empty string (no prefix)."
    )
    version_header: str = Field(
        "",
        description="If set, pygeoapi will set a response header with this "
                    "name and its value will hold the API version. "
                    "Defaults to an empty string (i.e. no header). "
                    "Often 'API-Version' or 'X-API-Version' are used here."
    )
    strict_slashes: bool = Field(
        False,
        description="If False (default), URL trailing slashes are allowed. "
                    "If True, pygeoapi will return a 404."
    )

    @staticmethod
    def create(**rules_config) -> 'APIRules':
        """ Returns a new APIRules instance for the current API version
        and configured rules. """
        obj = {
            k: v for k, v in rules_config.items() if k in APIRules.__fields__
        }
        # Validation will fail if required `api_version` is missing
        # or if `api_version` is not a semantic version number
        return APIRules.parse_obj(obj)

    @property
    def response_headers(self) -> dict:
        """ Gets a dictionary of additional response headers for the current
        API rules. Returns an empty dict if no rules apply. """
        headers = {}
        if self.version_header:
            headers[self.version_header] = self.api_version
        return headers

    def get_url_prefix(self, style: str = None) -> str:
        """
        Returns an API URL prefix to use in all paths.
        May include a (partial) API version. See docs for syntax.
        :param style: Set to 'django', 'flask' or 'starlette' to return a
                      specific prefix formatted for those frameworks.
                      If not set, only the prefix itself will be returned.
        """
        if not self.url_prefix:
            return ""
        major, minor, build = self.api_version.split('.')
        prefix = self.url_prefix.format(
            api_version=self.api_version,
            api_major=major,
            api_minor=minor,
            api_build=build
        ).strip('/')
        style = (style or '').lower()
        if style == 'django':
            # Django requires the slash at the end
            return rf"^{prefix}/"
        elif style in ('flask', 'starlette'):
            # Flask and Starlette need the slash in front
            return f"/{prefix}"
        # If no format is specified, return only the bare prefix
        return prefix
