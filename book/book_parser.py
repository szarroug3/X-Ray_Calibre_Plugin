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

    def update_ASIN(self, val):
        new_recs = [(113, val.encode(self._encoding)), (504, val.encode(self._encoding))]
        for rec_type, rec_val in self._exth_data.items():
            if rec_type != 113 and rec_type != 504:
                new_recs.append((rec_type, rec_val))

        new_recs.sort(key=lambda x:x[0])

        new_exth = b''
        for rec_type, rec_val in new_recs:
            new_exth = new_exth + pack('>LL', rec_type, len(rec_val) + 8) + rec_val

        # make new exth string with padding at the end
        new_exth = b'EXTH' + pack('>LL', len(new_exth) + 12, len(new_recs)) + new_exth + (b'\0' * self._pad(len(new_exth) + 12, 4))
        print (unpack('>4sLLLL', new_exth[:20]))

        with open('test.mobi', 'wb') as f:
            f.write(self._book_data[:self._records_start + self._exth_start])
            f.write(new_exth)
            f.write(self._book_data[self._records_start + self._exth_end:])