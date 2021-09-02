# =================================================================
#
# Authors: Benjamin Webb <benjamin.miller.webb@gmail.com>
#
# Copyright (c) 2021 Benjamin Webb
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

import os
import logging
import hashlib
import jsonschema
import yaml

from flask import Blueprint, request, url_for, redirect
import flask_login

from pygeoapi.util import yaml_load, render_j2_template
from pygeoapi.config import validate_config


LOGGER = logging.getLogger(__name__)

TEMPLATE_CONFIG, CONFIG = None, None
login_manager = flask_login.LoginManager()
users = {}

if 'PYGEOAPI_CONFIG' not in os.environ:
    raise RuntimeError('PYGEOAPI_CONFIG environment variable not set')

with open('template.config.yml', encoding='utf8') as fh:
    TEMPLATE_CONFIG = yaml_load(fh)

with open(os.environ.get('PYGEOAPI_CONFIG'), encoding='utf8') as fh:
    CONFIG = yaml_load(fh)


class Admin(flask_login.UserMixin):
    pass


ADMIN_BLUEPRINT = Blueprint('pygeoapi_admin', __name__,
                            template_folder="templates",
                            static_folder="/static",
                            )


@ADMIN_BLUEPRINT.record_once
def on_load(state):
    login_manager.init_app(state.app)
    state.app.secret_key = os.urandom(24)
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        os.environ.pop('ADMIN_PASS').encode('utf-8'),
        salt,
        100000
    )
    users[os.getenv('ADMIN_USER')] = {'password': key, 'salt': salt}


@ADMIN_BLUEPRINT.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_j2_template(CONFIG, 'admin/login.html', {})

    admin = request.form[os.getenv('ADMIN_USER')]
    login_key = hashlib.pbkdf2_hmac(
        'sha256',
        request.form['password'].encode('utf-8'),
        users[os.getenv('ADMIN_USER')]['salt'],
        100000
    )
    if login_key == users[os.getenv('ADMIN_USER')]['password']:
        user = Admin()
        user.id = admin
        flask_login.login_user(user)
        return redirect(url_for('pygeoapi_admin.admin'))

    return redirect(url_for('pygeoapi_admin.login'))


@ADMIN_BLUEPRINT.route('/admin')
@flask_login.login_required
def admin():
    return render_j2_template(CONFIG, 'admin/index.html', TEMPLATE_CONFIG)


@ADMIN_BLUEPRINT.route('/logout')
def logout():
    flask_login.logout_user()
    return redirect(url_for('pygeoapi.landing_page'))


@ADMIN_BLUEPRINT.route('/admin/config', methods=['POST'])
@flask_login.login_required
def config():
    with open("temp.config.yml", "w") as file:
        yaml.safe_dump(request.get_json(force=True), file,
                       sort_keys=False, indent=4, default_flow_style=False)

    with open('temp.config.yml', encoding='utf8') as fh:
        temp_config = yaml_load(fh)
        try:
            validate_config(temp_config)
            with open(os.environ.get('PYGEOAPI_CONFIG'), "w") as file:
                yaml.safe_dump(temp_config, file, sort_keys=False, indent=4,
                               default_flow_style=False)
            return 'Configuration file valid and applied to server'
        except jsonschema.exceptions.ValidationError as err:
            return {'msg': err.message, 'path': '.'.join(err.path)}, 422


@login_manager.user_loader
def user_loader(email):
    if email not in users:
        return

    user = Admin()
    user.id = email
    return user


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('pygeoapi_admin.login'))
