# Book.py

import os
import re
import json
import struct
from glob import glob
from urllib import urlencode
from datetime import datetime
from cStringIO import StringIO
from shutil import copy, rmtree

from calibre.ebooks.mobi import MobiError
from calibre.library import current_library_path
from calibre.ebooks.metadata.mobi import MetadataUpdater
from calibre.ebooks.metadata.meta import get_metadata, set_metadata

from calibre_plugins.xray_creator.lib.book_parser import BookParser
from calibre_plugins.xray_creator.lib.book_settings import BookSettings
from calibre_plugins.xray_creator.lib.xray_db_writer import XRayDBWriter
from calibre_plugins.xray_creator.lib.goodreads_parser import GoodreadsParser

books_updated = []
books_skipped = []

class Book(object):
    HEADERS = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/html", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0"}
    LIBRARY = current_library_path()

    # Status'
    SUCCESS = 0
    IN_PROGRESS = 1
    FAIL = 2

    # Status Messages
    FAILED_BASIC_INFORMATION_MISSING = 'Missing title, title sort, author, and/or author sort.'
    FAILED_DUPLICATE_UUID = 'Book has the same uuid as another book.'
    FAILED_COULD_NOT_CONNECT_TO_GOODREADS = 'Had a problem connecting to Goodreads.'
    FAILED_COULD_NOT_FIND_GOODREADS_PAGE = 'Could not find Goodreads page.'
    FAILED_COULD_NOT_PARSE_GOODREADS_DATA = 'Could not parse Goodreads data.'
    FAILED_UNSUPPORTED_FORMAT = 'Chosen format is unsupported.'
    FAILED_LOCAL_BOOK_NOT_FOUND = 'Local book not found.'
    FAILED_UNABLE_TO_PARSE_BOOK = 'Unable to parse book.'
    FAILED_UNABLE_TO_UPDATE_ASIN = 'Unable to update ASIN in book on device.'
    FAILED_CREATE_LOCAL_XRAY_DIR = 'Unable to create local x-ray directory.'
    FAILED_REMOVE_LOCAL_XRAY = 'Unable to remove local x-ray file.'
    FAILED_UNABLE_TO_WRITE_XRAY = 'Unable to write x-ray file.'
    FAILED_BOOK_NOT_ON_DEVICE = 'The book is not on the device.'
    FAILED_FAILED_TO_CREATE_XRAY = 'Attempted to create x-ray but failed to do so.'
    FAILED_PREFERENCES_SET_TO_NOT_CREATE_XRAY = 'No local x-ray found. Your preferences are set to not create one if one is not already found when sending to device.'
    FAILED_FAILED_TO_SEND_XRAY = 'Could not send x-ray to device.'
    FAILED_NO_CONNECTED_DEVICE = 'No device is connected.'

    # allowed formats
    FMTS = ['mobi', 'azw3']

    def __init__(self, db, book_id, goodreads_conn, amazon_conn, formats, send_to_device, create_xray, expand_aliases, send_author_profile):
        self._db = db
        self._book_id = book_id
        self._goodreads_conn = goodreads_conn
        self._formats = formats
        self._send_to_device = send_to_device
        self._create_xray = create_xray
        self._send_author_profile= send_author_profile

        self._status = self.IN_PROGRESS
        self._status_message = None
        self._format_specific_info = None
        self._goodreads_conn = goodreads_conn

        book_path = self._db.field_for('path', book_id).replace('/', os.sep)
        self._book_settings = BookSettings(self._db, self._book_id, self._goodreads_conn, amazon_conn, expand_aliases)

        self._get_basic_information()
    
    @property
    def status(self):
        return self._status

    @property
    def status_message(self):
        return self._status_message
    
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
    def title_and_author(self):
        return self._title + ' - ' + self._author
    
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

    def formats_not_failing_exist(self):
        return any(self.formats_not_failing())

    # get book's title, title sort, author and author sort if it exists
    def _get_basic_information(self):
        self._title = self._db.field_for('title', self._book_id)

        self._author = ' & '.join(self._db.field_for('authors', self._book_id))
        if self._title == 'Unknown' or self._author == 'Unknown':
            self._status = self.FAIL
            self._status_message = self.FAILED_BASIC_INFORMATION_MISSING
            return

        if not self._book_settings.prefs['goodreads_url'] or self._book_settings.prefs['goodreads_url'] == '':
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_FIND_GOODREADS_PAGE
            return

        self._goodreads_url = self._book_settings.prefs['goodreads_url']
        self._aliases = self._book_settings.prefs['aliases']

    def _parse_goodreads_data(self):
        try:
            self._parsed_goodreads_data = GoodreadsParser(self._goodreads_url, self._goodreads_conn, create_author_profile=self._send_author_profile)
            self._parsed_goodreads_data.parse()
            if self._send_author_profile:
                self._book_settings.author_profile = self._parsed_goodreads_data.author_profile

            for char in self._parsed_goodreads_data.characters.values():
                if char['label'] not in self._aliases.keys():
                    self._aliases[char['label']] = char['aliases']

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
                self._format_specific_info.append(info)
                continue

            info['local_book'] = local_book
            info['local_xray'] = os.path.join('.'.join(local_book.split('.')[:-1]) + '.sdr', fmt.lower())
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
            except:
                info['status'] = self.FAIL
                info['status_message'] = self.FAILED_CREATE_LOCAL_XRAY_DIR

            try:
                if remove_files_from_dir:
                    for file in glob(os.path.join(info['local_xray'], '*.asc')):
                        os.remove(file)
            except:
                info['status'] = self.FAIL
                info['status_message'] = self.FAILED_REMOVE_LOCAL_XRAY

            try:
                xray_db_writer = XRayDBWriter(info['local_xray'], self._goodreads_url, info['parsed_book_data'])
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

    def create_xray(self, info, log=None, abort=None, remove_files_from_dir=False):
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

    def send_xray(self, device_books, overwrite=True, already_created=True, log=None, abort=None):
        send_author_profile = self._send_author_profile
        created_author_profile = already_created
        for info in self.formats_not_failing():
            send_xray = True
            try:
                if device_books is None:
                    info['send_status'] = self.FAIL
                    info['status_message'] = self.FAILED_NO_CONNECTED_DEVICE
                    continue

                # check to make sure book is on the device
                elif not device_books.has_key('%s_%s' % (self.book_id, info['format'].lower())):
                    info['send_status'] = self.FAIL
                    info['status_message'] = self.FAILED_BOOK_NOT_ON_DEVICE
                    send_xray = False
                    continue

                device_book = device_books['%s_%s' % (self.book_id, info['format'].lower())]
                info['device_book'] = device_book['device_book']
                info['device_xray'] = device_book['device_xray']
                device_root = device_book['device_root']

                local_xray = os.path.join(info['local_xray'], 'XRAY.asc')
                if not os.path.exists(local_xray):
                    if already_created:
                        info['send_status'] = self.FAIL
                        info['status_message'] = self.FAILED_FAILED_TO_CREATE_XRAY
                        send_xray = False

                    elif not self._create_xray:
                        info['send_status'] = self.FAIL
                        info['status_message'] = self.FAILED_PREFERENCES_SET_TO_NOT_CREATE_XRAY
                        send_xray = False
                    else:
                        try:
                            self.create_xray(info=info, log=log, abort=abort)
                        except Exception as e:
                            info['send_status'] = self.FAIL
                            info['status_message'] = e
                            send_xray = False

                        if not os.path.exists(local_xray):
                            info['send_status'] = self.FAIL
                            info['status_message'] = self.FAILED_FAILED_TO_CREATE_XRAY
                            send_xray = False

                if not send_xray and not send_author_profile:
                    continue 

                if send_author_profile and not self._book_settings.author_profile:
                    if created_author_profile:
                        send_author_profile = False
                    else:
                        try:
                            goodreads_parser = GoodreadsParser(self._goodreads_url, self._goodreads_conn, send_author_profile=self._send_author_profile)
                            goodreads_parser.get_author_profile()
                            created_author_profile = True
                            if not goodreads_parser.author_profile:
                                send_author_profile = False
                                if log: log('%s \t\tWarning: Failed to create author profile.' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))

                            self._book_settings.author_profile = goodreads_parser.author_profile
                        except:
                            send_author_profile = False
                            if log: log('%s \t\tWarning: Failed to create author profile.' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))

                if not send_xray and not send_author_profile:
                    continue 

                device_xray_files = glob(os.path.join(info['device_xray'], 'XRAY.entities.*_' + info['format'].lower() + '*.asc'))
                device_author_profile_files = glob(os.path.join(info['device_xray'], 'AuthorProfile.profile.*_' + info['format'].lower() + '*.asc'))
                if not overwrite:
                    if len(device_xray_files) > 0:
                        info['send_status'] = self.SUCCESS
                        info['status_message'] = 'Book already has x-ray.'
                        send_xray = False

                    if send_author_profile and len(device_author_profile_files) > 0:
                        send_author_profile = False

                    if not send_xray and not send_author_profile:
                        continue

                else:
                    if send_xray:
                        for file in device_xray_files:
                            os.remove(file)
                    if send_author_profile:
                        for file in device_author_profile_files:
                            os.remove(file)

                try:
                    with open(info['device_book'], 'r+b') as stream:
                        mu = ASINUpdater(stream)
                        original_asin, new_asin = mu.update(info['format'])
                        
                    if original_asin and original_asin != new_asin:
                        # if we changed the asin, update the image file name
                        thumbname_orig = os.path.join(device_root, "system", "thumbnails", "thumbnail_%s_EBOK_portrait.jpg" % original_asin)
                        thumbname_new = thumbname_orig.replace(original_asin, new_asin)

                        # check to make sure file exists before trying to modify it
                        if os.path.exists(thumbname_orig):
                            os.rename(thumbname_orig, thumbname_new)
                except:
                    info['send_status'] = self.FAIL
                    info['status_message'] = self.FAILED_UNABLE_TO_UPDATE_ASIN
                    continue

                if not os.path.exists(info['device_xray']):
                    os.mkdir(info['device_xray'])

                # copy file to temporary directory and rename to file name with correct asin
                tmp_dir = os.path.join(os.path.dirname(local_xray), 'tmp')
                if os.path.exists(tmp_dir):
                    rmtree(tmp_dir)
                os.mkdir(tmp_dir)
                if send_xray:
                    copy(local_xray, tmp_dir)
                    original_name = os.path.basename(local_xray)
                    new_name = 'XRAY.entities.%s.asc' % new_asin
                    if not os.path.exists(os.path.join(tmp_dir, new_name)):
                        os.rename(os.path.join(tmp_dir, original_name), os.path.join(tmp_dir, new_name))

                    # copy file to x-ray folder on device and clean up
                    copy(os.path.join(tmp_dir, new_name), info['device_xray'])
                    rmtree(tmp_dir)
                    info['send_status'] = self.SUCCESS

                    # one last check to make sure file is actually on the device
                    if not os.path.exists(os.path.join(info['device_xray'], 'XRAY.entities.%s.asc' % new_asin)):
                        info['send_status'] = self.FAIL
                        info['status_message'] = self.FAILED_FAILED_TO_SEND_XRAY

                if send_author_profile:
                    author_profile = self._book_settings.author_profile
                    author_profile['a'] = new_asin
                    json.dump(author_profile, open(os.path.join(info['device_xray'], 'AuthorProfile.profile.%s.asc' % new_asin), 'w+'))
            except:
                info['send_status'] = self.FAIL
                info['status_message'] = self.FAILED_FAILED_TO_SEND_XRAY

    def create_xray_event(self, device_books, log=None, notifications=None, abort=None, book_num=None, total=None):
        actions = 4.0
        if self._send_to_device:
            actions += 1
        perc = book_num * actions
        try:
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
            
            if abort and abort.isSet() or not self.formats_not_failing_exist():
                return
            if notifications: notifications.put((perc/(total * actions), 'Parsing %s book data' % self.title_and_author))
            if log: log('%s \tParsing book data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
            perc += 1
            self._parse_book()
            
            if abort and abort.isSet() or not self.formats_not_failing_exist():
                return
            if notifications: notifications.put((perc/(total * actions), 'Creating %s x-ray' % self.title_and_author))
            if log: log('%s \tCreating x-ray...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
            perc += 1
            self._write_xray()
            self._status = self.SUCCESS
            self._status_message = None

            if abort and abort.isSet() or not self.formats_not_failing_exist():
                return
            if self._send_to_device:
                if notifications: notifications.put((perc/(total * actions), 'Sending %s x-ray to device' % self.title_and_author))
                if log: log('%s \tSending x-ray to device...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
                perc += 1
                self.send_xray(device_books)
        except:
            return

    def send_xray_event(self, device_books, log=None, notifications=None, abort=None, book_num=None, total=None):
        actions = 2.0
        perc = book_num * actions
        if abort and abort.isSet():
            return
        if notifications: notifications.put((perc/(total * actions), 'Getting %s format specific data' % self.title_and_author))
        if log: log('%s \tGetting format specific data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        perc += 1
        self._get_format_specific_information()

        if abort and abort.isSet() or not self.formats_not_failing_exist():
                return
        if notifications: notifications.put((perc/(total * actions), 'Sending %s x-ray to device' % self.title_and_author))
        if log: log('%s \tSending x-ray to device...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        self.send_xray(device_books, overwrite=False, already_created=False, log=log, abort=abort)

class ASINUpdater(MetadataUpdater):
    def update(self, fmt):
        def update_exth_record(rec):
            recs.append(rec)
            if rec[0] in self.original_exth_records:
                self.original_exth_records.pop(rec[0])

        if self.type != "BOOKMOBI":
                raise MobiError("Setting ASIN only supported for MOBI files of type 'BOOK'.\n"
                                "\tThis is a '%s' file of type '%s'" % (self.type[0:4], self.type[4:8]))

        recs = []
        original = None
        asin = ''
        if 113 in self.original_exth_records:
            asin = self.original_exth_records[113]
            original = asin
        elif 504 in self.original_exth_records:
            asin = self.original_exth_records[504]
            original = asin

        if '_' in asin:
            asin = '_'.join(asin.split('_')[:-1])
        asin += '_' + fmt.lower()

        if original == asin:
            return (original, asin)

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
