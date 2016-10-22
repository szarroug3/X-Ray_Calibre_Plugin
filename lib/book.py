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

class Book(object):
    LIBRARY = current_library_path().replace('/', os.sep)

    # Status
    SUCCESS = 0
    IN_PROGRESS = 1
    FAIL = 2

    # Status Messages
    FAILED_BASIC_INFORMATION_MISSING = 'Missing title and/or author'
    FAILED_COULD_NOT_FIND_ASIN = 'Could not find ASIN'
    FAILED_COULD_NOT_FIND_GOODREADS_PAGE = 'Could not find Goodreads page'
    FAILED_LOCAL_BOOK_NOT_FOUND = 'Local book not found'
    FAILED_COULD_NOT_PARSE_GOODREADS_DATA = 'Could not parse Goodreads data'
    FAILED_UNABLE_TO_PARSE_BOOK = 'Unable to parse book'
    FAILED_REMOVE_LOCAL_XRAY = 'Unable to remove local x-ray'
    FAILED_UNABLE_TO_WRITE_XRAY = 'Unable to write x-ray'
    FAILED_REMOVE_LOCAL_AUTHOR_PROFILE = 'Unable to remove local author profile'
    FAILED_UNABLE_TO_WRITE_AUTHOR_PROFILE = 'Unable to write author profile'
    FAILED_REMOVE_LOCAL_START_ACTIONS = 'Unable to remove local start actions'
    FAILED_UNABLE_TO_WRITE_START_ACTIONS = 'Unable to write start actions'
    FAILED_REMOVE_LOCAL_END_ACTIONS = 'Unable to remove local end actions'
    FAILED_UNABLE_TO_WRITE_END_ACTIONS = 'Unable to write end actions'

    # not used yet
    FAILED_UNSUPPORTED_FORMAT = 'Chosen format is unsupported'
    FAILED_UNABLE_TO_UPDATE_ASIN = 'Unable to update ASIN in book on device'
    FAILED_CREATE_LOCAL_XRAY_DIR = 'Unable to create local x-ray directory'
    FAILED_BOOK_NOT_ON_DEVICE = 'The book is not on the device'
    FAILED_FAILED_TO_CREATE_XRAY = 'Attempted to create x-ray but failed to do so'
    FAILED_PREFERENCES_SET_TO_NOT_CREATE_XRAY = 'No local x-ray found. Your preferences are set to not create one if one is not already found when sending to device'
    FAILED_FAILED_TO_SEND_XRAY = 'Could not send x-ray to device'
    FAILED_NO_CONNECTED_DEVICE = 'No device is connected'

    def __init__(self, db, book_id, goodreads_conn, amazon_conn, formats, send_to_device, create_xray_when_sending, expand_aliases,
                    create_send_xray, create_send_author_profile, create_send_start_actions, create_send_end_actions, file_preference):
        self._db = db
        self._book_id = book_id
        self._goodreads_conn = goodreads_conn
        self._formats = formats
        self._send_to_device = send_to_device
        self._create_xray_when_sending = create_xray_when_sending
        self._expand_aliases = expand_aliases
        self._create_send_xray = create_send_xray
        self._create_send_author_profile = create_send_author_profile
        self._create_send_start_actions = create_send_start_actions
        self._create_send_end_actions = create_send_end_actions
        self._file_preference = file_preference

        self._status = self.IN_PROGRESS
        self._status_message = None

        self._book_settings = BookSettings(self._db, self._book_id, self._goodreads_conn, amazon_conn, expand_aliases)

        self._get_basic_information()

        self._status = self.SUCCESS

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
        return '{0} - {1}'.format(self._title, self._author)

    @property
    def xray_format_information(self):
        return self._xray_format_information

    def xray_formats_failing(self):
        for info in self._xray_format_information:
            if info['status'] is self.FAIL:
                yield info

    def xray_formats_not_failing(self):
        for info in self._xray_format_information:
            if info['status'] is not self.FAIL:
                yield info

    def xray_formats_not_failing_exist(self):
        return any(self.xray_formats_not_failing())

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

        if not self._book_settings.prefs['asin'] or self._book_settings.prefs['asin'] == '':
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_FIND_ASIN
            return

        self._goodreads_url = self._book_settings.prefs['goodreads_url']
        self._asin = self._book_settings.prefs['asin']

        if self._create_send_xray:
            self._get_basic_xray_information()
        if self._create_send_author_profile or self._create_send_start_actions or self._create_send_end_actions:
            self._get_basic_non_xray_information()

    def _get_basic_xray_information(self):
        self._aliases = self._book_settings.prefs['aliases']
        self._xray_format_information = []

        for fmt in self._formats:
            info = {'format': fmt, 'status': self.IN_PROGRESS, 'status_message': None}

            # find local book if it exists; fail if it doesn't
            local_book = self._db.format_abspath(self._book_id, fmt.upper())
            if not local_book or not os.path.exists(local_book):
                info['status'] = self.FAIL
                info['status_message'] = self.FAILED_LOCAL_BOOK_NOT_FOUND
                self._xray_format_information.append(info)
                continue

            info['local_book'] = local_book
            local_xray = '.'.join(local_book.split('.')[:-1]) + '.sdr'
            if not os.path.exists(local_xray):
                os.mkdir(local_xray)
            info['local_xray'] = os.path.join(local_xray, fmt.lower())
            if not os.path.exists(info['local_xray']):
                os.mkdir(info['local_xray'])

            self._xray_format_information.append(info)

    def _get_basic_non_xray_information(self):
        local_book_directory = os.path.join(self.LIBRARY, self._db.field_for('path', self._book_id).replace('/', os.sep))
        self._local_book_directory = os.path.join(local_book_directory, 'non_xray')
        if not os.path.exists(self._local_book_directory):
            os.mkdir(self._local_book_directory)

        if self._create_send_author_profile:
            self._author_profile_status = self.IN_PROGRESS
            self._author_profile_status_message = None
        if self._create_send_start_actions:
            self._start_actions_status = self.IN_PROGRESS
            self._start_actions_status_message = None
        if self._create_send_end_actions:
            self._end_actions_status = self.IN_PROGRESS
            self._end_actions_status_message = None


    def create_files_event(self, device_books, log=None, notifications=None, abort=None, book_num=None, total=None):

        actions = 1.0
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
            if notifications: notifications.put((perc/(total * actions), 'Parsing {0} Goodreads data'.format(self.title_and_author)))
            if log: log('{0}    Parsing Goodreads data...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            self._parse_goodreads_data()
            perc += 1
            if self._status is self.FAIL:
                return


            if abort and abort.isSet():
                return
            if self._create_send_xray and self.xray_formats_not_failing_exist():
                if notifications: notifications.put((perc/(total * actions), 'Parsing {0} book data'.format(self.title_and_author)))
                if log: log('{0}    Creating x-ray...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                if log: log('{0}        Parsing book data...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                for info in self.xray_formats_not_failing():
                    self._parse_book(info)
                perc += 1

                if self.xray_formats_not_failing_exist():
                    if notifications: notifications.put((perc/(total * actions), 'Writing {0} x-ray'.format(self.title_and_author)))
                    if log: log('{0}        Writing x-ray...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                    for info in self.xray_formats_not_failing():
                        self._write_xray(info, mark_as_success=device_books is None or not self._send_to_device)
                perc += 1

            if abort and abort.isSet():
                return
            if self._create_send_author_profile:
                if notifications: notifications.put((perc/(total * actions), 'Writing {0} author profile'.format(self.title_and_author)))
                if log: log('{0}    Writing author profile...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                self._write_author_profile()
                perc += 1

            if abort and abort.isSet():
                return
            if self._create_send_start_actions:
                if notifications: notifications.put((perc/(total * actions), 'Writing {0} start actions'.format(self.title_and_author)))
                if log: log('{0}    Writing start actions...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                self._write_start_actions()
                perc += 1

            if abort and abort.isSet():
                return
            if self._create_send_end_actions:
                if notifications: notifications.put((perc/(total * actions), 'Writing {0} end actions'.format(self.title_and_author)))
                if log: log('{0}    Writing end actions...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                self._write_end_actions()
                perc += 1
        except:
            return

    def _parse_goodreads_data(self):
        try:
            goodreads_data = GoodreadsParser(self._goodreads_url, self._goodreads_conn, self._asin,
                create_xray=self._create_send_xray, create_author_profile=self._create_send_author_profile,
                create_start_actions=self._create_send_start_actions, create_end_actions=self._create_send_end_actions)
            goodreads_data.parse()

            if self._create_send_xray:
                self._goodreads_xray = goodreads_data.xray
                for char in self._goodreads_xray['characters'].values():
                    if char['label'] not in self._aliases.keys():
                        self._aliases[char['label']] = char['aliases']

                self._book_settings.prefs['aliases'] = self._aliases

            if self._create_send_author_profile:
                self._goodreads_author_profile = goodreads_data.author_profile
            if self._create_send_start_actions:
                self._goodreads_start_actions = goodreads_data.start_actions
            if self._create_send_end_actions:
                self._goodreads_end_actions = goodreads_data.end_actions
        except:
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_PARSE_GOODREADS_DATA


    def _parse_book(self, info):
        try:
            book_parser = BookParser(info['format'], info['local_book'], self._goodreads_xray, self._aliases)
            book_parser.parse()
            info['parsed_book_data'] = book_parser.parsed_data
        except:
            info['status'] = self.FAIL
            info['status_message'] = self.FAILED_UNABLE_TO_PARSE_BOOK

    def _write_xray(self, info, remove_files_from_dir=True, mark_as_success=True):
        try:
            if remove_files_from_dir:
                for file in glob(os.path.join(info['local_xray'], 'XRAY.entities.*.asc')):
                    os.remove(file)
        except:
            info['status'] = self.FAIL
            info['status_message'] = self.FAILED_REMOVE_LOCAL_XRAY
            return

        try:
            xray_db_writer = XRayDBWriter(info['local_xray'], self._goodreads_url, self._asin, info['parsed_book_data'])
            xray_db_writer.write_xray()
        except:
            info['status'] = self.FAIL
            info['status_message'] = self.FAILED_UNABLE_TO_WRITE_XRAY
            return

        if mark_as_success:
            info['status'] = self.SUCCESS

    def _write_author_profile(self, remove_files_from_dir=True):
        try:
            if remove_files_from_dir:
                for file in glob(os.path.join(self._local_book_directory, 'AuthorProfile.profile.*.asc')):
                    os.remove(file)
        except:
            self._author_profile_status = self.FAIL
            self._author_profile_status_message = self.FAILED_REMOVE_LOCAL_AUTHOR_PROFILE
            return

        try:
            with open(os.path.join(self._local_book_directory, 'AuthorProfile.profile.{0}.asc'.format(self._asin)), 'w+') as author_profile:
                json.dump(self._goodreads_author_profile, author_profile)
        except:
            self._author_profile_status = self.FAIL
            self._author_profile_status_message = self.FAILED_UNABLE_TO_WRITE_AUTHOR_PROFILE
            return

        self._author_profile_status = self.SUCCESS

    def _write_start_actions(self, remove_files_from_dir=True):
        try:
            if remove_files_from_dir:
                for file in glob(os.path.join(self._local_book_directory, 'StartActions.data.*.asc')):
                    os.remove(file)
        except:
            self._start_actions_status = self.FAIL
            self._start_actions_status_message = self.FAILED_REMOVE_LOCAL_START_ACTIONS
            return

        try:
            with open(os.path.join(self._local_book_directory, 'StartActions.data.{0}.asc'.format(self._asin)), 'w+') as start_actions:
                json.dump(self._goodreads_start_actions, start_actions)
        except:
            self._start_actions_status = self.FAIL
            self._start_actions_status_message = self.FAILED_UNABLE_TO_WRITE_START_ACTIONS
            return

        self._start_actions_status = self.SUCCESS

    def _write_end_actions(self, remove_files_from_dir=True):
        try:
            if remove_files_from_dir:
                for file in glob(os.path.join(self._local_book_directory, 'EndActions.data.*.asc')):
                    os.remove(file)
        except:
            self._end_actions_status = self.FAIL
            self._end_actions_status_message = self.FAILED_REMOVE_LOCAL_END_ACTIONS
            return

        try:
            with open(os.path.join(self._local_book_directory, 'EndActions.data.{0}.asc'.format(self._asin)), 'w+') as end_actions:
                json.dump(self._goodreads_end_actions, end_actions)
        except:
            self._end_actions_status = self.FAIL
            self._end_actions_status_message = self.FAILED_UNABLE_TO_WRITE_END_ACTIONS
            return

        self._end_actions_status = self.SUCCESS

    def send_files(self, device_books, overwrite=True, already_created=True, log=None, abort=None):
        pass