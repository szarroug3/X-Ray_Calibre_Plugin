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
    WARNING = 3

    # Status Messages
    FAILED_BASIC_INFORMATION_MISSING = 'Missing title, title sort, author, and/or author sort.'
    FAILED_DUPLICATE_UUID = 'Book has the same uuid as another book.'
    FAILED_COULD_NOT_CONNECT_TO_GOODREADS = 'Had a problem connecting to Goodreads.'
    FAILED_COULD_NOT_FIND_GOODREADS_PAGE = 'Could not find Goodreads page.'
    FAILED_COULD_NOT_PARSE_GOODREADS_DATA = 'Could not parse Goodreads data.'
    FAILED_COULD_NOT_FIND_ASIN = 'Could not find ASIN.'
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

    def __init__(self, db, book_id, goodreads_conn, amazon_conn, formats, send_to_device, create_xray_when_sending, expand_aliases,
        create_send_xray, create_send_author_profile, create_send_start_actions, create_send_end_actions):
        self._db = db
        self._book_id = book_id
        self._goodreads_conn = goodreads_conn
        self._formats = formats
        self._send_to_device = send_to_device
        self._create_xray_when_sending = create_xray_when_sending
        self._create_send_xray = create_send_xray
        self._create_send_author_profile = create_send_author_profile
        self._create_send_start_actions = create_send_start_actions
        self._create_send_end_actions = create_send_end_actions

        self._status = self.IN_PROGRESS
        self._status_message = None
        self._local_non_xray = None
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

        if not self._book_settings.prefs['asin']:
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_FIND_ASIN
            return

        self._goodreads_url = self._book_settings.prefs['goodreads_url']
        self._asin = self._book_settings.prefs['asin']
        self._aliases = self._book_settings.prefs['aliases']

    def _parse_goodreads_data(self):
        try:
            self._parsed_goodreads_data = GoodreadsParser(self._goodreads_url, self._goodreads_conn, self._asin,
                create_xray=self._create_send_xray, create_author_profile=self._create_send_author_profile,
                create_start_actions=self._create_send_start_actions, create_end_actions=self._create_send_end_actions)
            self._parsed_goodreads_data.parse()
            if self._create_send_author_profile:
                self._book_settings.author_profile = self._parsed_goodreads_data.author_profile
            if self._create_send_start_actions:
                self._book_settings.start_actions = self._parsed_goodreads_data.start_actions
            if self._create_send_end_actions:
                self._book_settings.end_actions = self._parsed_goodreads_data.end_actions

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
            if not self._local_non_xray:
                self._local_non_xray = '.'.join(local_book.split('.')[:-1]) + '.sdr'
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

    def _write_xray(self, info=None, remove_files_from_dir=True, log=None):
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
                    for file in glob(os.path.join(info['local_xray'], 'XRAY.entities.*.asc')):
                        os.remove(file)
            except:
                if log: log('%s \t\tWarning: Failed to remove old x-ray.' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
                return

            try:
                xray_db_writer = XRayDBWriter(info['local_xray'], self._goodreads_url, self._asin, info['parsed_book_data'])
                xray_db_writer.create_xray()
            except:
                if log: log('%s \t\tWarning: Failed to create x-ray.' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
                return

        if not info:
            for info in self.formats_not_failing():
                _write(info, remove_files_from_dir)
            return
        _write(info, remove_files_from_dir)
        if info['status'] is self.FAIL:
            raise Exception(info['status_message'])

    def create_files(self, info, log=None, abort=None, remove_files_from_dir=False):
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

    def send_files(self, device_books, overwrite=True, already_created=True, log=None, abort=None):
        create_send_xray = self._create_send_xray
        create_send_author_profile = self._create_send_author_profile
        create_send_start_actions = self._create_send_start_actions
        create_send_end_actions = self._create_send_end_actions
        created_xray = already_created
        created_author_profile = already_created
        created_start_actions = already_created
        created_end_actions = already_created
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

                local_xray = os.path.join(info['local_xray'], 'XRAY.entities.{0}.asc'.format(self._asin))
                if not os.path.exists(local_xray):
                    if already_created:
                        info['send_status'] = self.FAIL
                        info['status_message'] = self.FAILED_FAILED_TO_CREATE_XRAY
                        send_xray = False

                    elif not self._create_xray_when_sending:
                        info['send_status'] = self.FAIL
                        info['status_message'] = self.FAILED_PREFERENCES_SET_TO_NOT_CREATE_XRAY
                        send_xray = False
                    else:
                        try:
                            self.create_files(info=info, log=log, abort=abort)
                        except Exception as e:
                            info['send_status'] = self.FAIL
                            info['status_message'] = e
                            send_xray = False

                        if not os.path.exists(local_xray):
                            info['send_status'] = self.FAIL
                            info['status_message'] = self.FAILED_FAILED_TO_CREATE_XRAY
                            send_xray = False

                if not send_xray and not create_send_author_profile and not create_send_start_actions and not create_send_end_actions:
                    continue

                if create_send_author_profile and not self._book_settings.author_profile:
                    if created_author_profile:
                        create_send_author_profile = False
                    else:
                        try:
                            goodreads_parser = GoodreadsParser(self._goodreads_url, self._goodreads_conn, create_send_author_profile=self._create_send_author_profile)
                            goodreads_parser.get_author_profile()
                            created_author_profile = True
                            if not goodreads_parser.author_profile:
                                create_send_author_profile = False
                                self.status = self.WARNING
                                if log: log('%s \t\tWarning: Failed to create author profile.' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))

                            self._book_settings.author_profile = goodreads_parser.author_profile
                        except:
                            create_send_author_profile = False
                            if log: log('%s \t\tWarning: Failed to create author profile.' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))

                if create_send_start_actions and not self._book_settings.start_actions:
                    if created_start_actions:
                        create_send_start_actions = False
                    else:
                        try:
                            goodreads_parser = GoodreadsParser(self._goodreads_url, self._goodreads_conn, create_send_start_actions=self._create_send_start_actions)
                            goodreads_parser.get_start_actions()
                            created_start_actions = True
                            if not goodreads_parser.start_actions:
                                create_send_start_actions = False
                                if log: log('%s \t\tWarning: Failed to create start actions.' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))

                            self._book_settings.start_actions = goodreads_parser.start_actions
                        except:
                            create_send_start_actions = False
                            if log: log('%s \t\tWarning: Failed to create start actions.' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))

                if create_send_end_actions and not self._book_settings.end_actions:
                    if created_end_actions:
                        create_send_end_actions = False
                    else:
                        try:
                            goodreads_parser = GoodreadsParser(self._goodreads_url, self._goodreads_conn, create_send_end_actions=self._create_send_end_actions)
                            goodreads_parser.get_end_actions()
                            created_end_actions = True
                            if not goodreads_parser.end_actions:
                                create_send_end_actions = False
                                if log: log('%s \t\tWarning: Failed to create end actions.' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))

                            self._book_settings.end_actions = goodreads_parser.end_actions
                        except:
                            create_send_end_actions = False
                            if log: log('%s \t\tWarning: Failed to create end actions.' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))

                if not send_xray and not create_send_author_profile and not create_send_end_actions:
                    continue 

                device_xray_files = glob(os.path.join(info['device_xray'], 'XRAY.entities.%s.asc' % self._asin))
                device_author_profile_files = glob(os.path.join(info['device_xray'], 'AuthorProfile.profile.%s.asc' % self._asin))
                device_start_actions_files = glob(os.path.join(info['device_xray'], 'StartActions.data.%s.asc' % self._asin))
                device_end_actions_files = glob(os.path.join(info['device_xray'], 'EndActions.data.%s.asc' % self._asin))
                if not overwrite:
                    if len(device_xray_files) > 0:
                        info['send_status'] = self.SUCCESS
                        info['status_message'] = 'Book already has x-ray.'
                        send_xray = False

                    if create_send_author_profile and len(device_author_profile_files) > 0:
                        create_send_author_profile = False

                    if create_send_start_actions and len(device_start_actions_files) > 0:
                        create_send_start_actions = False

                    if create_send_end_actions and len(device_end_actions_files) > 0:
                        create_send_end_actions = False

                    if not send_xray and not create_send_author_profile and not create_send_start_actions and not create_send_end_actions:
                        continue

                else:
                    if send_xray:
                        for file in device_xray_files:
                            os.remove(file)
                    if create_send_author_profile:
                        for file in device_author_profile_files:
                            os.remove(file)
                    if create_send_start_actions:
                        for file in device_start_actions_files:
                            os.remove(file)
                    if create_send_end_actions:
                        for file in device_end_actions_files:
                            os.remove(file)

                try:
                    with open(info['device_book'], 'r+b') as stream:
                        mu = ASINUpdater(stream)
                        original_asin, new_asin = mu.update(self._asin)
                except:
                    info['send_status'] = self.FAIL
                    info['status_message'] = self.FAILED_UNABLE_TO_UPDATE_ASIN
                    continue

                if not os.path.exists(info['device_xray']):
                    os.mkdir(info['device_xray'])

                # copy files to kindle and clean up
                if send_xray:
                    copy(local_xray, info['device_xray'])
                    info['send_status'] = self.SUCCESS

                    # one last check to make sure file is actually on the device
                    if not os.path.exists(os.path.join(info['device_xray'], 'XRAY.entities.%s.asc' % self._asin)):
                        info['send_status'] = self.FAIL
                        info['status_message'] = self.FAILED_FAILED_TO_SEND_XRAY

                if create_send_author_profile:
                    json.dump(self._book_settings.author_profile, open(os.path.join(info['device_xray'], 'AuthorProfile.profile.%s.asc' % self._asin), 'w+'))

                if create_send_start_actions:
                    json.dump(self._book_settings.start_actions, open(os.path.join(info['device_xray'], 'StartActions.data.%s.asc' % self._asin), 'w+'))

                if create_send_end_actions:
                    json.dump(self._book_settings.end_actions, open(os.path.join(info['device_xray'], 'EndActions.data.%s.asc' % self._asin), 'w+'))
            except:
                info['send_status'] = self.FAIL
                info['status_message'] = self.FAILED_FAILED_TO_SEND_XRAY

    def create_files_event(self, device_books, log=None, notifications=None, abort=None, book_num=None, total=None):
        actions = 2.0
        if self._create_send_xray:
            actions += 2
        if self._create_send_author_profile:
            actions += 1
        if self._create_send_start_actions:
            actions += 1
        if self._create_send_end_actions:
            actions += 1
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
            if self._create_send_xray:
                if notifications: notifications.put((perc/(total * actions), 'Parsing %s book data' % self.title_and_author))
                if log: log('%s \tParsing book data...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
                perc += 1
                self._parse_book()
                if notifications: notifications.put((perc/(total * actions), 'Creating %s x-ray' % self.title_and_author))
                if log: log('%s \tCreating x-ray...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
                perc += 1
                self._write_xray()
            
            if abort and abort.isSet() or not self.formats_not_failing_exist():
                return
            if self._create_send_author_profile:
                if notifications: notifications.put((perc/(total * actions), 'Creating %s author profile' % self.title_and_author))
                if log: log('%s \tCreating author profile...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
                perc += 1
                self._write_author_profile()
            
            if abort and abort.isSet() or not self.formats_not_failing_exist():
                return
            if self._create_send_start_actions:
                if notifications: notifications.put((perc/(total * actions), 'Creating %s start actions' % self.title_and_author))
                if log: log('%s \tCreating start actions...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
                perc += 1
                self._write_start_actions()
            
            if abort and abort.isSet() or not self.formats_not_failing_exist():
                return
            if self._create_send_end_actions:
                if notifications: notifications.put((perc/(total * actions), 'Creating %s end actions' % self.title_and_author))
                if log: log('%s \tCreating end actions...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
                perc += 1
                self._write_end_actions()

            self._status = self.SUCCESS
            self._status_message = None

            if abort and abort.isSet() or not self.formats_not_failing_exist():
                return
            if self._send_to_device:
                if notifications: notifications.put((perc/(total * actions), 'Sending %s x-ray to device' % self.title_and_author))
                if log: log('%s \tSending x-ray to device...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
                perc += 1
                self.send_files(device_books)
        except:
            return

    def send_files_event(self, device_books, log=None, notifications=None, abort=None, book_num=None, total=None):
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
        self.send_files(device_books, overwrite=False, already_created=False, log=log, abort=abort)

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
        original = None
        if 113 in self.original_exth_records:
            original = self.original_exth_records[113]
        elif 504 in self.original_exth_records:
            original = self.original_exth_records[504]

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
