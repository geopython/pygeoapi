# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2023 Tom Kralidis
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
from pathlib import Path
import sys
from typing import Union

from lxml import etree
from owslib.iso import CI_ResponsibleParty, MD_Metadata
from tinydb import TinyDB


if len(sys.argv) < 3:
    print(f'Usage: {sys.argv[0]} <path/to/xml-files> <output.db>')
    sys.exit(1)

xml_dir = Path(sys.argv[1])
index_name = Path(sys.argv[2])

if index_name.exists():
    index_name.unlink()

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
                'office': {}
            }
        }
    }

    party['name'] = ci.name or ci.position

    if ci.phone:
        party['contactInfo']['phone'] = {
            'office': ci.phone
        }
    if ci.email:
        party['contactInfo']['email'] = {
            'office': ci.email
        }
    if ci.address:
        party['contactInfo']['address']['office']['deliveryPoint'] = ci.address
    if ci.city:
        party['contactInfo']['address']['office']['city'] = ci.city
    if ci.region:
        party['contactInfo']['address']['office']['administrativeArea'] = ci.region  # noqa
    if ci.postcode:
        party['contactInfo']['address']['office']['postalCode'] = ci.postcode
    if ci.country:
        party['contactInfo']['address']['office']['country'] = ci.country
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


for xml_file in xml_dir.glob('*.xml'):
    print(xml_file)
    m = MD_Metadata(etree.parse(str(xml_file)))

    _raw_metadata = m.xml.decode('utf-8')
    _anytext = get_anytext(_raw_metadata)

    identifier = m.identifier
    type_ = m.hierarchy
    title = m.identification[0].title
    description = m.identification[0].abstract

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
    for keyword_set in m.identification[0].keywords:
        theme = {
            'concepts': []
        }

        for kw in keyword_set.keywords:
            theme['concepts'].append({
                'id': kw.name
            })

        try:
            theme['scheme'] = keyword_set.thesaurus['url']
        except (AttributeError, KeyError, TypeError):
            pass

        themes.append(theme)

    providers = []
    contacts = (m.contact + m.identification[0].creator +
                m.identification[0].publisher +
                m.identification[0].contributor)

    if m.distribution:
        contacts.extend(m.distribution.distributor)

    if contacts:
        for contact in contacts:
            if isinstance(contact, CI_ResponsibleParty):
                providers.append(contact2party(contact))

    bbox_crs = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'

    minx = float(m.identification[0].bbox.minx)
    miny = float(m.identification[0].bbox.miny)
    maxx = float(m.identification[0].bbox.maxx)
    maxy = float(m.identification[0].bbox.maxy)

    bbox = [minx, miny, maxx, maxy]

    te_begin = m.identification[0].temporalextent_start
    if te_begin == 'missing':
        te_begin = None
    te_end = m.identification[0].temporalextent_end

    json_record = {
        'id': identifier,
        'conformsTo': [
            'http://www.opengis.net/spec/ogcapi-records-1/1.0/req/record-core'
        ],
        'type': 'Feature',
        'time': [te_begin, te_end],
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
            'created': issued,
            'updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'type': type_,
            'title': title,
            'description': description,
            'providers': providers,
            'externalIds': [{
                'scheme': 'default',
                'value': identifier
            }],
            'themes': themes,
            '_metadata-anytext': _anytext
        },
        'links': links
    }

    try:
        res = db.insert(json_record)
        print(f'Metadata record {xml_file} loaded with internal id {res}')
    except Exception as err:
        print(err)
