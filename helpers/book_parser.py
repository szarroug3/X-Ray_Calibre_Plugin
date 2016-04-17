# book_parser.py

import os
import re
from sys import exit
from struct import unpack

from calibre.ebooks.mobi.huffcdic import HuffReader
from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.compression.palmdoc import decompress_doc

class BookParser(object):
    PARAGRAPH_PAT = re.compile(r'<p.*?>.+?(?:<\/p>)', re.I)
    PLAIN_TEXT_PAT = re.compile(r'>([^<]+?)<', re.I)

    def __init__(self, book_path, shelfari_data):
        self._book_path = book_path
        self._excerpt_data = {}
        self._entity_data = {}

        for char in shelfari_data.characters.items():
            label = char[1]['label']
            desc = char[1]['description'] if char[1]['description'] else ''
            self._entity_data[label] = {'entity_id': char[0], 'description': desc, 'type': 1, 'mentions': 0, 'excerpt_ids': [], 'occurrence': []}

        for term in shelfari_data.terms.items():
            label = term[1]['label']
            desc = term[1]['description'] if term[1]['description'] else ''
            self._entity_data[label] = {'entity_id': term[0], 'description': desc, 'type': 2, 'mentions': 0, 'excerpt_ids': [], 'occurrence': []}

    @property
    def erl(self):
        return self._erl
    
    @property
    def excerpt_data(self):
        return self._excerpt_data

    @property
    def entity_data(self):
        return self._entity_data

    @property
    def codec(self):
        return self._codec   

    def parse(self):
        self._book_html = MobiExtractor(self._book_path, open(os.devnull, 'w')).extract_text()
        self.find_erl_and_encoding()
        paragraph_data = []

        # find all paragraphs (sections enclosed in html p tags) and their starting offset
        for node in re.finditer(self.PARAGRAPH_PAT, self._book_html):
            # get plain text from paragraph and locations of letters from beginning of file
            results = [(word.group(0)[1:-1].decode(self._codec), word.start(0)) for word in re.finditer(self.PLAIN_TEXT_PAT, node.group(0))]
            word_loc = {'words': '', 'loc': []}
            for group, loc in results:
                start = node.start(0) + loc + 1
                for char in group:
                    word_loc['words'] = word_loc['words'] + char
                    word_loc['loc'].append(start)
                    start += 1
            paragraph_data.append((word_loc, node.start(0) + 1))

        # get db data
        for excerpt_id, data in enumerate(paragraph_data):
            word_loc = data[0]
            para_start = data[1]
            self._excerpt_data[excerpt_id] = {'loc': para_start, 'len': len(word_loc['words']), 'related_entities': []}
            for word in self.entity_data.keys():
                WORD_PAT = re.compile(r'\b{}\b'.format(word), re.I)
                for match in re.finditer(WORD_PAT, word_loc['words']):
                    entity_id = self._entity_data[word]['entity_id']
                    self._entity_data[word]['mentions'] += 1
                    self._entity_data[word]['excerpt_ids'].append(excerpt_id)
                    self._entity_data[word]['occurrence'].append({'loc': word_loc['loc'][match.start(0)],
                                'len': self._find_len(match.start(0), word_loc['words'])})
                    if entity_id not in self._excerpt_data[excerpt_id]['related_entities']:
                        self._excerpt_data[excerpt_id]['related_entities'].append(entity_id)

    def _find_len(self, start, string):
        previous_space = string[:start].rfind(' ', )
        next_space = string.find(' ', start)
        if previous_space != -1 and next_space != -1:
            next_space -= 1
        if previous_space == -1:
            previous_space = 0
        if next_space == -1:
            next_space = len(string) - 1
        return (next_space - previous_space)

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