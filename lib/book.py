# Book.py

import os
import re
import struct
import ctypes
from glob import glob
from shutil import copy, rmtree
from urllib import urlencode
from datetime import datetime
from cStringIO import StringIO
from httplib import HTTPConnection, BadStatusLine

from calibre.ebooks.mobi import MobiError
from calibre.ebooks.metadata.meta import get_metadata, set_metadata
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.metadata.mobi import MetadataUpdater

from calibre_plugins.xray_creator.lib.book_parser import BookParser
from calibre_plugins.xray_creator.lib.xray_db_writer import XRayDBWriter
from calibre_plugins.xray_creator.lib.shelfari_parser import ShelfariParser

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

class Book(object):
    AMAZON_ASIN_PAT = re.compile(r'data\-asin=\"([a-zA-z0-9]+)\"')
    SHELFARI_URL_PAT = re.compile(r'href="(.+/books/.+?)"')
    HEADERS = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain", "User-Agent": "Mozilla/5.0"}

    # Status'
    SUCCESS = 0
    IN_PROGRESS = 1
    FAIL = 2

    # Status Messages
    FAILED_BASIC_INFORMATION_MISSING = 'Missing title, title sort, author, and/or author sort.'
    FAILED_COULD_NOT_FIND_AMAZON_PAGE = 'Could not find amazon page.'
    FAILED_COULD_NOT_FIND_AMAZON_ASIN = 'Could not find asin on amazon page.'
    FAILED_COULD_NOT_FIND_SHELFARI_PAGE = 'Could not find shelfari page.'
    FAILED_COULD_NOT_PARSE_SHELFARI_DATA = 'Could not parse shelfari data.'
    FAILED_UNSUPPORTED_FORMAT = 'Chosen format is unsupported.'
    FAILED_LOCAL_BOOK_NOT_FOUND = 'Local book not found.'
    FAILED_UNABLE_TO_PARSE_BOOK = 'Unable to parse book.'
    FAILED_UNABLE_TO_UPDATE_ASIN = 'Unable to update ASIN in book on device.'
    FAILED_UNABLE_TO_WRITE_XRAY = 'Unable to write x-ray file.'
    FAILED_BOOK_NOT_ON_DEVICE = 'The book is not on the device.'
    FAILED_FAILED_TO_CREATE_XRAY = 'Attempted to create x-ray but failed to do so.'
    FAILED_PREFERENCES_SET_TO_NOT_CREATE_XRAY = 'No local x-ray found. Your preferences are set to not create one if one is not already found when sending to device.'
    FAILED_FAILED_TO_COPY_XRAY = 'Could not copy local x-ray file to device.'
    FAILED_FAILED_TO_SEND_XRAY = 'Could not send x-ray to device.'
    FAILED_NO_CONNECTED_DEVICE = 'No device is connected.'

    # allowed formats
    FMTS = ['mobi', 'azw3']

    def __init__(self, db, book_id, formats, spoilers=False, send_to_device=True, create_xray=True):
        self._db = db
        self._book_id = book_id
        self._formats = formats
        self._spoilers = spoilers
        self._send_to_device = send_to_device
        self._create_xray = create_xray
        self._status = self.IN_PROGRESS
        self._status_message = None
        self._format_specific_info = None

        self._get_basic_information()
        if self.status is self.FAIL:
            return

    @property
    def status(self):
        return self._status

    @property
    def status_message(self):
        return self._status_message
    

    @property
    def title(self):
        return self._title

    @property
    def author(self):
        return self._author
    
    
    @property
    def title_and_author(self):
        return self._title + ' - ' + self._author

    @property
    def format_specific_info(self):
        return self._format_specific_info

    def formats_not_failing(self):
        for info in self._format_specific_info:
            if info['status'] is not self.FAIL:
                yield info

    # get book's title, title sort, author, author sort, and asin if it exists
    def _get_basic_information(self):
        self._title = self._db.field_for('title', self._book_id)
        self._title_sort = self._db.field_for('sort', self._book_id)

        self._author = self._db.field_for('authors', self._book_id)
        if len(self._author) > 0:
            self._author = ' & '.join(self._author)
        self._author_sort = self._db.field_for('author_sort', self._book_id)
        if not self._title or not self._title_sort or not self._author or not self._author_sort:
            self._status = self.FAIL
            self._status_message = self.FAILED_BASIC_INFORMATION_MISSING
            raise Exception(self._status_message)

        identifiers = self._db.field_for('identifiers', self._book_id)
        self._asin = self._db.field_for('identifiers', self._book_id)['mobi-asin'].decode('ascii') if 'mobi-asin' in identifiers.keys() else None

        # if all basic information is available, sanitize information
        if self._author_sort[-1] == '.': self._author_sort = self._author_sort[:-1] + '_'
        self._author_sort = self._author_sort.replace(':', '_').replace('\"', '_')

        trailing_period = False
        while self._title_sort[-1] == '.':
            self._title_sort = self._title_sort[:-1]
            trailing_period = True
        if trailing_period:
            self._title_sort += '_'
        self._title_sort = self._title_sort.replace(':', '_').replace('\"', '_')

        trailing_period = False
        self._author_in_filename = self._author
        while self._author_in_filename[-1] == '.':
            self._author_in_filename = self._author_in_filename[:-1]
            trailing_period = True
        if trailing_period:
            self._author_in_filename += '_'
        self._author_in_filename = self._author_in_filename.replace(':', '_').replace('\"', '_')

    def _get_asin(self, connection):
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
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_FIND_AMAZON_PAGE
            raise Exception(self._status_message)

        soup = BeautifulSoup(response)
        results = soup.findAll('div', {'id': 'resultsCol'})
       
        if not results or len(results) == 0:
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_FIND_AMAZON_PAGE
            raise Exception(self._status_message)

        for r in results:
            if 'Buy now with 1-Click' in str(r):
                asinSearch = self.AMAZON_ASIN_PAT.search(str(r))
                if asinSearch:
                    self._asin = asinSearch.group(1)
                    mi = self._db.get_metadata(self._book_id)
                    identifiers = mi.get_identifiers()
                    identifiers['mobi-asin'] = self._asin
                    mi.set_identifiers(identifiers)
                    self._db.set_metadata(self._book_id, mi)
                    return connection

        self._status = self.FAIL
        self._status_message = self.FAILED_COULD_NOT_FIND_AMAZON_ASIN
        raise Exception(self._status_message)

    def _get_shelfari_url(self, connection):
        self._shelfari_url = None
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
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_FIND_SHELFARI_PAGE
            raise Exception(self._status_message)
        urlsearch = self.SHELFARI_URL_PAT.search(response)
        if not urlsearch:
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_FIND_SHELFARI_PAGE
            raise Exception(self._status_message)
        self._shelfari_url = urlsearch.group(1)
        return connection

    def _parse_shelfari_data(self):
        try:
            self._parsed_shelfari_data = ShelfariParser(self._shelfari_url, spoilers=self._spoilers)
            self._parsed_shelfari_data.parse()
        except Exception:
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_PARSE_SHELFARI_DATA
            raise Exception(self._status_message)

    def _get_format_specific_information(self):
        self._format_specific_info = []

        for fmt in self._formats:
            info = {'format': fmt}
            
            # check to make sure format is supported
            if fmt.lower() not in self.FMTS:
                info['status'] = self.FAIL
                info['status_message'] = self.FAILED_UNSUPPORTED_FORMAT
                continue

            # find local book if it exists; fail if it doesn't
            local_book = self._db.format_abspath(self._book_id, fmt.upper())
            if not local_book or not os.path.exists(local_book):
                info['status'] = self.FAIL
                info['status_message'] = self.FAILED_LOCAL_BOOK_NOT_FOUND
                continue

            info['local_book'] = local_book
            info['local_xray'] = os.path.join('.'.join(local_book.split('.')[:-1]) + '.sdr', fmt.lower())
            info['device_book'] = os.path.join('documents', self._author_sort, self._title_sort + ' - ' + self._author_in_filename + '.' + fmt.lower())
            info['device_xray'] = '.'.join(info['device_book'].split('.')[:-1]) + '.sdr'
            info['status'] = self.IN_PROGRESS
            info['status_message'] = None
            self._format_specific_info.append(info)

    def _parse_book(self):
        for info  in self.formats_not_failing():
            try:
                info['parsed_book_data'] = BookParser(info['format'], info['local_book'], self._parsed_shelfari_data)
                info['parsed_book_data'].parse()
            except:
                info['status'] = self.FAIL
                info['status_message'] = self.FAILED_UNABLE_TO_PARSE_BOOK

    def _write_xray(self, remove_files_from_dir=True):
        for info  in self.formats_not_failing():
            try:
                # make sure local xray directory exists; create it if it doesn't
                if not os.path.exists(info['local_xray']):
                    if not os.path.exists(os.path.dirname(info['local_xray'])):
                        os.mkdir(os.path.dirname(info['local_xray']))
                    os.mkdir(info['local_xray'])
                    
                if remove_files_from_dir:
                    for file in glob(os.path.join(info['local_xray'], '*.asc')):
                        os.remove(file)

                xray_db_writer = XRayDBWriter(info['local_xray'], self._asin, self._shelfari_url, info['parsed_book_data'])
                xray_db_writer.create_xray()
                info['status'] = self.SUCCESS
                info['status_message'] = None
            except:
                info['status'] = self.FAIL
                info['status_message'] = self.FAILED_UNABLE_TO_WRITE_XRAY

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

    def create_xray(self, aConnection, sConnection, log=None, abort=None, remove_files_from_dir=False):
        if abort and abort.isSet():
            return
        if log: log('%s \t\t\tGetting ASIN...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        if not self._asin or len(self._asin) != 10:
            aConnection = self._get_asin(aConnection)

        if abort and abort.isSet():
            return
        if log: log('%s \t\t\tGetting shelfari url...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        try:
            sConnection = self._get_shelfari_url(sConnection)
        except:
            # try to get our own asin and try again if the one in mobi-asin doesn't work out
            self._status = self.IN_PROGRESS
            self._status_message = None
            aConnection = self._get_asin(aConnection)
            sConnection = self._get_shelfari_url(sConnection)

        if abort and abort.isSet():
            return
        if log: log('%s \t\t\tParsing shelfari data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        self._parse_shelfari_data()
        
        if abort and abort.isSet():
            return
        if log: log('%s \t\t\tParsing book data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        self._parse_book()
        
        if abort and abort.isSet():
            return
        if log: log('%s \t\t\tCreating x-ray...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        self._write_xray(remove_files_from_dir=remove_files_from_dir)
        return (aConnection, sConnection)

    def send_xray(self, overwrite=True, already_created=True, log=None, abort=None, aConnection=None, sConnection=None):
        device_drive = self._find_device()
        for info  in self.formats_not_failing():
            try:
                if not device_drive:
                    info['send_status'] = self.FAIL
                    info['status_message'] = self.FAILED_NO_CONNECTED_DEVICE
                    continue
    
                info['device_book'] = os.path.join(device_drive, os.sep, info['device_book'])
                info['device_xray'] = os.path.join(device_drive, os.sep, info['device_xray'])

                # check to make sure book is on the device
                if not os.path.exists(info['device_book']):
                    info['send_status'] = self.FAIL
                    info['status_message'] = self.FAILED_BOOK_NOT_ON_DEVICE
                    continue

                local_xray = glob(os.path.join(info['local_xray'], '*.asc'))
                if len(local_xray) == 0:
                    if already_created:
                        info['send_status'] = self.FAIL
                        info['status_message'] = self.FAILED_FAILED_TO_CREATE_XRAY
                        continue

                    if not self._create_xray:
                        info['send_status'] = self.FAIL
                        info['status_message'] = self.FAILED_PREFERENCES_SET_TO_NOT_CREATE_XRAY
                        continue

                    try:
                        aConnection, sConnection = self.create_xray(aConnection, sConnection, log=log, abort=abort)
                    except Exception as e:
                        info['send_status'] = self.FAIL
                        info['status_message'] = e
                        continue

                    local_xray = glob(os.path.join(info['local_xray'], '*.asc'))
                    if len(local_xray) == 0:
                        info['send_status'] = self.FAIL
                        info['status_message'] = self.FAILED_FAILED_TO_CREATE_XRAY
                        continue

                # at this point, the book exists on the device and we have a local x-ray file

                device_xray_files = glob(os.path.join(info['device_xray'], '*_' + info['format'].lower() + '*.asc'))
                if len(device_xray_files) > 0:
                    if not overwrite:
                        info['send_status'] = self.SUCCESS
                        info['status_message'] = 'Book already has x-ray.'
                        continue

                    for file in device_xray_files:
                        os.remove(file)

                try:
                    with open(info['device_book'], 'r+b') as stream:
                        mu = ASINUpdater(stream)
                        info['original_asin'], info['asin'] = mu.update(self._asin, info['format'])
                    if info['original_asin'] is not info['asin']:
                        # if we changed the asin, update the image file name
                        for dirName, subDirList, fileList in os.walk(info['device_book'].split(os.sep)[0]):
                            for file in glob(os.path.join(dirName, '*%s*.jpg' % info['original_asin'])):
                                new_name = file.replace(info['original_asin'], info['asin'])
                                os.rename(file, new_name)
                except:
                    info['send_status'] = self.FAIL
                    info['status_message'] = self.FAILED_UNABLE_TO_UPDATE_ASIN
                    continue

                if not os.path.exists(info['device_xray']):
                    os.mkdir(info['device_xray'])

                # copy file to temporary directory and rename to file name with correct asin
                tmp_dir = os.path.join(os.path.dirname(local_xray[0]), 'tmp')
                if os.path.exists(tmp_dir):
                    rmtree(tmp_dir)
                os.mkdir(tmp_dir)
                copy(local_xray[0], tmp_dir)
                original_name = os.path.basename(local_xray[0])
                new_name = 'XRAY.entities.%s.asc' % info['asin']
                if not os.path.exists(os.path.join(tmp_dir, new_name)):
                    os.rename(os.path.join(tmp_dir, original_name), os.path.join(tmp_dir, new_name))

                # copy file to x-ray folder on device and clean up
                copy(os.path.join(tmp_dir, 'XRAY.entities.%s.asc' % info['asin']), info['device_xray'])
                rmtree(tmp_dir)
                info['send_status'] = self.SUCCESS

                # one last check to make sure file is actually on the device
                if not os.path.exists(os.path.join(info['device_xray'], 'XRAY.entities.%s.asc' % info['asin']):
                    info['send_status'] = self.FAIL
                    info['status_message'] = self.FAILED_FAILED_TO_SEND_XRAY
                    continue
            except:
                info['send_status'] = self.FAIL
                info['status_message'] = self.FAILED_FAILED_TO_SEND_XRAY

        return (aConnection, sConnection)

    def create_xray_event(self, aConnection, sConnection, log=None, notifications=None, abort=None, book_num=None, total=None):
        actions = 6.0
        if self._send_to_device:
            actions += 1
        perc = book_num * actions
        try:
            if abort and abort.isSet():
                return
            if not self._asin or len(self._asin) != 10:
                if notifications: notifications.put((perc/(total * actions), 'Getting %s ASIN' % self.title_and_author))
                if log: log('%s \tGetting ASIN...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
                aConnection = self._get_asin(aConnection)
            perc += 1

            if abort and abort.isSet():
                return
            if notifications: notifications.put((perc/(total * actions), 'Getting %s shelfari url' % self.title_and_author))
            if log: log('%s \tGetting shelfari url...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
            perc += 1
            try:
                sConnection = self._get_shelfari_url(sConnection)
            except:
                # try to get our own asin and try again if the one in mobi-asin doesn't work out
                self._status = self.IN_PROGRESS
                self._status_message = None
                aConnection = self._get_asin(aConnection)
                sConnection = self._get_shelfari_url(sConnection)

            if abort and abort.isSet():
                return
            if notifications: notifications.put((perc/(total * actions), 'Parsing %s shelfari data' % self.title_and_author))
            if log: log('%s \tParsing shelfari data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
            perc += 1
            self._parse_shelfari_data()

            if abort and abort.isSet():
                return
            if notifications: notifications.put((perc/(total * actions), 'Getting %s format specific data' % self.title_and_author))
            if log: log('%s \tGetting format specific data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
            perc += 1
            self._get_format_specific_information()
            
            if abort and abort.isSet():
                return
            if notifications: notifications.put((perc/(total * actions), 'Parsing %s book data' % self.title_and_author))
            if log: log('%s \tParsing book data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
            perc += 1
            self._parse_book()
            
            if abort and abort.isSet():
                return
            if notifications: notifications.put((perc/(total * actions), 'Creating %s x-ray' % self.title_and_author))
            if log: log('%s \tCreating x-ray...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
            perc += 1
            self._write_xray()
            self._status = self.SUCCESS
            self._status_message = None

            if abort and abort.isSet():
                return
            if self._send_to_device:
                if notifications: notifications.put((perc/(total * actions), 'Sending %s x-ray to device' % self.title_and_author))
                if log: log('%s \tSending x-ray to device...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
                perc += 1
                self.send_xray()
            return (aConnection, sConnection)
        except:
            return (aConnection, sConnection)

    def send_xray_event(self, aConnection, sConnection, log=None, notifications=None, abort=None, book_num=None, total=None):
        actions = 2.0
        perc = book_num * actions
        if abort and abort.isSet():
            return
        if notifications: notifications.put((perc/(total * actions), 'Getting %s format specific data' % self.title_and_author))
        if log: log('%s \t\tGetting format specific data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        perc += 1
        self._get_format_specific_information()

        if abort and abort.isSet():
            return
        if notifications: notifications.put((perc/(total * actions), 'Sending %s x-ray to device' % self.title_and_author))
        if log: log('%s \t\tSending x-ray to device...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        return self.send_xray(overwrite=False, already_created=False, log=log, abort=abort, aConnection=aConnection, sConnection=sConnection)

class ASINUpdater(MetadataUpdater):
    def update(self, asin, fmt):
        def update_exth_record(rec):
            recs.append(rec)
            if rec[0] in self.original_exth_records:
                self.original_exth_records.pop(rec[0])

        if self.type != "BOOKMOBI":
                raise MobiError("Setting ASIN only supported for MOBI files of type 'BOOK'.\n"
                                "\tThis is a '%s' file of type '%s'" % (self.type[0:4], self.type[4:8]))

        recs = []
        original = None
        if 113 in self.original_exth_records:
            asin = self.original_exth_records[113]
            original = asin
        elif 504 in self.original_exth_records:
            asin = self.original_exth_records[504]
            original = asin

        if '_' in asin:
            asin = '_'.join(asin.split('_')[:-1])
        asin += '_' + fmt.lower()

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

        return (original, asin)