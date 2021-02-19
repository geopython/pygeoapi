# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2021 Tom Kralidis
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

from datetime import datetime
from glob import glob
import os
import sys

from lxml import etree
from owslib.iso import MD_Metadata
from tinydb import TinyDB


if len(sys.argv) < 3:
    print('Usage: {} <path/to/xml-files> <output.db>'.format(sys.argv[0]))
    sys.exit(1)

xml_dir = sys.argv[1]
index_name = sys.argv[2]

if os.path.exists(index_name):
    os.remove(index_name)

db = TinyDB(index_name)


def get_anytext(bag):
    """
    generate bag of text for free text searches
    accepts list of words, string of XML, or etree.Element
    """

    namespaces = {
        'gco': 'http://www.isotc211.org/2005/gco'
    }

    if isinstance(bag, list):  # list of words
        return ' '.join([_f for _f in bag if _f]).strip()
    else:  # xml
        text_bag = []

        if isinstance(bag, (bytes, str)):
            # serialize to lxml
            bag = etree.fromstring(bag)

        for t in bag.xpath('//gco:CharacterString', namespaces=namespaces):
            if t.text is not None:
                text_bag.append(t.text.strip())

    return ' '.join(text_bag)


for xml_file in glob('{}/*.xml'.format(xml_dir)):
    m = MD_Metadata(etree.parse(xml_file))

    _raw_metadata = m.xml.decode('utf-8')
    _anytext = get_anytext(_raw_metadata)

    identifier = m.identifier
    type_ = m.hierarchy
    title = m.identification.title
    description = m.identification.abstract

    contact = m.identification.contact
    issued = m.datestamp

    links = []
    if m.distribution and m.distribution.online:
        for ln in m.distribution.online:
            lnk = {
                'href': ln.url,
                'rel': 'item'
            }
            if hasattr(ln, 'name') and ln.name is not None:
                lnk['title'] = ln.name
            if hasattr(ln, 'protocol') and ln.protocol is not None:
                lnk['type'] = ln.protocol
            links.append(lnk)

    themes = []
    for keyword_set in m.identification.keywords2:
        theme = {}
        theme['concepts'] = keyword_set.keywords
        try:
            theme['scheme'] = keyword_set.thesaurus['url']
        except (AttributeError, KeyError, TypeError):
            pass
        themes.append(theme)

    contact = ''
    for c in m.contact:
        contact = getattr(c, 'email', None)
        if not contact:
            continue
        if hasattr(c, 'name') and c.name is not None:
            contact = '{}, {}'.format(c.name, contact)
        if hasattr(c, 'organization') and c.organization is not None:
            contact = '{}, {}'.format(contact, c.organization)
        break

    bbox_crs = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'

    minx = float(m.identification.bbox.minx)
    miny = float(m.identification.bbox.miny)
    maxx = float(m.identification.bbox.maxx)
    maxy = float(m.identification.bbox.maxy)

    bbox = [minx, miny, maxx, maxy]

    te_begin = m.identification.temporalextent_start
    if te_begin == 'missing':
        te_begin = None
    te_end = m.identification.temporalextent_end

    json_record = {
        'id': identifier,
        'type': 'Feature',
        'geometry': {
            'type': 'Polygon',
            'coordinates': [[
                [minx, miny],
                [minx, maxy],
                [maxx, maxy],
                [maxx, miny],
                [minx, miny]
            ]]
        },
        'properties': {
            'record-created': issued,
            'record-updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'type': type_,
            'title': title,
            'description': description,
            'contactPoint': contact,
            'associations': links,
            'externalId': identifier,
            'themes': themes,
            'extent': {
                'spatial': {
                    'bbox': [[bbox]],
                    'crs': bbox_crs
                },
                'temporal': {
                    'interval': [te_begin, te_end],
                    'trs': 'http://www.opengis.net/def/uom/ISO-8601/0/Gregorian'  # noqa
                }
            },
            '_metadata-anytext': _anytext
        }
    }

    try:
        res = db.insert(json_record)
        print('Metadata record {} loader with internal id {}'.format(
            xml_file, res))
    except Exception as err:
        print(err)
