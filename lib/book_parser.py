# book_parser.py
'''Parses book using given information'''

import os
import re
from struct import unpack, error
from random import randrange

from calibre.ebooks.mobi import MobiError
from calibre.ebooks.mobi.huffcdic import HuffReader
from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.compression.palmdoc import decompress_doc

PARAGRAPH_PAT = re.compile(r'<p.*?>.+?(?:<\/p>)', re.I)
PLAIN_TEXT_PAT = re.compile(r'>([^<]+?)<', re.I)

class BookParser(object):
    '''Class to parse book using information from user and goodreads'''

    def __init__(self, book_type, book_path, goodreads_data, aliases):
        self._book_path = book_path
        self._entity_data = {}
        self._quotes = goodreads_data['quotes']
        self._aliases = {}
        self._parsed_data = None

        self._offset = 0
        if book_type.lower() == 'azw3':
            self._offset = -16

        for char, char_data in goodreads_data['characters'].items():
            original = char_data['label']
            label = original.lower()
            desc = char_data['description']
            self._entity_data[label] = {'original_label': original, 'entity_id': char, 'description': desc,
                                        'type': 1, 'mentions': 0, 'excerpt_ids': [], 'occurrence': []}

        for setting, setting_data in goodreads_data['settings'].items():
            original = setting_data['label']
            label = original.lower()
            desc = setting_data['description']
            self._entity_data[label] = {'original_label': original, 'entity_id': setting, 'description': desc,
                                        'type': 2, 'mentions': 0, 'excerpt_ids': [], 'occurrence': []}

        for term, alias_list in aliases.items():
            if term.lower() in self._entity_data.keys():
                for alias in alias_list:
                    self._aliases[alias.lower()] = term.lower()

    @property
    def parsed_data(self):
        return self._parsed_data

    def parse(self):
        '''Parses book'''
        erl, codec = self.find_erl_and_encoding()
        notable_clips, excerpt_data = self._parse_paragraph_data(codec)

        num_excerpts = len(excerpt_data)
        # add random excerpts to make sure notable clips has at least 20 excerpts
        if len(notable_clips) + num_excerpts >= 20:
            num_of_notable_clips = 20
        else:
            num_of_notable_clips = len(notable_clips) + num_excerpts
        while len(notable_clips) < num_of_notable_clips:
            rand_excerpt = randrange(0, num_excerpts - 1)
            if rand_excerpt not in notable_clips:
                notable_clips.append(rand_excerpt)

        self._parsed_data = {'erl': erl,
                             'excerpt_data': excerpt_data,
                             'notable_clips': notable_clips,
                             'entity_data': self._entity_data,
                             'codec': codec}

    def _parse_paragraph_data(self, codec):
        '''Parses paragraph data in book'''
        escaped_word_list = [re.escape(word) for word in self._aliases.keys() + self._entity_data.keys()]
        word_pat = re.compile(r'(\b' + r'\b|\b'.join(escaped_word_list) + r'\b)', re.I)

        # get db data
        excerpt_id = 0
        excerpt_data = {}
        notable_clips = []
        for word_loc, para_start in self._get_paragraph_data(codec):
            related_entities = []
            if len(self._entity_data.keys()) > 0:
            # for each match found, fill in entity_data and excerpt_data information
                for match in re.finditer(word_pat, word_loc['words']):
                    entity_id = self._process_match(match, codec, excerpt_id, word_loc)
                    if entity_id not in related_entities:
                        related_entities.append(entity_id)
            for quote in self._quotes:
                if quote.lower() in word_loc['words'].lower() and excerpt_id not in notable_clips:
                    notable_clips.append(excerpt_id)
            excerpt_data[excerpt_id] = {'loc': para_start, 'len': self._find_len_excerpt(word_loc),
                                        'related_entities': related_entities}
            excerpt_id += 1

        return notable_clips, excerpt_data

    def _get_paragraph_data(self, codec):
        '''Gets paragraphs from book'''
        paragraph_data = []
        book_html = MobiExtractor(self._book_path, open(os.devnull, 'w')).extract_text()

        # find all paragraphs (sections enclosed in html p tags) and their starting offset
        for node in re.finditer(PARAGRAPH_PAT, book_html):
            # get plain text from paragraph and locations of letters from beginning of file
            results = [(word.group(0)[1:-1].decode(codec), word.start(0))
                       for word in re.finditer(PLAIN_TEXT_PAT, node.group(0))]
            word_loc = {'words': '', 'locs': [], 'char_sizes': []}
            for group, loc in results:
                start = node.start(0) + loc + 1 + self._offset
                for char in group:
                    word_loc['words'] += char
                    word_loc['locs'].append(start)
                    start += len(char.encode(codec))
                    word_loc['char_sizes'].append(len(char.encode(codec)))
            if len(word_loc['locs']) > 0:
                paragraph_data.append((word_loc, word_loc['locs'][0]))

        return paragraph_data

    def _process_match(self, match, codec, excerpt_id, word_loc):
        matched_word = match.group(1).decode(codec).lower()
        if matched_word in self._entity_data.keys():
            term = self._entity_data[matched_word]
        elif matched_word in self._aliases.keys():
            term = self._entity_data[self._aliases[matched_word]]
        entity_id = term['entity_id']
        term['mentions'] += 1
        term['excerpt_ids'].append(excerpt_id)
        word_start = self._find_start(match.start(0), word_loc['words'])
        term['occurrence'].append({'loc': word_loc['locs'][word_start],
                                   'len': self._find_len_word(match.start(0), match.end(0), word_loc)})
        return entity_id

    @staticmethod
    def _find_start(start, string):
        '''Finds beggining index of word'''
        previous_space = string[:start].rfind(' ')
        if previous_space == -1:
            start_index = 0
        else:
            start_index = previous_space + 1
        return start_index

    @staticmethod
    def _find_len_word(start, end, word_loc):
        '''Finds length between starting index of word and the next space'''
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

    @staticmethod
    def _find_len_excerpt(word_loc):
        '''Finds length of excerpt'''
        string = word_loc['words']
        char_sizes = word_loc['char_sizes']

        total_len = 0
        for char in range(0, len(string)):
            total_len += char_sizes[char]

        return total_len

    def find_erl_and_encoding(self):
        '''Finds book's erl and codec'''
        with open(self._book_path, 'rb') as fname:
            book_data = fname.read()

        try:
            nrecs, = unpack('>H', book_data[76:78])
            recs_start = 78 + (nrecs * 8) + 2
            erl, = unpack('>L', book_data[recs_start + 4:recs_start + 8])
            codec = 'latin-1' if unpack('>L', book_data[recs_start + 28:recs_start + 32])[0] == 1252 else 'utf8'
            return erl, codec
        except error:
            raise MobiError

class MobiExtractor(MobiReader):
    '''Reads MOBI file'''
    def extract_text(self, offset=1):
        '''Gets text from file'''
        text_sections = [self.text_section(i) for i in range(offset, min(self.book_header.records + offset,
                                                                         len(self.sections)))]
        processed_records = list(range(offset-1, self.book_header.records +
                                       offset))

        mobi_html = b''

        if self.book_header.compression_type == 'DH':
            huffs = [self.sections[i][0] for i in range(self.book_header.huff_offset,
                                                        self.book_header.huff_offset + self.book_header.huff_number)]
            processed_records += list(range(self.book_header.huff_offset,
                                            self.book_header.huff_offset + self.book_header.huff_number))
            huff = HuffReader(huffs)
            huff_unpack = huff.unpack

        elif self.book_header.compression_type == '\x00\x02':
            huff_unpack = decompress_doc

        elif self.book_header.compression_type == '\x00\x01':
            huff_unpack = lambda x: x
        else:
            raise MobiError('Unknown compression algorithm: %s' % repr(self.book_header.compression_type))
        mobi_html = b''.join(map(huff_unpack, text_sections))
        if mobi_html.endswith(b'#'):
            mobi_html = mobi_html[:-1]

        if self.book_header.ancient and '<html' not in mobi_html[:300].lower():
            mobi_html = mobi_html.replace('\r ', '\n\n ')
        mobi_html = mobi_html.replace('\0', '')
        if self.book_header.codec == 'cp1252':
            mobi_html = mobi_html.replace('\x1e', '')  # record separator
            mobi_html = mobi_html.replace('\x02', '')  # start of text
        return mobi_html
