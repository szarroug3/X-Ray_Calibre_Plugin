# book_parser.py

import os
import re
from sys import exit
from struct import unpack

from calibre.ebooks.mobi.huffcdic import HuffReader
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.compression.palmdoc import decompress_doc

class BookParser(object):
    PARAGRAPH_PAT = re.compile(r'<p.*?>.+?(?:<\/p>)')
    def __init__(self, book_path, shelfari_data):
        self._book_path = book_path
        self._excerpt_data = {}
        self._entity_data = {}
        self._entity_id = {}

        for char in shelfari_data.characters.items():
            label = char[1]['label'].lower()
            desc = char[1]['description'].lower() if char[1]['description'] else None
            self._entity_data[char[0]] = {'label': label, 'description': desc, 'type': 1, 'mentions': 0, 'excerpt_ids': [], 'occurrence': []}
            self._entity_id[label] = char[0]

        for term in shelfari_data.terms.items():
            label = term[1]['label'].lower()
            desc = term[1]['description'].lower() if term[1]['description'] else None
            self._entity_data[term[0]] = {'label': label, 'description': desc, 'type': 1, 'mentions': 0, 'excerpt_ids': [], 'occurrence': []}
            self._entity_id[label] = term[0]

    @property
    def erl(self):
        return self._erl
    
    @property
    def excerpt_data(self):
        return self._excerpt_data

    @property
    def entity_data(self):
        return self._entity_data
    

    def parse(self):
        self._book_html = MobiExtractor(self._book_path, open(os.devnull, 'w')).extract_text()

        self.find_erl_and_encoding()
        self._paragraph_data = []

        # find all paragraphs (sections enclosed in html p tags) and their starting offset
        for node in re.finditer(self.PARAGRAPH_PAT, self._book_html):
            # get plain text from paragraph and locations of letters from beginning of file
            results = [(word.group(0)[1:-1].decode(self._codec).lower(), word.start(0)) for word in re.finditer(r'>([^<]+?)<', node, re.I)]
            word_loc = {'words': '', 'loc': []}
            for group, loc in results:
                start = node.start(0) + loc + 1
                for char in group:
                    word_loc['words'] = word_loc['words'] + char
                    word_loc['loc'].append(start)
                    start += 1
            self._paragraph_data.append(word_loc, node.start(0) + 1)
        self._get_data()


    def _get_data(self):
        with open('text.txt', 'w+') as f:
            for excerpt_id, word_loc, para_start in enumerate(self._paragraph_data):
                self._excerpt_data[excerpt_id: {'loc': para_start, 'len': len(word_loc), 'related_entities': []}]
                for word in re.finditer(r'([a-z]+)', word_loc['words'], re.I):
                        if word.group(0) in self._entity_id.keys():
                            self._entity_data[self._entity_id[word.group(0)]]['mentions'] += 1
                            self._entity_data[self._entity_id[word.group(0)]]['excerpt_ids'].append(excerpt_id)
                            self._entity_data[self._entity_id[word.group(0)]]['occurrence'].append({'loc': word_loc[word.start(0)],
                                        'len': self._find_len(word.start(0), word.group(0))})
                            self._excerpt_data[excerpt_id]['related_entities'].append(self._entity_id[word.group(0)])

    def _find_len(self, start, string):
    next_space = string.find(' ', start)
    if next_space != 0
    return next_space - start

    # if there is no space between start and the end of the string, return length from start to end of string
    return len(string) - start

    # do i really need to do this??
    def search_for_quotes(self):
        pass

    def find_erl_and_encoding(self):
        with open(self._book_path, 'rb') as f:
            book_data = f.read()

        nrecs, = unpack('>H', book_data[76:78])
        recs_start = 78 + (nrecs * 8) + 2
        self._erl, = unpack('>L', book_data[recs_start + 4:recs_start + 8])
        self._codec = 'latin-1' if unpack('>L', book_data[recs_start + 28:recs_start + 32])[0] == 1252 else 'utf8'

class MobiExtractor(MobiReader):
    def extract_text(self, offset=1):
        text_sections = [self.text_section(i) for i in range(offset, min(self.book_header.records + offset, len(self.sections)))]
        processed_records = list(range(offset-1, self.book_header.records +
            offset))

        self.mobi_html = b''

        if self.book_header.compression_type == 'DH':
            huffs = [self.sections[i][0] for i in range(self.book_header.huff_offset, self.book_header.huff_offset + self.book_header.huff_number)]
            processed_records += list(range(self.book_header.huff_offset, self.book_header.huff_offset + self.book_header.huff_number))
            huff = HuffReader(huffs)
            unpack = huff.unpack

        elif self.book_header.compression_type == '\x00\x02':
            unpack = decompress_doc

        elif self.book_header.compression_type == '\x00\x01':
            unpack = lambda x: x
        else:
            raise MobiError('Unknown compression algorithm: %s' % repr(self.book_header.compression_type))
        self.mobi_html = b''.join(map(unpack, text_sections))
        if self.mobi_html.endswith(b'#'):
            self.mobi_html = self.mobi_html[:-1]

        if self.book_header.ancient and '<html' not in self.mobi_html[:300].lower():
            self.mobi_html = self.mobi_html.replace('\r ', '\n\n ')
        self.mobi_html = self.mobi_html.replace('\0', '')
        if self.book_header.codec == 'cp1252':
            self.mobi_html = self.mobi_html.replace('\x1e', '')  # record separator
            self.mobi_html = self.mobi_html.replace('\x02', '')  # start of text
        return self.mobi_html