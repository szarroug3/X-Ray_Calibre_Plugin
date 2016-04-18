# book_parser.py

import os
import re
from random import randrange
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
        self._quotes = shelfari_data.quotes
        self._notable_clips = []

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
    def notable_clips(self):
        return self._notable_clips
    

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
            results = [(word.group(0)[1:-1].decode(self.codec), word.start(0)) for word in re.finditer(self.PLAIN_TEXT_PAT, node.group(0))]
            word_loc = {'words': '', 'locs': [], 'char_sizes': []}
            for group, loc in results:
                start = node.start(0) + loc + 1
                for char in group:
                    word_loc['words'] += char
                    word_loc['locs'].append(start)
                    start += len(char.encode(self.codec))
                    word_loc['char_sizes'].append(len(char.encode(self.codec)))
            if len(word_loc['locs']) > 0:
                paragraph_data.append((word_loc, word_loc['locs'][0]))

        # get db data
        excerpt_id = 0
        for word_loc, para_start in paragraph_data:
            rel_ent = []
            add_excerpt = False
            for word in self.entity_data.keys():
                # search for word in the paragraph
                WORD_PAT = re.compile(r'\b{}\b'.format(word), re.I)
                # for each match found, fill in entity_data and excerpt_data information
                for match in re.finditer(WORD_PAT, word_loc['words']):
                    entity_id = self._entity_data[word]['entity_id']
                    self._entity_data[word]['mentions'] += 1
                    self._entity_data[word]['excerpt_ids'].append(excerpt_id)
                    self._entity_data[word]['occurrence'].append({'loc': word_loc['locs'][self._find_start(match.start(0), word_loc['words'])],
                                'len': self._find_len_word(match.start(0), match.end(0), word_loc)})
                    if entity_id not in rel_ent:
                        rel_ent.append(entity_id)
                        add_excerpt = True
                for quote in self._quotes:
                    if quote.lower() in word_loc['words'].lower() and excerpt_id not in self._notable_clips:
                        self._notable_clips.append(excerpt_id)
                        add_excerpt = True
            if add_excerpt:
                self._excerpt_data[excerpt_id] = {'loc': para_start, 'len': self._find_len_excerpt(word_loc), 'related_entities': rel_ent}
                excerpt_id += 1

        # add random excerpts to make sure notable clips has at least 20 excerpts
        while len(self._notable_clips) < 20:
            rand_excerpt = randrange(0, excerpt_id - 1)
            if rand_excerpt not in self._notable_clips:
                self._notable_clips.append(rand_excerpt)

    def _find_start(self, start, string):
        previous_space = string[:start].rfind(' ')
        if previous_space == -1:
            previous_space = 0
        else:
            previous_space += 1
        return previous_space

    def _find_len_word(self, start, end, word_loc):
        string = word_loc['words']
        char_sizes = word_loc['char_sizes']

        first_char = string[:start].rfind(' ')
        last_char = string.find(' ', end)

        if first_char == -1:
            first_char = 0
        else:
            first_char += 1
        if last_char == -1:
            last_char = len(string) - 1
        else:
            last_char -= 1

        total_len = 0
        for char in range(first_char, last_char + 1):
            total_len += char_sizes[char]

        return total_len

    def _find_len_excerpt(self, word_loc):
        string = word_loc['words']
        char_sizes = word_loc['char_sizes']

        total_len = 0
        for char in range(0, len(string) ):
            total_len += char_sizes[char]

        return total_len

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