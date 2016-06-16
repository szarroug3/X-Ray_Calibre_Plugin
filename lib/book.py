# Book.py

import os
import sys
import re
import struct
import ctypes
import subprocess
from glob import glob
from shutil import copy, rmtree
from urllib import urlencode
from datetime import datetime
from cStringIO import StringIO
from httplib import HTTPSConnection

from calibre.utils.config import JSONConfig
from calibre.library import current_library_path

from calibre.ebooks.mobi import MobiError
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.metadata.mobi import MetadataUpdater
from calibre.ebooks.metadata.meta import get_metadata, set_metadata

from calibre_plugins.xray_creator.lib.book_parser import BookParser
from calibre_plugins.xray_creator.lib.book_settings import BookSettings
from calibre_plugins.xray_creator.lib.xray_db_writer import XRayDBWriter
from calibre_plugins.xray_creator.lib.goodreads_parser import GoodreadsParser


# Drive types - mirror's what Window's GetDriveType() API returns, for convenience
DRIVE_REMOVABLE   = 2
DRIVE_FIXED       = 3

books_updated = []
books_skipped = []

class Book(object):
    AMAZON_ASIN_PAT = re.compile(r'data\-asin=\"([a-zA-z0-9]+)\"')
    HEADERS = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/html", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0"}
    LIBRARY = current_library_path()

    # Status'
    SUCCESS = 0
    IN_PROGRESS = 1
    FAIL = 2

    # Status Messages
    FAILED_BASIC_INFORMATION_MISSING = 'Missing title, title sort, author, and/or author sort.'
    FAILED_COULD_NOT_CONNECT_TO_AMAZON = 'Had a problem connecting to Amazon.'
    FAILED_COULD_NOT_CONNECT_TO_GOODREADS = 'Had a problem connecting to Goodreads.'
    FAILED_COULD_NOT_FIND_AMAZON_PAGE = 'Could not find amazon page.'
    FAILED_COULD_NOT_FIND_AMAZON_ASIN = 'Could not find asin on Amazon page.'
    FAILED_COULD_NOT_FIND_GOODREADS_PAGE = 'Could not find Goodreads page.'
    FAILED_COULD_NOT_PARSE_GOODREADS_DATA = 'Could not parse Goodreads data.'
    FAILED_UNSUPPORTED_FORMAT = 'Chosen format is unsupported.'
    FAILED_LOCAL_BOOK_NOT_FOUND = 'Local book not found.'
    FAILED_UNABLE_TO_PARSE_BOOK = 'Unable to parse book.'
    FAILED_UNABLE_TO_UPDATE_ASIN = 'Unable to update ASIN in book on device.'
    FAILED_UNABLE_TO_WRITE_XRAY = 'Unable to write x-ray file.'
    FAILED_BOOK_NOT_ON_DEVICE = 'The book is not on the device.'
    FAILED_FAILED_TO_CREATE_XRAY = 'Attempted to create x-ray but failed to do so.'
    FAILED_PREFERENCES_SET_TO_NOT_CREATE_XRAY = 'No local x-ray found. Your preferences are set to not create one if one is not already found when sending to device.'
    FAILED_FAILED_TO_SEND_XRAY = 'Could not send x-ray to device.'
    FAILED_NO_CONNECTED_DEVICE = 'No device is connected.'

    # allowed formats
    FMTS = ['mobi', 'azw3']

    def __init__(self, db, book_id, aConnection, gConnection, formats=None, send_to_device=True, create_xray=True, proxy=False, https_address=None, https_port=None):
        self._db = db
        self._book_id = book_id
        self._formats = formats
        self._send_to_device = send_to_device
        self._create_xray = create_xray
        self._status = self.IN_PROGRESS
        self._status_message = None
        self._format_specific_info = None
        self._proxy = proxy
        self._https_address = https_address
        self._https_port = https_port

        book_path = self._db.field_for('path', book_id).replace('/', os.sep)
        self._book_settings = BookSettings(self._db, self._book_id, aConnection, gConnection)

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
    def asin(self):
        return self._asin
    
    @property
    def goodreads_url(self):
        return self._goodreads_url

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
        if self._title is 'Unknown' or self._title_sort is 'Unknown' or not self._author or not self._author_sort:
            self._status = self.FAIL
            self._status_message = self.FAILED_BASIC_INFORMATION_MISSING
            return

        self._asin = self._book_settings.prefs['asin'] if self._book_settings.prefs['asin'] != '' else None
        if not self._asin:
            identifiers = self._db.field_for('identifiers', self._book_id)
            self._asin = self._db.field_for('identifiers', self._book_id)['mobi-asin'].decode('ascii') if 'mobi-asin' in identifiers.keys() else None
            if self._asin:
                self._book_settings.prefs['asin'] = self._asin

        self._goodreads_url = self._book_settings.prefs['goodreads_url'] if self._book_settings.prefs['goodreads_url'] != '' else None
        self._aliases = self._book_settings.prefs['aliases']

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

    def get_asin(self, connection):
        query = urlencode({'keywords': '%s - %s' % (self._title, self._author)})
        try:
            connection.request('GET', '/s/ref=sr_qz_back?sf=qz&rh=i%3Adigital-text%2Cn%3A154606011%2Ck%3A' + query[9:] + '&' + query, headers=self.HEADERS)
            response = connection.getresponse().read()
        except Exception as e:
            try:
                connection.close()
                if self._proxy:
                    connection = HTTPSConnection(self._https_address, self._https_port)
                    connection.set_tunnel('www.amazon.com', 443)
                else:
                    connection = HTTPSConnection('www.amazon.com')

                connection.request('GET', '/s/ref=sr_qz_back?sf=qz&rh=i%3Adigital-text%2Cn%3A154606011%2Ck%3A' + query[9:] + '&' + query, headers=self.HEADERS)
                response = connection.getresponse().read()
            except:
                self._status = self.FAIL
                self._status_message = self.FAILED_COULD_NOT_CONNECT_TO_AMAZON
                raise Exception(self._status_message)

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
                    self._book_settings.prefs['asin'] = self._asin
                    return connection

        self._status = self.FAIL
        self._status_message = self.FAILED_COULD_NOT_FIND_AMAZON_ASIN
        raise Exception(self._status_message)

    def get_goodreads_url(self, connection):
        self._goodreads_url = None
        connection = self._search_goodreads(connection, self._asin)
        if not self._goodreads_url:
            connection = self._search_goodreads(connection, self.title_and_author)
            if not self._goodreads_url:
                self._status = self.FAIL
                self._status_message = self.FAILED_COULD_NOT_FIND_GOODREADS_PAGE
                raise Exception(self._status_message)

        self._book_settings.prefs['goodreads_url'] = self._goodreads_url
        return connection

    def _search_goodreads(self, connection, keywords):
        query = urlencode ({'Keywords': keywords})
        try:
            connection.request('GET', '/search/books?' + query)
            response = connection.getresponse().read()
        except:
            try:
                connection.close()
                if self._proxy:
                    connection = HTTPSConnection(self._https_address, self._https_port)
                    connection.set_tunnel('www.goodreads.com', 443)
                else:
                    connection = HTTPSConnection('www.goodreads.com')

                connection.request('GET', '/search/books?' + query)
                response = connection.getresponse().read()
            except:
                self._status = self.FAIL
                self._status_message = self.FAILED_COULD_NOT_CONNECT_TO_GOODREADS
                raise Exception(self._status_message)
        
        # check to make sure there are results
        if 'did not return any results' in response:
            return connection
        urlsearch = self.GOODREADS_URL_PAT.search(response)
        if not urlsearch:
            return connection

        self._goodreads_url = urlsearch.group(1)
        return connection

    def _parse_goodreads_data(self):
        try:
            self._parsed_goodreads_data = GoodreadsParser(self._goodreads_url)
            self._parsed_goodreads_data.parse()

            for char in self._parsed_goodreads_data.characters.values():
                if char['label'] not in self._aliases.keys():
                    self._aliases[char['label']] = []

            self._book_settings.prefs['aliases'] = self._aliases
        except:
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_PARSE_GOODREADS_DATA
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

    def _parse_book(self, info=None):
        def _parse(info):
            try:
                info['parsed_book_data'] = BookParser(info['format'], info['local_book'], self._parsed_goodreads_data, self._aliases)
                info['parsed_book_data'].parse()
            except:
                info['status'] = self.FAIL
                info['status_message'] = self.FAILED_UNABLE_TO_PARSE_BOOK

        if not info:
            for info in self.formats_not_failing():
                _parse(info)
            return

        _parse(info)
        if info['status'] is self.FAIL:
            raise Exception(info['status_message'])

    def _write_xray(self, info=None, remove_files_from_dir=True):
        def _write(info, remove_files):
            try:
                # make sure local xray directory exists; create it if it doesn't
                if not os.path.exists(info['local_xray']):
                    if not os.path.exists(os.path.dirname(info['local_xray'])):
                        os.mkdir(os.path.dirname(info['local_xray']))
                    os.mkdir(info['local_xray'])
                    
                if remove_files_from_dir:
                    for file in glob(os.path.join(info['local_xray'], '*.asc')):
                        os.remove(file)

                xray_db_writer = XRayDBWriter(info['local_xray'], self._asin, self._goodreads_url, info['parsed_book_data'])
                xray_db_writer.create_xray()
                info['status'] = self.SUCCESS
                info['status_message'] = None
            except:
                info['status'] = self.FAIL
                info['status_message'] = self.FAILED_UNABLE_TO_WRITE_XRAY

        if not info:
            for info in self.formats_not_failing():
                _write(info, remove_files_from_dir)
            return
        _write(info, remove_files_from_dir)
        if info['status'] is self.FAIL:
            raise Exception(info['status_message'])

    def _find_device(self):
        """
        Look for the Kindle and return the device drive (for Windows) or mount point (for OS X/Linux)
        """
        drive_info = self._get_drive_info()
        removable_drives = [drive_letter for drive_letter, drive_type in drive_info if drive_type == DRIVE_REMOVABLE]
        for drive in removable_drives:
            magic_file = os.path.join(drive, "system", "version.txt")
            if os.path.exists(magic_file):
                if open(magic_file).readline().startswith("Kindle"):
                    return drive
        return None

    # Return list of tuples mapping drive letters to drive types
    def _get_drive_info(self):
        """
        Return a list of tuples, each tuple containing drive letter/path and drive type
        
        eg. ("C:", DRIVE_FIXED) or ("/Volumes/Kindle", DRIVE_REMOVABLE)
        """
        result = []
        if sys.platform == "win32":    
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                bit = 2 ** i
                if bit & bitmask:
                    drive_letter = '%s:' % chr(65 + i)
                    drive_type = ctypes.windll.kernel32.GetDriveTypeA('%s\\' % drive_letter)
                    result.append((drive_letter, drive_type))
        elif sys.platform == "darwin" or "linux" in sys.platform:
            # mount output shows us what is attached
            # Ignore anything that isn't a device, which will start with slash (eg. /dev/disk1)
            # Only interested in device name and mountpoint
            stdout, stderr = subprocess.Popen("mount", stdout=subprocess.PIPE).communicate()            
            for mount_entry in [x.split() for x in stdout.split('\n') if x.startswith("/")]:
                device = mount_entry[0]
                mountpoint = mount_entry[2]
                if mountpoint == "/":
                    result.append((mountpoint, DRIVE_FIXED))
                else:
                    # This is a slight lie - non-Windows systems don't have such an obvious
                    # split between fixed + removeable, so with the exception of the root device
                    # (which I'm pretty certain isn't a Kindle!), claim everything is removable
                    result.append((mountpoint, DRIVE_REMOVABLE))
        else:
            import errno
            raise EnvironmentError(errno.EINVAL, "Unknown platform %s" % (sys.platform))
            
        return result

    def create_xray(self, aConnection, gConnection, info, log=None, abort=None, remove_files_from_dir=False):
        if abort and abort.isSet():
            return
        if not self._asin or len(self._asin) != 10:
            if log: log('%s \t\tGetting ASIN...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
            aConnection = self.get_asin(aConnection)

        if abort and abort.isSet():
            return
        if not self._goodreads_url:
            if log: log('%s \t\tGetting Goodreads url...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
            try:
                gConnection = self.get_goodreads_url(gConnection)
            except:
                # try to get our own asin and try again if the one in mobi-asin doesn't work out
                self._status = self.IN_PROGRESS
                self._status_message = None
                aConnection = self.get_asin(aConnection)
                gConnection = self.get_goodreads_url(gConnection)

        if abort and abort.isSet():
            return
        if log: log('%s \t\tParsing Goodreads data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        self._parse_goodreads_data()
        
        if abort and abort.isSet():
            return
        if log: log('%s \t\tParsing book data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        self._parse_book(info=info)
        
        if abort and abort.isSet():
            return
        if log: log('%s \t\tCreating x-ray...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        self._write_xray(info, remove_files_from_dir=remove_files_from_dir)
        return (aConnection, gConnection)

    def send_xray(self, overwrite=True, already_created=True, log=None, abort=None, aConnection=None, gConnection=None):
        device = self._find_device()
        for info in self.formats_not_failing():
            try:
                if not device:
                    info['send_status'] = self.FAIL
                    info['status_message'] = self.FAILED_NO_CONNECTED_DEVICE
                    continue

                info['device_book'] = os.path.join(device, info['device_book'])
                info['device_xray'] = os.path.join(device, info['device_xray'])

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
                        aConnection, gConnection = self.create_xray(aConnection, gConnection, info=info, log=log, abort=abort)
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
                        
                    if info['original_asin'] != info['asin']:
                        # if we changed the asin, update the image file name
                        thumbname_orig = os.path.join(device, "system", "thumbnails", "thumbnail_%s_EBOK_portrait.jpg" % (info['original_asin']))
                        thumbname_new = thumbname_orig.replace(info['original_asin'], info['asin'])
                        os.rename(thumbname_orig, thumbname_new)
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
                if not os.path.exists(os.path.join(info['device_xray'], 'XRAY.entities.%s.asc' % info['asin'])):
                    info['send_status'] = self.FAIL
                    info['status_message'] = self.FAILED_FAILED_TO_SEND_XRAY
                    continue
            except:
                info['send_status'] = self.FAIL
                info['status_message'] = self.FAILED_FAILED_TO_SEND_XRAY

        return (aConnection, gConnection)

    def create_xray_event(self, aConnection, gConnection, log=None, notifications=None, abort=None, book_num=None, total=None):
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
                aConnection = self.get_asin(aConnection)
            perc += 1

            if abort and abort.isSet():
                return
            try:
                if not self._goodreads_url:
                    if notifications: notifications.put((perc/(total * actions), 'Getting %s Goodreads url' % self.title_and_author))
                    if log: log('%s \tGetting Goodreads url...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
                    gConnection = self.get_goodreads_url(gConnection)
            except:
                # try to get our own asin and try again if the one in mobi-asin doesn't work out
                self._status = self.IN_PROGRESS
                self._status_message = None
                aConnection = self.get_asin(aConnection)
                gConnection = self.get_goodreads_url(gConnection)
            perc += 1

            if abort and abort.isSet():
                return
            if notifications: notifications.put((perc/(total * actions), 'Parsing %s Goodreads data' % self.title_and_author))
            if log: log('%s \tParsing Goodreads data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
            perc += 1
            self._parse_goodreads_data()

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
            return (aConnection, gConnection)
        except:
            return (aConnection, gConnection)

    def send_xray_event(self, aConnection, gConnection, log=None, notifications=None, abort=None, book_num=None, total=None):
        actions = 2.0
        perc = book_num * actions
        if abort and abort.isSet():
            return
        if notifications: notifications.put((perc/(total * actions), 'Getting %s format specific data' % self.title_and_author))
        if log: log('%s \tGetting format specific data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        perc += 1
        self._get_format_specific_information()

        if abort and abort.isSet():
            return
        if notifications: notifications.put((perc/(total * actions), 'Sending %s x-ray to device' % self.title_and_author))
        if log: log('%s \tSending x-ray to device...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        return self.send_xray(overwrite=False, already_created=False, log=log, abort=abort, aConnection=aConnection, gConnection=gConnection)

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