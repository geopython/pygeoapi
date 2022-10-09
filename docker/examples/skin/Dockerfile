# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#          Just van den Broecke <justb4@gmail.com>
#          Francesco Bartoli <xbartolone@gmail.com>
#          Angelos Tzotsos <gcpp.kalxas@gmail.com>
#          Paul van Genuchten <genuchten@yahoo.com>
#
# Copyright (c) 2020 Tom Kralidis
# Copyright (c) 2019 Just van den Broecke
# Copyright (c) 2020 Francesco Bartoli
# Copyright (c) 2021 Angelos Tzotsos
# Copyright (c) 2022 Paul van Genuchten
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

FROM geopython/pygeoapi:latest

LABEL maintainer="Paul van Genuchten <genuchten@yahoo.com>"

RUN apt update && apt install -y --no-install-recommends wget unzip

# a skin example
RUN wget "https://github.com/pvgenuchten/pygeoapi-skin-dashboard/archive/refs/heads/main.zip"
RUN unzip main.zip -d /pygeoapi
RUN rm main.zip

COPY ./skin.config.yml /pygeoapi/local.config.yml

WORKDIR /pygeoapi
ENTRYPOINT ["/entrypoint.sh"]
