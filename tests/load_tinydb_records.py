# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 Tom Kralidis
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
from typing import Union

from lxml import etree
from owslib.iso import CI_ResponsibleParty, MD_Metadata
from tinydb import TinyDB


if len(sys.argv) < 3:
    print('Usage: {} <path/to/xml-files> <output.db>'.format(sys.argv[0]))
    sys.exit(1)

xml_dir = sys.argv[1]
index_name = sys.argv[2]

if os.path.exists(index_name):
    os.remove(index_name)

db = TinyDB(index_name)


def contact2party(ci: CI_ResponsibleParty) -> dict:
    """
    Generates an OARec party object from an
    OWSLib ISO CI_ResponsibleParty object

    :param ci: OWSLib `CI_ResponsibleParty` object

    :returns: `dict` of OARec party object
    """

    party = {
        'contactInfo': {
            'address': {
                'main': {}
            }
        }
    }

    party['name'] = ci.name or ci.position
    if ci.phone:
        party['contactInfo']['phone'] = ci.phone
    if ci.email:
        party['contactInfo']['email'] = ci.email
    if ci.address:
        party['contactInfo']['address']['main']['deliveryPoint'] = ci.address
    if ci.city:
        party['contactInfo']['address']['main']['city'] = ci.city
    if ci.region:
        party['contactInfo']['address']['main']['administrativeArea'] = ci.region  # noqa
    if ci.postcode:
        party['contactInfo']['address']['main']['postalCode'] = ci.postcode
    if ci.country:
        party['contactInfo']['address']['main']['country'] = ci.country
    if ci.onlineresource:
        party['contactInfo']['url'] = {
            'href': ci.onlineresource.url,
            'rel': ci.onlineresource.protocol,
            'title': ci.onlineresource.name,
            'description': ci.onlineresource.description,
        }

    if ci.role:
        party['roles'] = [{'name': ci.role}]

    return party


def get_anytext(bag: Union[list, str]) -> str:
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
    title = m.identificationinfo[0].title
    description = m.identificationinfo[0].abstract

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
    for keyword_set in m.identificationinfo[0].keywords2:
        theme = {}
        theme['concepts'] = keyword_set.keywords
        try:
            theme['scheme'] = keyword_set.thesaurus['url']
        except (AttributeError, KeyError, TypeError):
            pass
        themes.append(theme)

    providers = []
    contacts = (m.contact + m.identificationinfo[0].creator +
                m.identificationinfo[0].publisher +
                m.identificationinfo[0].contributor)

    if m.distribution:
        contacts.extend(m.distribution.distributor)

    if contacts:
        for contact in contacts:
            providers.append(contact2party(contact))

    bbox_crs = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'

    minx = float(m.identificationinfo[0].bbox.minx)
    miny = float(m.identificationinfo[0].bbox.miny)
    maxx = float(m.identificationinfo[0].bbox.maxx)
    maxy = float(m.identificationinfo[0].bbox.maxy)

    bbox = [minx, miny, maxx, maxy]

    te_begin = m.identificationinfo[0].temporalextent_start
    if te_begin == 'missing':
        te_begin = None
    te_end = m.identificationinfo[0].temporalextent_end

    json_record = {
        'id': identifier,
        'conformsTo': [
            'http://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core'
        ],
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
            'recordCreated': issued,
            'recordUpdated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'type': type_,
            'title': title,
            'description': description,
            'providers': providers,
            'externalIds': [{
                'scheme': 'default',
                'value': identifier
            }],
            'themes': themes,
            'extent': {
                'spatial': {
                    'bbox': [bbox],
                    'crs': bbox_crs
                },
                'temporal': {
                    'interval': [te_begin, te_end],
                    'trs': 'http://www.opengis.net/def/uom/ISO-8601/0/Gregorian'  # noqa
                }
            },
            '_metadata-anytext': _anytext
        },
        'links': links
    }

    try:
        res = db.insert(json_record)
        print('Metadata record {} loaded with internal id {}'.format(
            xml_file, res))
    except Exception as err:
        print(err)
