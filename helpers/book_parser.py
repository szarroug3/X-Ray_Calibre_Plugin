# book_parser.py

import os
from struct import unpack

from calibre.ebooks.mobi.huffcdic import HuffReader
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.mobi.reader.mobi6 import MobiReader
from calibre.ebooks.compression.palmdoc import decompress_doc

class BookParser(object):
    def __init__(self, book_path):
        self._book_path = book_path

    def parse(self):
        self._book_html = MobiExtractor(self._book_path, open(os.devnull, 'w')).extract_text()
        self.find_erl_and_encoding()
        self._book_html_soup = BeautifulSoup(self._book_html)
        self._book_text = [paragraph.decode(self._codec) for paragraph in self._book_html_soup.findAll("p", text=True)]
        

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