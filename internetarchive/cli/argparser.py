# -*- coding: utf-8 -*-
"""
internetarchive.cli.argparser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2015 Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from collections import defaultdict
from xml.dom.minidom import parseString
import re


def get_xml_text(xml_str, tag_name=None, text=None):
    tag_name = 'Message' if not tag_name else tag_name
    text = '' if not text else text
    p = parseString(xml_str)
    elements = p.getElementsByTagName(tag_name)
    for e in elements:
        for node in e.childNodes:
            if node.nodeType == node.TEXT_NODE:
                text += node.data
    return text


def get_args_dict(strings):
    args = defaultdict(list)
    for s in strings:
        for (key, value) in \
                [[x.strip() for x in re.split(r'[:=]', p, 1)]
                    for p in re.split('[,;&]', s)]:
            assert value
            if value not in args[key]:
                args[key].append(value)
    for key in args:
        # Flatten single item lists.
        if len(args[key]) <= 1:
            args[key] = args[key][0]
    return args
