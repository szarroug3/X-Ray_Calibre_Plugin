# mobi.py

from __future__ import (absolute_import, print_function)

import os
import re
import struct
import ctypes
from glob import glob
from shutil import copy
from urllib import urlencode
from datetime import datetime
from cStringIO import StringIO
from httplib import HTTPConnection, BadStatusLine

from calibre.ebooks.mobi import MobiError
from calibre.ebooks.metadata.meta import get_metadata, set_metadata
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.metadata.mobi import MetadataUpdater

from calibre_plugins.xray_creator.helpers.book_parser import BookParser
from calibre_plugins.xray_creator.helpers.xray_db_writer import XRayDBWriter
from calibre_plugins.xray_creator.helpers.shelfari_parser import ShelfariParser

# Drive types
DRIVE_UNKNOWN     = 0  # The drive type cannot be determined.
DRIVE_NO_ROOT_DIR = 1  # The root path is invalbookID; for example, there is no volume mounted at the specified path.
DRIVE_REMOVABLE   = 2  # The drive has removable media; for example, a floppy drive, thumb drive, or flash card reader.
DRIVE_FIXED       = 3  # The drive has fixed media; for example, a hard disk drive or flash drive.
DRIVE_REMOTE      = 4  # The drive is a remote (network) drive.
DRIVE_CDROM       = 5  # The drive is a CD-ROM drive.
DRIVE_RAMDISK     = 6  # The drive is a RAM disk.
books_updated = []
books_skipped = []

class Books(object):
    def __init__(self, db, book_ids, spoilers=False, send_to_device=True, create_xray=True):
        self._book_ids = book_ids
        self._db = db
        self._books = []
        self._books_skipped = []
        self._aConnection = HTTPConnection('www.amazon.com')
        self._sConnection = HTTPConnection('www.shelfari.com')
        self._spoilers = spoilers
        self._send_to_device = send_to_device
        self._create_xray = create_xray

        for book_id in book_ids:
            title = self._db.field_for('title', book_id)
            title_sort = self._db.field_for('sort', book_id)
            author = self._db.field_for('authors', book_id)
            if len(author) > 0:
                author = author[0]
            author_sort = self._db.field_for('author_sort', book_id)
            identifiers = self._db.field_for('identifiers', book_id)
            if 'mobi-asin' in identifiers.keys():
                asin = db.field_for('identifiers', book_id)['mobi-asin'].decode('ascii')
            else:
                asin = None
            local_book_path = db.format_abspath(book_id, 'MOBI')
            if local_book_path and title and author and title_sort and author_sort:
                device_book_path = os.path.join('documents', author_sort, title_sort + ' - ' + author + '.mobi')
                self._books.append(Book(book_id, local_book_path, device_book_path, title, author, asin=asin, aConnection=self._aConnection, sConnection=self._sConnection, spoilers=self._spoilers, db=self._db))
                continue
            if title and author: self._books_skipped.append('%s - %s missing book path.' % (title, author))
            elif local_book_path: self._books_skipped.append('%s missing title or author.' % (os.path.basename(local_book_path).split('.')[0]))
            else: self._books_skipped.append('Unknown book with id %s missing book path, title and/or author.' % book_id)


    @property
    def books(self):
        return self._books

    @property
    def book_skipped(self):
        return self._book_skipped

    def _find_kindle(self):
        drive_info = self._get_drive_info()
        removable_drives = [drive_letter for drive_letter, drive_type in drive_info if drive_type == DRIVE_REMOVABLE]
        for drive in removable_drives:
            for dirName, subDirList, fileList in os.walk(drive):
                if dirName == drive + 'system\.mrch':
                    for fName in fileList:
                        if 'amzn1_account' in fName:
                            return drive
        return None

    # Return list of tuples mapping drive letters to drive types
    def _get_drive_info(self):
        result = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            bit = 2 ** i
            if bit & bitmask:
                drive_letter = '%s:' % chr(65 + i)
                drive_type = ctypes.windll.kernel32.GetDriveTypeA('%s\\' % drive_letter)
                result.append((drive_letter, drive_type))
        return result

    def update_asin(self, book):
        try:
            if not book.asin or len(book.asin) != 10:
                self._aConnection = book.get_asin()
            if not book.asin or len(book.asin) != 10:
                self._books.remove(book)
                self._books_skipped.append('%s - %s skipped because could not find ASIN or ASIN is invalid.' % (book.title, book.author))
                return False
            mi = self._db.get_metadata(book.book_id)
            mi.get_identifiers()['mobi-asin'] = book.asin
            self._db.set_metadata(book.book_id, mi)
            book.update_asin()
        except Exception as e:
            self._books.remove(book)
            self._books_skipped.append('%s - %s skipped because could not update ASIN.\n\t\t%s.' % (book.title, book.author, e))
            return False

        return True

    def get_shelfari_url(self, book):
        try:
            if book.asin and len(book.asin) == 10:
                self._sConnection = book.get_shelfari_url()
                if not book.shelfari_url:
                    self._books.remove(book)
                    self._books_skipped.append('%s - %s skipped because no shelfari url found.' % (book.title, book.author))
                    return False
        except Exception as e:
            self._books.remove(book)
            self._books_skipped.append('%s - %s skipped because %s.' % (book.title, book.author, e))
            return False

        return True

    def parse_shelfari_data(self, book):
        try:
            book.parse_shelfari_data()
        except Exception as e:
            self._books.remove(book)
            self._books_skipped.append('%s - %s skipped because could not parse shelfari data.\n\t\t%s' % (book.title, book.author, e))
            return False

        return True

    def parse_book_data(self, book, log=None):
        try:
            book.parse_book_data(log=log)
        except Exception as e:
            self._books.remove(book)
            self._books_skipped.append('%s - %s skipped because could not parse book data.\n\t\t%s' % (book.title, book.author, e))
            return False

        return True

    def write_xray_file(self, book):
        try:
            book.write_xray_file()
        except Exception as e:
            self._books.remove(book)
            self._books_skipped.append('%s - %s skipped because could not write X-Ray file.\n\t\t%s' % (book.title, book.author, e))
            return False

        return True

    def send_xray(self, book, kindle_drive, already_created_xray=True):
        try:
            book.send_xray(kindle_drive, already_created_xray=already_created_xray)
        except Exception as e:
            self._books.remove(book)
            self._books_skipped.append('%s - %s skipped because could not send x-ray.\n\t\t%s.' % (book.title, book.author, e))
            return False

        return True

    def create_xrays_event(self, abort, log, notifications):
        notif = notifications
        actions = 5.0
        if self._send_to_device:
            actions += 1
        for i, book in enumerate(self._books):
            title_and_author = '%s - %s' % (book.title, book.author)
            if abort.isSet():
                return
            log('%s\t%s' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S'), title_and_author))
            notif.put(((i * actions)/(len(self._books) * actions), 'Updating %s ASIN' % title_and_author))
            log('%s\t\tUpdating ASIN' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            completed = self.update_asin(book)
            if not completed:
                continue

            if abort.isSet():
                return

            notif.put((((i * actions) + 1)/(len(self._books) * actions), 'Getting %s shelfari URL' % title_and_author))
            log('%s\t\tGetting shelfari URL' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            completed = self.get_shelfari_url(book)
            if not completed:
                continue

            if abort.isSet():
                return
            notif.put((((i * actions) + 2)/(len(self._books) * actions), 'Parsing %s shelfari data' % title_and_author))
            log('%s\t\tParsing shelfari data' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            completed = self.parse_shelfari_data(book)
            if not completed:
                continue

            if abort.isSet():
                return
            notif.put((((i * actions) + 3)/(len(self._books) * actions), 'Parsing %s book data' % title_and_author))
            log('%s\t\tParsing book data' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            completed = self.parse_book_data(book)
            if not completed:
                continue

            if abort.isSet():
                return
            notif.put((((i * actions) + 4)/(len(self._books) * actions), 'Creating %s x-ray' % title_and_author))
            log('%s\t\tCreating x-ray' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            completed = self.write_xray_file(book)
            if not completed:
                continue

            if self._send_to_device:
                if abort.isSet():
                    return
                kindle_drive = self._find_kindle()
                notif.put((((i * actions) + 5)/(len(self._books) * actions), 'Sending %s x-ray to device' % title_and_author))
                log('%s\t\tSending x-ray to device' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                if kindle_drive:
                    self.send_xray(book, kindle_drive)

        if len(self._books_skipped) > 0:
            log('\nBooks Skipped:')
            for book in self._books_skipped:
                log('\t%s' % book)

        if len(self._books) > 0:
            log('\nBooks Completed:')
            for book in self._books:
                log('\t%s - %s' % (book.title, book.author))

    def send_xrays_event(self, abort, log, notifications):
        kindle_drive = self._find_kindle()
        if not kindle_drive:
            raise Exception('No device connected.')
        notif = notifications
        for i, book in enumerate(self._books):
            if abort.isSet():
                return
            notif.put((i/float(len(self._books)), 'Sending %s - %s x-ray to Device' % (book.title, book.author)))
            self.send_xray(book, kindle_drive, already_created_xray=False)

        if len(self._books_skipped) > 0:
            log('Books Skipped:')
            for book in self._books_skipped:
                log('\t%s' % book)

        if len(self._books) > 0:
            log('Books Completed:')
            for book in self._books:
                log('\t%s - %s' % (book.title, book.author))

class Book(object):
    AMAZON_ASIN_PAT = re.compile(r'data\-asin=\"([a-zA-z0-9]+)\"')
    SHELFARI_URL_PAT = re.compile(r'href="(.+/books/.+?)"')
    HEADERS = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain", "User-Agent": "Mozilla/5.0"}

    def __init__(self, book_id, local_book_path, device_book_path, title, author, asin=None, db=None, aConnection=None, sConnection=None, shelfari_url=None, spoilers=False, create_xray=True):
        self._book_id = book_id
        self._local_book_path = local_book_path
        self._device_book_path = device_book_path
        self._local_xray_directory = self._local_book_path[:-4] + 'sdr'
        self._device_xray_directory = self._device_book_path[:-4] + 'sdr'
        self._author = author
        self._title = title
        self._spoilers = spoilers
        self._create_xray = create_xray
        self._db = db
        if asin:
            self._asin = asin
        else:
            self._asin = None
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
    def local_xray_directory(self):
        return self._local_xray_directory

    @property
    def device_xray_directory(self):
        return self._device_xray_directory
      
     
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
            raise ValueError('Could not find Amazon page for %s - %s' % ( self._title, self._author))
        soup = BeautifulSoup(response)
        results = soup.findAll('div', {'id': 'resultsCol'})
        for r in results:
            if 'Buy now with 1-Click' in str(r):
                asinSearch = self.AMAZON_ASIN_PAT.search(str(r))
                if asinSearch:
                    self._asin = asinSearch.group(1)
                    return self.aConnection
        raise ValueError('Could not find ASIN for %s - %s' % ( self._title, self._author))

    def update_asin(self):
        with open(self._local_book_path, 'r+b') as stream:
            mu = MobiASINUpdater(stream)
            self._asin = mu.update(asin=self.asin)

    def update_asin_on_device(self, asin):
        with open(self._device_book_path, 'r+b') as stream:
            mu = MobiASINUpdater(stream)
            self._asin = mu.update(asin=asin)

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
        self._parsed_shelfari_data = ShelfariParser(self._shelfari_url, spoilers=self._spoilers)
        self._parsed_shelfari_data.parse()

    def parse_book_data(self, log=None):
        self._parsed_book_data = BookParser(self._local_book_path, self._parsed_shelfari_data)
        self._parsed_book_data.parse(log=log)

    def write_xray_file(self):
        self._xray_db_writer = XRayDBWriter(self.local_xray_directory, self.asin, self.shelfari_url, self._parsed_book_data)
        self._xray_db_writer.create_xray()

    def create_xray(self):
        try:
            if not self.asin or len(self.asin) != 10:
                self._aConnection = self.get_asin()
            if not self.asin or len(self.asin) != 10:
                return
            mi = self._db.get_metadata(self.book_id)
            mi.get_identifiers()['mobi-asin'] = self.asin
            self._db.set_metadata(self.book_id, mi)
            self.update_asin()
            if self.asin and len(self.asin) == 10:
                self._sConnection = self.get_shelfari_url()
                if not self.shelfari_url:
                    books_to_remove.append((self, '%s - %s skipped because no shelfari url found.' % (self.title, self.author)))
            book.parse_shelfari_data()
            book.parse_book_data()
            book.write_xray_file()
        except Exception:
            return

    def send_xray(self, kindle_drive, already_created_xray=False):
        self._device_xray_directory = os.path.join(kindle_drive, os.sep, self._device_xray_directory)
        self._device_book_path = os.path.join(kindle_drive, os.sep, self._device_book_path)

        # check if x-ray directory and book path exist, return if either doesn't - that means book isn't on kindle
        if not os.path.exists(self._device_xray_directory) or not os.path.exists(self._device_book_path):
            return

        # do nothing if book already has x-ray
        if len(glob(os.path.join(self._device_xray_directory, '*.asc'))) > 0:
            return

        # do nothing if book has no x-ray and create_xray is false
        if not self._create_xray and already_created_xray:
            return

        # check if there's a local x-ray file and create one if there isn't
        local_file = glob(os.path.join(self._local_xray_directory, '*.asc'))
        if len(local_file) == 0:
            self.create_xray()

        # check if there's a local x-ray file and copy it to device if there is
        local_file = glob(os.path.join(self._local_xray_directory, '*.asc'))
        if len(local_file) > 0:
            self.update_asin_on_device(local_file[0].split('.')[3])
            copy(local_file[0], os.path.join(kindle_drive, os.sep, self._device_xray_directory))

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