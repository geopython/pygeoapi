# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
# Authors: Benjamin Webb <benjamin.miller.webb@gmail.com>
#
# Copyright (c) 2023 Tom Kralidis
# Copyright (c) 2023 Benjamin Webb
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

import time

from pathlib import Path
import unittest

from requests import Session

THISDIR = Path(__file__).resolve().parent


class APITest(unittest.TestCase):
    def setUp(self):
        """setup test fixtures, etc."""

        self.admin_endpoint = 'http://localhost:5000/admin/config'
        self.http = Session()
        self.http.headers.update({
            'Content-type': 'application/json',
            'Accept': 'application/json'
        })

    def tearDown(self):
        """return to pristine state"""

        pass

    def test_admin(self):

        url = f'{self.admin_endpoint}'
        content = self.http.get(url).json()

        keys = ['logging', 'metadata', 'resources', 'server']
        self.assertEqual(sorted(content.keys()), keys)

        # PUT configuration
        with get_abspath('admin-put.json').open() as fh:
            put = fh.read()
        response = self.http.put(url, data=put)
        self.assertEqual(response.status_code, 204)

        # NOTE: we sleep 5 between CRUD requests so as to let gunicorn
        # restart with the refreshed configuration
        time.sleep(5)

        content = self.http.get(url).json()
        self.assertEqual(content['logging']['level'], 'INFO')

        # PATCH configuration
        with get_abspath('admin-patch.json').open() as fh:
            patch = fh.read()

        response = self.http.patch(url, data=patch)
        self.assertEqual(response.status_code, 204)

        time.sleep(5)

        content = self.http.get(url).json()
        self.assertEqual(content['logging']['level'], 'DEBUG')

    def test_resources_crud(self):

        url = f'{self.admin_endpoint}/resources'
        content = self.http.get(url).json()
        self.assertEqual(len(content.keys()), 1)

        # POST a new resource
        with get_abspath('resource-post.json').open() as fh:
            post_data = fh.read()

        response = self.http.post(url, data=post_data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.text,
                         'Location: /admin/config/resources/data2')

        # NOTE: we sleep 5 between CRUD requests so as to let gunicorn
        # restart with the refreshed configuration
        time.sleep(5)

        content = self.http.get(url).json()
        self.assertEqual(len(content.keys()), 2)

        # PUT an existing resource
        url = f'{self.admin_endpoint}/resources/data2'
        with get_abspath('resource-put.json').open() as fh:
            post_data = fh.read()
        print(url)
        print(get_abspath('resource-put.json'))
        response = self.http.put(url, data=post_data)
        self.assertEqual(response.status_code, 204)

        time.sleep(5)

        content = self.http.get(url).json()
        self.assertEqual(content['title']['en'],
                         'Data assets, updated by HTTP PUT')

        # PATCH an existing resource
        url = f'{self.admin_endpoint}/resources/data2'
        with get_abspath('resource-patch.json').open() as fh:
            post_data = fh.read()

        response = self.http.patch(url, data=post_data)
        self.assertEqual(response.status_code, 204)

        time.sleep(5)

        content = self.http.get(url).json()
        self.assertEqual(content['title']['en'],
                         'Data assets, updated by HTTP PATCH')

        # DELETE an existing new resource
        response = self.http.delete(url)
        self.assertEqual(response.status_code, 204)

        time.sleep(5)

        url = f'{self.admin_endpoint}/resources'
        content = self.http.get(url).json()
        self.assertEqual(len(content.keys()), 1)


def get_abspath(filepath):
    """helper function absolute file access"""

    return Path(THISDIR) / 'data' / 'admin' / filepath


if __name__ == '__main__':
    unittest.main()
