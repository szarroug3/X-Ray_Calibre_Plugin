# mobi.py

from __future__ import (absolute_import, print_function)

import os
import re
import struct
from urllib import urlencode
from cStringIO import StringIO
from httplib import HTTPConnection, BadStatusLine

from calibre.ebooks.mobi import MobiError
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.metadata.mobi import MetadataUpdater

from calibre_plugins.xray_creator.helpers.book_parser import BookParser
from calibre_plugins.xray_creator.helpers.shelfari_parser import ShelfariParser

class Books(object):
    def __init__(self, db, book_ids):
        self._book_ids = book_ids
        self._db = db
        self._books = []
        self._books_skipped = []
        self._aConnection = HTTPConnection('www.amazon.com')
        self._sConnection = HTTPConnection('www.shelfari.com')

        for book_id in book_ids:
            title = db.field_for('title', book_id)
            author, = db.field_for('authors', book_id)
            asin = db.field_for('identifiers', book_id)['mobi-asin'].decode('ascii')
            book_path = db.format_abspath(book_id, 'MOBI')
            if book_path and title and author:
                self._books.append(Book(book_id, book_path, title, author, asin=asin, aConnection=self._aConnection, sConnection=self._sConnection))
                continue
            if title and author: self._books_skipped.append('%s - %s missing book path.' % (title, author))
            elif book_path: self._books_skipped.append('%s missing title or author.' % (os.path.basename(book_path).split('.')[0]))
            else: self._books_skipped.append('Unknown book with id %s missing book path, title and/or author.' % book_id)


    @property
    def books(self):
        return self._books

    @property
    def book_skipped(self):
        return self._book_skipped

    def update_asins(self):
        books_to_remove = []
        for book in self._books:
            try:
                update = False
                if not book.asin or len(book.asin) != 10:
                    mi = self._db.get_metadata(book.book_id)
                    book.asin = mi.get_identifier['mobi-asin']
                    update = True
                if not book.asin or len(book.asin) != 10:
                    self._aConnection = book.get_asin()
                    update = True
                if not book.asin or len(book.asin) != 10:
                    books_to_remove.append((book, '%s - %s skipped because could not find ASIN or ASIN is invalid.' % (book.title, book.author)))
                    continue
                if update: book.update_asin()
            except Exception as e:
                books_to_remove.append((book, '%s - %s skipped because %s.' % (book.title, book.author, e)))

        for book, reason in books_to_remove:
            self._books.remove(book)
            self._books_skipped.append(reason)

    def get_shelfari_urls(self):
        books_to_remove = []
        for book in self._books:
            try:
                if book.asin and len(book.asin) == 10:
                    self._sConnection = book.get_shelfari_url()
                    if not book.shelfari_url:
                        books_to_remove.append((book, '%s - %s skipped because no shelfari url found.' % (book.title, book.author)))
            except Exception as e:
                books_to_remove.append((book, '%s - %s skipped because %s.' % (book.title, book.author, e)))

        for book, reason in books_to_remove:
            self._books.remove(book)
            self._books_skipped.append(reason)

    def parse_shelfari_data(self):
        books_to_remove = []
        for book in self._books:
            try:
                book.parse_shelfari_data()
            except Exception:
                books_to_remove.append((book, '%s - %s skipped because could not parse shelfari data.' % (book.title, book.author)))

        for book, reason in books_to_remove:
            self._books.remove(book)
            self._books_skipped.append(reason)

    def parse_book_data(self):
        books_to_remove = []
        for book in self._books:
            #try:
            book.parse_book_data()
            # except Exception:
            #     books_to_remove.append((book, '%s - %s skipped because could not parse book data.' % (book.title, book.author)))

        for book, reason in books_to_remove:
            self._books.remove(book)
            self._books_skipped.append(reason)

    def create_xray_files(self):
        books_to_remove = []
        for book in self._books:
            #try:
            book.create_xray_file()
            # except Exception:
            #     books_to_remove.append((book, '%s - %s skipped because could not write X-Ray file.' % (book.title, book.author)))

        for book, reason in books_to_remove:
            self._books.remove(book)
            self._books_skipped.append(reason)

    def create_xrays(self):
        self.update_asins()
        self.get_shelfari_urls()
        self.parse_shelfari_data()
        self.parse_book_data()

        for book in self._books:
            print ('%s - %s' % (book.title, book.author))
        print
        for book in self._books_skipped:
            print (book)



class Book(object):
    AMAZON_ASIN_PAT = re.compile(r'data\-asin=\"([a-zA-z0-9]+)\"')
    SHELFARI_URL_PAT = re.compile(r'href="(.+/books/.+?)"')
    HEADERS = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain", "User-Agent": "Mozilla/5.0"}

    def __init__(self, book_id, book_path, title, author, asin=None, aConnection=None, sConnection=None, shelfari_url=None):
        self._book_id = book_id
        self._book_path = book_path
        self._xray_directory = os.path.join(*os.path.abspath(self._book_path).split('.')[:-1]) + '.sdr'
        self._author = author
        self._title = title
        if asin:
            self._asin = asin
        else:
            self.check_asin()
        self._shelfari_url = shelfari_url
        if aConnection:
            self._aConnection = aConnection
        else:
            self._aConnection = HTTPConnection('www.amazon.com')
        if sConnection:
            self._sConnection = sConnection
        else:
            self._sConnection = HTTPConnection('www.shelfari.com')

    @property
    def book_id(self):
        return self._book_id
    
    @property
    def title(self):
        return self._title

    @property
    def author(self):
        return self._author

    @property
    def asin(self):
        return self._asin

    @property
    def shelfari_url(self):
        return self._shelfari_url
    
    @property
    def aConnection(self):
        return self._aConnection

    @property
    def sConnection(self):
        return self._sConnection

    @property
    def xray_db_creator(self):
        return self._xray_db_creator

    @property
    def xray_directory(self):
        return self._xray_directory    
     
    def get_asin(self):
        query = urlencode({'keywords': '%s - %s' % ( self._title, self._author)})
        self.aConnection.request('GET', '/s/ref=sr_qz_back?sf=qz&rh=i%3Adigital-text%2Cn%3A154606011%2Ck%3A' + query[9:] + '&' + query, None, self.HEADERS)
        try:
            response = self.aConnection.getresponse().read()
        except BadStatusLine:
            self.aConnection.close()
            self.aConnection = HTTPConnection('www.amazon.com')
            self.aConnection.request('GET', '/s/ref=sr_qz_back?sf=qz&rh=i%3Adigital-text%2Cn%3A154606011%2Ck%3A' + query[9:] + '&' + query, None, self.HEADERS)
            response = self.aConnection.getresponse().read()
        # check to make sure there are results
        if 'did not match any products' in response and not 'Did you mean:' in response and not 'so we searched in All Departments' in response:
            raise ValueError('Could not find ASIN for %s - %s' % ( self._title, self._author))
        soup = BeautifulSoup(response)
        results = soup.findAll('div', {'id': 'resultsCol'})
        for r in results:
            if 'Buy now with 1-Click' in str(r):
                asinSearch = self.AMAZON_ASIN_PAT.search(str(r))
                if asinSearch:
                    self._asin = asinSearch.group(1)
                    return self.aConnection
        raise ValueError('Could not find ASIN for %s - %s' % ( self._title, self._author))

    def check_asin(self):
        with open(self._book_path, 'r') as stream:
            mu = MobiASINUpdater(stream)
            self._asin = mu.update(asin=self.asin)

    def update_asin(self):
        with open(self._book_path, 'r+b') as stream:
            mu = MobiASINUpdater(stream)
            self._asin = mu.update(asin=self.asin)

    def get_shelfari_url(self):
        query = urlencode ({'Keywords': self.asin})
        self.sConnection.request('GET', '/search/books?' + query)
        try:
            response = self.sConnection.getresponse().read()
        except BadStatusLine:
            self.sConnection.close()
            self.sConnection = HTTPConnection('www.shelfari.com')
            self.sConnection.request('GET', '/search/books?' + query)
            response = self.sConnection.getresponse().read()
        
        # check to make sure there are results
        if 'did not return any results' in response:
            return self.sConnection
        urlsearch = self.SHELFARI_URL_PAT.search(response)
        if not urlsearch:
            return self.sConnection
        self._shelfari_url = urlsearch.group(1)
        return self.sConnection

    def parse_shelfari_data(self):
        self._parsed_shelfari_data = ShelfariParser(self._shelfari_url)
        self._parsed_shelfari_data.parse()

    def parse_book_data(self):
        self._parsed_book_data = BookParser(self._book_path, self._parsed_shelfari_data)
        self._parsed_book_data.parse()

    def write_xray_file(self):
        self._xray_db_writer = XRayDBWriter(self.xray_directory, self.asin, self._parsed_book_data)
        self._xray_db_writer.create_xray()

class MobiASINUpdater(MetadataUpdater):
    def update(self, asin):
        def update_exth_record(rec):
            recs.append(rec)
            if rec[0] in self.original_exth_records:
                self.original_exth_records.pop(rec[0])

        if self.type != "BOOKMOBI":
                raise MobiError("Setting ASIN only supported for MOBI files of type 'BOOK'.\n"
                                "\tThis is a '%s' file of type '%s'" % (self.type[0:4], self.type[4:8]))

        recs = []
        update_exth_record((113, asin.encode(self.codec, 'replace')))
        update_exth_record((504, asin.encode(self.codec, 'replace')))

        # Include remaining original EXTH fields
        for id in sorted(self.original_exth_records):
            recs.append((id, self.original_exth_records[id]))
        recs = sorted(recs, key=lambda x:(x[0],x[0]))

        exth = StringIO()
        for code, data in recs:
            exth.write(struct.pack('>II', code, len(data) + 8))
            exth.write(data)
        exth = exth.getvalue()
        trail = len(exth) % 4
        pad = '\0' * (4 - trail) # Always pad w/ at least 1 byte
        exth = ['EXTH', struct.pack('>II', len(exth) + 12, len(recs)), exth, pad]
        exth = ''.join(exth)

        if getattr(self, 'exth', None) is None:
            raise MobiError('No existing EXTH record. Cannot update ASIN.')

        self.create_exth(exth=exth)

        return asin

    def check_for_asin(self):
        if 113 in self.original_exth_records.keys() and len(self.original_exth_records[113]) == 10:
            if 504 in self.original_exth_records.keys() and self.original_exth_records[504] == self.original_exth_records[113]:
                return 1
            return self.original_exth_records[113]
        if 504 in self.original_exth_records.keys() and len(self.original_exth_records[504]) == 10:
                return self.original_exth_records[504]