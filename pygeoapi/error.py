# =================================================================
#
# Authors: Bernhard Mallinger <bernhard.mallinger@eox.at>
#
# Copyright (c) 2024 Bernhard Mallinger
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


from http import HTTPStatus


class GenericError(Exception):
    """Exception class where error codes and messages
    can be defined in custom error subclasses, so custom
    providers and processes can raise appropriate errors.
    """

    ogc_exception_code = 'NoApplicableCode'
    http_status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    default_msg = 'Unknown error'

    def __init__(self, msg=None, *args, user_msg=None) -> None:
        # if only a user_msg is provided, use it as msg
        if user_msg and not msg:
            msg = user_msg
        super().__init__(msg, *args)
        self.user_msg = user_msg

    @property
    def message(self):
        return self.user_msg if self.user_msg else self.default_msg
