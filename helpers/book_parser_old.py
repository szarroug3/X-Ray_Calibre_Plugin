# book_parser.py

from struct import *

class BookParser(object):
    def __init__(self, book_path):
        self._book_path = book_path
        self._parse_book()

    def _parse_book(self):
        with open(self._book_path, 'rb') as f:
            self._book_data = f.read()

        self._dbName = self._book_data[0:32]
        self._numOfRecs, = unpack('>H', self._book_data[76:78])
        self._records_start = 78 + (self._numOfRecs * 8) + 2
        self._records = self._book_data[self._records_start:]

        # get erl and encoding
        self._erl, = unpack('>L', self._records[4:8])
        self._encoding = 'latin-1' if unpack('>L', self._records[28:32])[0] == 1252 else 'utf8'
        
        # check if mobi has exth and get exth record location
        if self._records[16:20] != b'MOBI':
            raise ValueError('MOBI header not found.')
        has_exth = bin(unpack('>L', self._records[128:132])[0])[2] == '1'
        if not has_exth:
            raise ValueError('Book has no EXTH.')
        self._exth_start = unpack('>L', self._records[20:24])[0] + 16
        self._exth = self._records[self._exth_start:]
        if self._exth[:4] != b'EXTH':
            raise ValueError('EXTH header not found.')
        exth_len, self._num_of_exth = unpack('>LL', self._exth[4:12])
        self._exth_end = exth_len + self._pad(exth_len, 4)
        self._exth = self._exth[:self._exth_end]
        self._parse_exth()


    def _parse_exth(self):
        self._exth_data = {}
        pos = 12
        for i in range(self._num_of_exth):
            rec_type, rec_length = unpack('>LL', self._exth[pos:pos + 8])
            pos = pos + 8
            self._exth_data[rec_type] = self._exth[pos:pos + rec_length - 8]
            pos = pos + rec_length - 8

    def _pad(self, val, mod):
        if val % mod == 0:
            return 0
        return mod - (val % mod)