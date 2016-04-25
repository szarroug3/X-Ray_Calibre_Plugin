# xray_creator.py

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
    def __init__(self, db, book_ids, types=[], spoilers=False, send_to_device=True, create_xray=True):
        self._book_ids = book_ids
        self._db = db
        self._books = []
        self._books_skipped = []
        self._aConnection = HTTPConnection('www.amazon.com')
        self._sConnection = HTTPConnection('www.shelfari.com')
        self._send_to_device = send_to_device

        if len(types) == 0:
            self._books_skipped.append('No books processed because no book file type chosen in preferences.')
            return

        for book_id in book_ids:
            # Get basic book information
            title = self._db.field_for('title', book_id)
            title_sort = self._db.field_for('sort', book_id)
            author = self._db.field_for('authors', book_id)
            if len(author) > 0:
                author = ' & '.join(author)
            author_sort = self._db.field_for('author_sort', book_id)
            identifiers = self._db.field_for('identifiers', book_id)
            asin = self._db.field_for('identifiers', book_id)['mobi-asin'].decode('ascii') if 'mobi-asin' in identifiers.keys() else None

            if not title or not title_sort or not author or not author_sort:
                if title:
                    self._books_skipped.append('%s: missing title sort, author, or author sort information.' % title)
                    continue
                if title_sort:
                    self._books_skipped.append('%s: missing title, author, or author sort information.' % title_sort)
                    continue
                if author:
                    self._books_skipped.append('%s: missing title, title sort, or author sort information.' % title_sort)
                    continue
                if author_sort:
                    self._books_skipped.append('%s: missing title, title sort, or author information.' % title_sort)
                    continue
                self._books_skipped.append('Unknown book missing title, title sort, author, and author sort information.')
                continue

            # Book definitely has title, title_sort, author, and author_sort at this point

            # sanitize author_sort and title_sort and get author name  in filename
            if author_sort[-1] == '.': author_sort = author_sort[:-1] + '_'
            author_sort = author_sort.replace(':', '_').replace('\"', '_')

            trailing_period = False
            while title_sort[-1] == '.':
                title_sort = title_sort[:-1]
                trailing_period = True
            if trailing_period:
                title_sort += '_'
            title_sort = title_sort.replace(':', '_').replace('\"', '_')

            trailing_period = False
            author_in_filename = author
            while author_in_filename[-1] == '.':
                author_in_filename = title_sort[:-1]
                trailing_period = True
            if trailing_period:
                author_in_filename += '_'
            author_in_filename = author_in_filename.replace(':', '_').replace('\"', '_')

            type_specific_data = []

            for book_type in types:
                type_info = {'type': book_type, 'local_book': db.format_abspath(book_id, book_type)}
                if not type_info['local_book']:
                    type_info['status'] = 'Fail'
                    type_info['status_message'] = 'Book path in %s format not found.' % book_type
                    type_specific_data.append(type_info)
                    continue

                # book path exists at this point
                type_info['status'] = 'In Progress'
                type_info['status_message'] = ''
                type_info['local_xray'] = os.path.join('.'.join(type_info['local_book'].split('.')[:-1]) + '.sdr', book_type)
                type_info['device_book'] = os.path.join('documents', author_sort, title_sort + ' - ' + author_in_filename + '.' + book_type.lower())
                type_info['device_xray'] = '.'.join(type_info['device_book'].split('.')[:-1]) + '.sdr'
                type_specific_data.append(type_info)
            self._books.append(Book(self._db, book_id, title, author, type_specific_data, asin, spoilers, create_xray))

    def _find_device(self):
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

    def create_xrays_event(self, abort, log, notifications):
        notif = notifications
        log('')
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
            if not book.asin or len(book.asin) != 10:
                self._aConnection = book.get_asin(self._aConnection)
            if book.status is 'Fail':
                continue
            book.update_asin()
            if book.status is 'Fail':
                continue

            if abort.isSet():
                return
            notif.put((((i * actions) + 1)/(len(self._books) * actions), 'Getting %s shelfari URL' % title_and_author))
            log('%s\t\tGetting shelfari URL' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            self._sConnection = book.get_shelfari_url(self._sConnection)
            if book.status is 'Fail':
                continue

            if abort.isSet():
                return
            notif.put((((i * actions) + 2)/(len(self._books) * actions), 'Parsing %s shelfari data' % title_and_author))
            log('%s\t\tParsing shelfari data' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            book.parse_shelfari_data()
            if book.status is 'Fail':
                continue

            if abort.isSet():
                return
            notif.put((((i * actions) + 3)/(len(self._books) * actions), 'Parsing %s book data' % title_and_author))
            log('%s\t\tParsing book data' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            book.parse_book_data()

            if abort.isSet():
                return
            notif.put((((i * actions) + 4)/(len(self._books) * actions), 'Creating %s x-ray' % title_and_author))
            log('%s\t\tCreating x-ray' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            book.write_xray_file()

            if self._send_to_device:
                if abort.isSet():
                    return
                device_drive = self._find_device()
                notif.put((((i * actions) + 5)/(len(self._books) * actions), 'Sending %s x-ray to device' % title_and_author))
                log('%s\t\tSending x-ray to device' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                book.send_xray(device_drive)

        if len(self._books_skipped) > 0:
            log('\nBooks Skipped:')
            for book in self._books_skipped:
                log('\t%s' % book)

        if len(self._books) > 0:
            log('\nBook Proccessing Information:')
            for book in self._books:
                log('\t%s - %s:' % (book.title, book.author))
                if book.status is 'Fail':
                    log('\t\t%s' % book.status_message)
                    continue
                for type_data in book.type_specific_data:
                    if type_data['status'] is 'Fail':
                        log('\t\t%s: %s' % (type_data['type'], type_data['status_message']))
                        continue
                    if not type_data['send_status']:
                        log('\t\t%s: %s' % (type_data['type'], type_data['send_status_message']))
                        continue
                    log('\t\t%s: Sent to device.' % type_data['type'])

    def send_xrays_event(self, abort, log, notifications):   
        log('')
        device_drive = self._find_device()
        if not device_drive:
            raise Exception('No device connected.')
        notif = notifications
        for i, book in enumerate(self._books):
            if abort.isSet():
                return
            notif.put((i/float(len(self._books)), 'Sending %s - %s x-ray to device' % (book.title, book.author)))
            log('%s\t%s - %s' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S'), book.title, book.author))
            book.send_xray(device_drive, already_created=False, log=log, aConnection=self._aConnection, sConnection=self._sConnection)

        if len(self._books_skipped) > 0:
            log('\nBooks Skipped:')
            for book in self._books_skipped:
                log('\t%s' % book)

        if len(self._books) > 0:
            log('\nBook Proccessing Information:')
            for book in self._books:
                log('\t%s - %s:' % (book.title, book.author))
                for type_data in book.type_specific_data:
                    if not type_data['send_status']:
                        log('\t\t%s: %s' % (type_data['type'], type_data['send_status_message']))
                        continue
                    log('\t\t%s: Sent to device.' % type_data['type'])


class Book(object):
    AMAZON_ASIN_PAT = re.compile(r'data\-asin=\"([a-zA-z0-9]+)\"')
    SHELFARI_URL_PAT = re.compile(r'href="(.+/books/.+?)"')
    HEADERS = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain", "User-Agent": "Mozilla/5.0"}

    def __init__(self, db, book_id, title, author, type_specific_data, asin, spoilers, create_xray):
        self._db = db
        self._book_id = book_id
        self._title = title
        self._author = author
        self._type_specific_data = type_specific_data
        self._asin = asin
        self._spoilers = spoilers
        self._create_xray = create_xray
        self._status = 'In Progress'
        self._status_message = None

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
    def status(self):
        return self._status

    @property
    def type_specific_data(self):
        return self._type_specific_data
    
    @property
    def status_message(self):
        return self._status_message
    
    def get_asin(self, connection):
        query = urlencode({'keywords': '%s - %s' % ( self._title, self._author)})
        connection.request('GET', '/s/ref=sr_qz_back?sf=qz&rh=i%3Adigital-text%2Cn%3A154606011%2Ck%3A' + query[9:] + '&' + query, None, self.HEADERS)
        try:
            response = connection.getresponse().read()
        except BadStatusLine:
            connection.close()
            connection = HTTPConnection('www.amazon.com')
            connection.request('GET', '/s/ref=sr_qz_back?sf=qz&rh=i%3Adigital-text%2Cn%3A154606011%2Ck%3A' + query[9:] + '&' + query, None, self.HEADERS)
            response = connection.getresponse().read()

        # check to make sure there are results
        if 'did not match any products' in response and not 'Did you mean:' in response and not 'so we searched in All Departments' in response:
            self._status = 'Fail'
            self._status_message = 'Could not find amazon page.'
            return
        soup = BeautifulSoup(response)
        results = soup.findAll('div', {'id': 'resultsCol'})
        for r in results:
            if 'Buy now with 1-Click' in str(r):
                asinSearch = self.AMAZON_ASIN_PAT.search(str(r))
                if asinSearch:
                    self._asin = asinSearch.group(1)
                    return connection

        self._status = 'Fail'
        self._status_message = 'Could not find ASIN on amazon page.'

    def update_asin(self):
        mi = self._db.get_metadata(self._book_id)
        mi.get_identifiers()['mobi-asin'] = self.asin
        self._db.set_metadata(self._book_id, mi)

        for type_data in self._type_specific_data:
            if type_data['status'] is not 'Fail':
                try:
                    if type_data['type'].lower() == 'mobi' or type_data['type'].lower() == 'azw3':
                        with open(type_data['local_book'], 'r+b') as stream:
                            mu = ASINUpdater(stream)
                            type_data['book_asin'] = mu.update(asin=self.asin)
                except Exception:
                    type_data['status'] = 'Fail'
                    type_data['status_message'] = 'Could not update ASIN in local book.'

    def update_asin_on_device(self, type_data, asin):
        if type_data['type'].lower() is 'mobi' or type_data['type'].lower() is 'azw3':
            with open(type_data['device_book'], 'r+b') as stream:
                mu = ASINUpdater(stream)
                mu.update(asin=asin)

    def get_shelfari_url(self, connection):
        query = urlencode ({'Keywords': self._asin})
        connection.request('GET', '/search/books?' + query)
        try:
            response = connection.getresponse().read()
        except BadStatusLine:
            connection.close()
            connection = HTTPConnection('www.shelfari.com')
            connection.request('GET', '/search/books?' + query)
            response = connection.getresponse().read()

        # check to make sure there are results
        if 'did not return any results' in response:
            self._status = 'Fail'
            self._status_message = 'Could not find shelfari page.'
            return connection
        urlsearch = self.SHELFARI_URL_PAT.search(response)
        if not urlsearch:
            self._status = 'Fail'
            self._status_message = 'Could not find shelfari page.'
            return connection
        self._shelfari_url = urlsearch.group(1)
        return connection

    def parse_shelfari_data(self):
        try:
            self._parsed_shelfari_data = ShelfariParser(self._shelfari_url, spoilers=self._spoilers)
            self._parsed_shelfari_data.parse()
            self._status = 'Success'
        except Exception:
            self._status = 'Fail'
            self._status_message = 'Could not parse shelfari data.'

    def parse_book_data(self, log=None):
        for type_data in self._type_specific_data:
            if type_data['status'] is not 'Fail':
                try:
                    type_data['parsed_book_data'] = BookParser(type_data['type'], type_data['local_book'], self._parsed_shelfari_data)
                    type_data['parsed_book_data'].parse(log=log)
                except Exception:
                    type_data['status'] = 'Fail'
                    type_data['status_message'] = 'Could not parse book data.'

    def write_xray_file(self):
        for type_data in self._type_specific_data:
            if type_data['status'] is not 'Fail':
                try:
                    xray_db_writer = XRayDBWriter(type_data['local_xray'], type_data['book_asin'], self._shelfari_url, type_data['parsed_book_data'])
                    xray_db_writer.create_xray()
                    type_data['status'] = 'Success'
                except Exception:
                    type_data['status'] = 'Fail'
                    type_data['status_message'] = 'Could not write x-ray file.'

    def create_xray(self, aConnection, sConnection, log=None):
        if log: log('%s\t\tUpdating ASIN' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
        if not self.asin or len(self.asin) != 10:
            aConnection = self.get_asin(aConnection)
        if self._status is 'Fail':
            return (aConnection, sConnection)
        self.update_asin()

        if log: log('%s\t\tGetting shelfari URL' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
        if self.asin and len(self.asin) == 10:
            sConnection = self.get_shelfari_url(sConnection)

        if self._status is 'Fail':
            return (aConnection, sConnection)

        if log: log('%s\t\tParsing shelfari data' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))       
        self.parse_shelfari_data()

        if self._status is 'Fail':
            return (aConnection, sConnection)

        if log: log('%s\t\tParsing book data' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
        self.parse_book_data()

        if log: log('%s\t\tCreating x-ray' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
        self.write_xray_file()

        if log: log('%s\t\tSending x-ray to device' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S')))

        return (aConnection, sConnection)

    def send_xray(self, device_drive, already_created=True, log=None, aConnection=None, sConnection=None):
        # find which version of book is on device
        sent = False
        rewritten = False
        for type_data in self.type_specific_data:
            print (type_data)
            if type_data['status'] is not 'Fail':
                type_data['send_status'] = False
                type_data['send_status_message'] = None
                if not device_drive:
                    type_data['send_status_message'] = 'Created x-ray but no device connected.'
                    continue
                type_data['device_xray'] = os.path.join(device_drive, os.sep, type_data['device_xray'])
                type_data['device_book'] = os.path.join(device_drive, os.sep, type_data['device_book'])

                # do nothing if book already has x-ray
                device_files = glob(os.path.join(type_data['device_xray'], '*.asc'))
                if len(device_files) > 0:
                    if sent:
                        type_data['send_status_message'] = 'X-Ray from another book format has already been sent.'
                        continue
                    if not already_created:
                        type_data['send_status_message'] = 'Book already has x-ray.'
                        continue

                if not os.path.exists(type_data['device_book']):
                    type_data['send_status_message'] = 'Book format not found on device.'
                    continue

                # do nothing if there is no local x-ray and we already tried to create one
                local_file = glob(os.path.join(type_data['local_xray'], '*.asc'))
                if not len(local_file) > 0:
                    if not self._create_xray:
                        type_data['send_status_message'] = 'No local x-ray found. Preferences set to not create one if not found.'
                        continue
                    if not already_created:
                        aConnection, sConnection = self.create_xray(aConnection, sConnection, log=log)
                    local_file = glob(os.path.join(type_data['local_xray'], '*.asc'))
                    if not len(local_file) > 0:
                        type_data['send_status_message'] = 'No local x-ray found. Already tried to create it but couldn\'t.'
                        continue

                try:
                    self.update_asin_on_device(type_data, local_file[0].split(os.sep)[-1].split('.')[2])
                except Exception:
                    type_data['send_status_message'] = 'Could not update ASIN in book on device.'
                    continue

                if len(device_files) > 0:
                    if rewritten:
                        type_data['send_status_message'] = 'Book already has x-ray.'
                        continue
                    for file in device_files:
                        os.remove(file)
                        rewritten = True

                if not os.path.exists(type_data['device_xray']):
                    os.mkdir(type_data['device_xray'])
                copy(local_file[0], type_data['device_xray'])
                type_data['send_status'] = True
                sent = True
        return (aConnection, sConnection)


class ASINUpdater(MetadataUpdater):
    def update(self, asin):
        def update_exth_record(rec):
            recs.append(rec)
            if rec[0] in self.original_exth_records:
                self.original_exth_records.pop(rec[0])

        if self.type != "BOOKMOBI":
                raise MobiError("Setting ASIN only supported for MOBI files of type 'BOOK'.\n"
                                "\tThis is a '%s' file of type '%s'" % (self.type[0:4], self.type[4:8]))

        recs = []
        if 113 in self.original_exth_records:
            return self.original_exth_records[113]
        if 504 in self.original_exth_records:
            asin = self.original_exth_records[504]

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