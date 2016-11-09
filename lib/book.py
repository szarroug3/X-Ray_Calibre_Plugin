# Book.py
'''Controls book functions and holds book data'''

import os
import json
import struct
from datetime import datetime
from cStringIO import StringIO
from shutil import copy

from calibre.ebooks.mobi import MobiError
from calibre.library import current_library_path
from calibre.ebooks.metadata.mobi import MetadataUpdater

from calibre_plugins.xray_creator.lib.status_info import StatusInfo
from calibre_plugins.xray_creator.lib.book_parser import BookParser
from calibre_plugins.xray_creator.lib.book_settings import BookSettings
from calibre_plugins.xray_creator.lib.xray_db_writer import XRayDBWriter
from calibre_plugins.xray_creator.lib.goodreads_parser import GoodreadsParser

class Book(object):
    '''Class to hold book information and creates/sends files depending on user settings'''

    LIBRARY = current_library_path().replace('/', os.sep)

    def __init__(self, database, book_id, goodreads_conn, amazon_conn, formats, send_to_device, create_files_when_sending,
                 expand_aliases, overwrite_local, overwrite_device, create_send_xray, create_send_author_profile,
                 create_send_start_actions, create_send_end_actions, file_preference):
        self._database = database
        self._book_id = book_id
        self._goodreads_conn = goodreads_conn
        self._formats = formats
        self._send_to_device = send_to_device
        self._create_files_when_sending = create_files_when_sending
        self._expand_aliases = expand_aliases
        self._overwrite_local = overwrite_local
        self._overwrite_device = overwrite_device
        self._create_send_xray = create_send_xray
        self._create_send_author_profile = create_send_author_profile
        self._create_send_start_actions = create_send_start_actions
        self._create_send_end_actions = create_send_end_actions
        self._file_preference = file_preference

        self._status = StatusInfo(status=StatusInfo.IN_PROGRESS)

        self._aliases = None
        self._device_sdr = None
        self._local_book_directory = None
        self._formats_on_device = None
        self._xray_format_information = None

        self._xray_send_fmt = None
        self._xray_status = StatusInfo()
        self._xray_send_status = StatusInfo()
        self._author_profile_status = StatusInfo()
        self._author_profile_send_status = StatusInfo()
        self._start_actions_status = StatusInfo()
        self._start_actions_send_status = StatusInfo()
        self._end_actions_status = StatusInfo()
        self._end_actions_send_status = StatusInfo()

        self._goodreads_author_profile = None
        self._goodreads_end_actions = None
        self._goodreads_start_actions = None
        self._goodreads_xray = None

        self._book_settings = BookSettings(self._database, self._book_id, self._goodreads_conn, amazon_conn, expand_aliases)

        self._get_basic_information()

        if self._status.status != StatusInfo.FAIL:
            self._status.status = StatusInfo.SUCCESS

    @property
    def status(self):
        return self._status

    @property
    def xray_status(self):
        return self._xray_status

    @property
    def xray_send_status(self):
        return self._xray_send_status

    @property
    def xray_send_fmt(self):
        return self._xray_send_fmt

    @property
    def author_profile_status(self):
        return self._author_profile_status

    @property
    def author_profile_send_status(self):
        return self._author_profile_send_status

    @property
    def start_actions_status(self):
        return self._start_actions_status

    @property
    def start_actions_send_status(self):
        return self._start_actions_send_status

    @property
    def end_actions_status(self):
        return self._end_actions_status

    @property
    def end_actions_send_status(self):
        return self._end_actions_send_status

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

    def xray_formats_failing(self):
        '''Yields x-ray formats that are failing'''
        for fmt, info in self._xray_format_information.items():
            if info['status'].status is StatusInfo.FAIL:
                yield (fmt, info)

    def xray_formats_not_failing(self):
        '''Yields x-ray formats that are not failing'''
        for fmt, info in self._xray_format_information.items():
            if info['status'].status is not StatusInfo.FAIL:
                yield (fmt, info)

    def xray_formats_not_failing_exist(self):
        '''Checks if any formats that aren't failing exist'''
        return any(self.xray_formats_not_failing())

    def _get_basic_information(self):
        '''Gets title, author, goodreads url, ASIN, and file specific info for the book'''
        self._title = self._database.field_for('title', self._book_id)
        self._author = ' & '.join(self._database.field_for('authors', self._book_id))

        if self._title == 'Unknown' or self._author == 'Unknown':
            self._status.set(StatusInfo.FAIL, StatusInfo.F_BASIC_INFORMATION_MISSING)
            return

        if not self._book_settings.prefs['goodreads_url'] or self._book_settings.prefs['goodreads_url'] == '':
            self._status.set(StatusInfo.FAIL, StatusInfo.F_COULD_NOT_FIND_GOODREADS_PAGE)
            return

        if not self._book_settings.prefs['asin'] or self._book_settings.prefs['asin'] == '':
            self._status.set(StatusInfo.FAIL, StatusInfo.F_COULD_NOT_FIND_ASIN)
            return

        self._goodreads_url = self._book_settings.prefs['goodreads_url']
        self._asin = self._book_settings.prefs['asin']

        if self._create_send_xray:
            self._get_basic_xray_information()
        if self._create_send_author_profile or self._create_send_start_actions or self._create_send_end_actions:
            self._get_basic_non_xray_information()
        if self._send_to_device:
            self._files_to_send = {}

    def _get_basic_xray_information(self):
        '''Gets aliases and format information for the book and initializes x-ray variables'''
        self._aliases = self._book_settings.prefs['aliases']
        self._xray_format_information = {}
        self._xray_status.status = StatusInfo.IN_PROGRESS

        for fmt in self._formats:
            info = {'status': StatusInfo(status=StatusInfo.IN_PROGRESS)}

            # find local book if it exists; fail if it doesn't
            local_book = self._database.format_abspath(self._book_id, fmt.upper())
            if not local_book or not os.path.exists(local_book):
                info['status'].set(StatusInfo.FAIL, StatusInfo.F_LOCAL_BOOK_NOT_FOUND)
            else:
                info['local_book'] = local_book
                local_xray = '.'.join(local_book.split('.')[:-1]) + '.sdr'
                if not os.path.exists(local_xray):
                    os.mkdir(local_xray)
                info['local_xray'] = os.path.join(local_xray, fmt)
                if not os.path.exists(info['local_xray']):
                    os.mkdir(info['local_xray'])

            self._xray_format_information[fmt.lower()] = info

    def _get_basic_non_xray_information(self):
        '''Gets local book's directory and initializes non-xray variables'''
        book_path = self._database.field_for('path', self._book_id).replace('/', os.sep)
        local_book_directory = os.path.join(self.LIBRARY, book_path)
        self._local_book_directory = os.path.join(local_book_directory, 'non_xray')
        if not os.path.exists(self._local_book_directory):
            os.mkdir(self._local_book_directory)

        if self._create_send_author_profile:
            self._author_profile_status.status = StatusInfo.IN_PROGRESS
        if self._create_send_start_actions:
            self._start_actions_status.status = StatusInfo.IN_PROGRESS
        if self._create_send_end_actions:
            self._end_actions_status.status = StatusInfo.IN_PROGRESS

    def create_files_event(self, device_books, log=None, notifications=None, abort=None,
                           book_num=None, total=None):
        '''Creates and sends files depending on user's settings'''
        actions = 1.0
        if not self._overwrite_local:
            actions += 1
        if self._create_send_xray:
            actions += 2
        if self._create_send_author_profile:
            actions += 1
        if self._create_send_start_actions:
            actions += 1
        if self._create_send_end_actions:
            actions += 1
        if self._send_to_device and device_books is not None:
            actions += 1
        perc = book_num * actions

        title_and_author = self.title_and_author

        # Prep
        if abort and abort.isSet():
            return
        if not self._overwrite_local:
            if notifications: notifications.put((self._calculate_percentage(perc, total * actions),
                                                 'Checking for {0} existing files'.format(title_and_author)))
            if log: log('{0}    Checking for existing files...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            self._check_for_existing_files()
            perc += 1

        if abort and abort.isSet():
            return
        create_xray = self._create_send_xray and self.xray_formats_not_failing_exist()
        author_profile = self._create_send_author_profile and self._author_profile_status.status != StatusInfo.FAIL
        start_actions = self._create_send_start_actions and self._start_actions_status.status != StatusInfo.FAIL
        end_actions = self._create_send_end_actions and self._end_actions_status.status != StatusInfo.FAIL
        if create_xray or author_profile or start_actions or end_actions:
            if notifications: notifications.put((self._calculate_percentage(perc, total * actions),
                                                 'Parsing {0} Goodreads data'.format(title_and_author)))
            if log: log('{0}    Parsing Goodreads data...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            self._parse_goodreads_data(create_xray=create_xray, create_author_profile=author_profile,
                                       create_start_actions=start_actions, create_end_actions=end_actions)
            perc += 1
            if self._status.status is StatusInfo.FAIL:
                return

            # Creating Files
            if abort and abort.isSet():
                return
            if self._create_send_xray:
                if self.xray_formats_not_failing_exist() and self._xray_status.status != StatusInfo.FAIL:
                    if notifications: notifications.put((self._calculate_percentage(perc, total * actions),
                                                         'Parsing {0} book data'.format(self.title_and_author)))
                    if log: log('{0}    Creating x-ray...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                    if log: log('{0}        Parsing book data...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                    for fmt, info in self.xray_formats_not_failing():
                        self._parse_book(fmt, info)
                perc += 1

                if self.xray_formats_not_failing_exist():
                    if notifications: notifications.put((self._calculate_percentage(perc, total * actions),
                                                         'Writing {0} x-ray'.format(self.title_and_author)))
                    if log: log('{0}        Writing x-ray...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                    for fmt, info in self.xray_formats_not_failing():
                        self._write_xray(info)
                    self._xray_status.status = StatusInfo.SUCCESS
                perc += 1

            if self._create_send_author_profile:
                if self._author_profile_status.status != StatusInfo.FAIL:
                    if notifications: notifications.put((self._calculate_percentage(perc, total * actions),
                                                         'Writing {0} author profile'.format(self.title_and_author)))
                    if log: log('{0}    Writing author profile...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                    self._write_author_profile()
                perc += 1

            if self._create_send_start_actions:
                if self._start_actions_status.status != StatusInfo.FAIL:
                    if notifications: notifications.put((self._calculate_percentage(perc, total * actions),
                                                         'Writing {0} start actions'.format(self.title_and_author)))
                    if log: log('{0}    Writing start actions...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                    self._write_start_actions()
                perc += 1

            if self._create_send_end_actions:
                if self._end_actions_status.status != StatusInfo.FAIL:
                    if notifications: notifications.put((self._calculate_percentage(perc, total * actions),
                                                         'Writing {0} end actions'.format(self.title_and_author)))
                    if log: log('{0}    Writing end actions...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                    self._write_end_actions()
                perc += 1

            # Sending Files
            if self._send_to_device and device_books is not None:
                send_files = False
                if self._create_send_xray and self.xray_formats_not_failing_exist():
                    send_files = True
                elif self._create_send_author_profile and self._author_profile_status.status != StatusInfo.FAIL:
                    send_files = True
                elif self._create_send_start_actions and self._start_actions_status.status != StatusInfo.FAIL:
                    send_files = True
                elif self._create_send_end_actions and self._end_actions_status.status != StatusInfo.FAIL:
                    send_files = True

                if send_files:
                    if notifications: notifications.put((self._calculate_percentage(perc, total * actions),
                                                         'Sending {0} files to device'.format(self.title_and_author)))
                    if log: log('{0}    Sending files to device...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                    self._check_fmts_for_create_event(device_books)
                    self._send_files(device_books)
                perc += 1

    def send_files_event(self, device_books, log=None, notifications=None, abort=None, book_num=None, total=None):
        '''Sends files to device depending on user's settings'''
        try:
            if abort and abort.isSet():
                return

            if notifications: notifications.put((self._calculate_percentage(book_num, total), self.title_and_author))
            checked_data = self._check_fmts_for_send_event(device_books)
            create_xray_format_info, create_author_profile, create_start_actions, create_end_actions = checked_data
            if create_xray_format_info or create_author_profile or create_start_actions or create_end_actions:
                if log: log('{0}    Parsing {1} Goodreads data...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S'),
                                                                          self.title_and_author))
                create_xray = True if create_xray_format_info != None else False
                self._parse_goodreads_data(create_xray=create_xray, create_author_profile=create_author_profile,
                                           create_start_actions=create_start_actions, create_end_actions=create_end_actions)
                if self._status.status is StatusInfo.FAIL:
                    return
                if create_xray_format_info and self._xray_status.status != StatusInfo.FAIL:
                    if log: log('{0}    Creating {1} x-ray...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S'),
                                                                      self.title_and_author))
                    self._parse_book(create_xray_format_info['format'],
                                     self._xray_format_information[create_xray_format_info['format']])

                    if self._xray_format_information[create_xray_format_info['format']]['status'].status != StatusInfo.FAIL:
                        self._write_xray(self._xray_format_information[create_xray_format_info['format']])

                        if os.path.exists(create_xray_format_info['local']):
                            self._files_to_send['xray'] = create_xray_format_info

                if create_author_profile and self._author_profile_status.status != StatusInfo.FAIL:
                    if log: log('{0}    Creating {1} author profile...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S'),
                                                                               self.title_and_author))
                    self._write_author_profile()
                if create_start_actions and self._start_actions_status.status != StatusInfo.FAIL:
                    if log: log('{0}    Creating {1} start actions...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S'),
                                                                              self.title_and_author))
                    self._write_start_actions()
                if create_end_actions and self._end_actions_status.status != StatusInfo.FAIL:
                    if log: log('{0}    Creating {1} end actions...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S'),
                                                                            self.title_and_author))
                    self._write_end_actions()

            if len(self._files_to_send) > 0:
                if log: log('{0}    Sending files to device...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                self._send_files(device_books)
        except:
            return

    @staticmethod
    def _calculate_percentage(amt_completed, total):
        '''Calculates percentage of amt_completed compared to total; Minimum returned is .01'''
        return amt_completed/total if amt_completed/total >= .01 else .01


    def _parse_goodreads_data(self, create_xray=None, create_author_profile=None,
                              create_start_actions=None, create_end_actions=None):
        if create_xray is None:
            create_xray = self._create_send_xray
        if create_author_profile is None:
            create_author_profile = self._create_send_author_profile
        if create_start_actions is None:
            create_start_actions = self._create_send_start_actions
        if create_end_actions is None:
            create_end_actions = self._create_send_end_actions
        try:
            goodreads_data = GoodreadsParser(self._goodreads_url, self._goodreads_conn, self._asin,
                                             create_xray=create_xray, create_author_profile=create_author_profile,
                                             create_start_actions=create_start_actions,
                                             create_end_actions=create_end_actions)
            goodreads_data.parse()

            if create_xray:
                if goodreads_data.xray:
                    self._goodreads_xray = goodreads_data.xray
                    for char in self._goodreads_xray['characters'].values():
                        if char['label'] not in self._aliases.keys():
                            self._aliases[char['label']] = char['aliases']

                    self._book_settings.prefs['aliases'] = self._aliases
                    self._xray_status.status = StatusInfo.SUCCESS
                else:
                    self._xray_status.set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_CREATE_XRAY)
            if create_author_profile:
                if goodreads_data.author_profile:
                    self._goodreads_author_profile = goodreads_data.author_profile
                else:
                    self._author_profile_status.set(StatusInfo.FAIL,
                                                                       StatusInfo.F_UNABLE_TO_CREATE_AUTHOR_PROFILE)
            if create_start_actions:
                if goodreads_data.start_actions:
                    self._goodreads_start_actions = goodreads_data.start_actions
                else:
                    self._start_actions_status.set(StatusInfo.FAIL,
                                                                      StatusInfo.F_UNABLE_TO_CREATE_START_ACTIONS)
            if create_end_actions:
                if goodreads_data.end_actions:
                    self._goodreads_end_actions = goodreads_data.end_actions
                else:
                    self._end_actions_status.set(StatusInfo.FAIL,
                                                                    StatusInfo.F_UNABLE_TO_CREATE_END_ACTIONS)
        except:
            self._status.set(StatusInfo.FAIL, StatusInfo.F_COULD_NOT_PARSE_GOODREADS_DATA)

    def _parse_book(self, fmt, info):
        '''Will parse book using the format info given'''
        try:
            book_parser = BookParser(fmt, info['local_book'], self._goodreads_xray, self._aliases)
            book_parser.parse()
            info['parsed_book_data'] = book_parser.parsed_data
        except:
            info['status'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_PARSE_BOOK)

    def _check_for_existing_files(self):
        '''Checks if files exist and fails for that type if they do'''
        if self._create_send_xray:
            for fmt_info in self.xray_formats_not_failing():
                info = fmt_info[1]
                if os.path.exists(os.path.join(info['local_xray'], 'XRAY.entities.{0}.asc'.format(self._asin))):
                    info['status'].set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_LOCAL_XRAY)
        if self._create_send_author_profile:
            if os.path.exists(os.path.join(self._local_book_directory, 'AuthorProfile.profile.{0}.asc'.format(self._asin))):
                self._author_profile_status.set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_LOCAL_AUTHOR_PROFILE)
        if self._create_send_start_actions:
            if os.path.exists(os.path.join(self._local_book_directory, 'StartActions.data.{0}.asc'.format(self._asin))):
                self._start_actions_status.set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_LOCAL_START_ACTIONS)
        if self._create_send_end_actions:
            if os.path.exists(os.path.join(self._local_book_directory, 'EndActions.data.{0}.asc'.format(self._asin))):
                self._end_actions_status.set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_LOCAL_END_ACTIONS)

    def _write_xray(self, info):
        '''Writes x-ray file using goodreads and parsed book data; Will save in local directory'''
        try:
            filename = os.path.join(info['local_xray'], 'XRAY.entities.{0}.asc'.format(self._asin))
            if os.path.exists(filename):
                os.remove(filename)
        except:
            info['status'].set(StatusInfo.FAIL, StatusInfo.F_REMOVE_LOCAL_XRAY)

        try:
            xray_db_writer = XRayDBWriter(info['local_xray'], self._goodreads_url, self._asin, info['parsed_book_data'])
            xray_db_writer.write_xray()
        except:
            info['status'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_WRITE_XRAY)
            return

        if not os.path.exists(os.path.join(info['local_xray'], 'XRAY.entities.{0}.asc'.format(self._asin))):
            info['status'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_WRITE_XRAY)
            return

        info['status'].status = StatusInfo.SUCCESS

    def _write_author_profile(self):
        '''Writes author profile file using goodreads; Will save in local directory'''
        try:
            filename = os.path.join(self._local_book_directory, 'AuthorProfile.profile.{0}.asc'.format(self._asin))
            if os.path.exists(filename):
                os.remove(filename)
        except:
            self._author_profile_status.set(StatusInfo.FAIL, StatusInfo.F_REMOVE_LOCAL_AUTHOR_PROFILE)

        try:
            with open(os.path.join(self._local_book_directory, 'AuthorProfile.profile.{0}.asc'.format(self._asin)),
                      'w+') as author_profile:
                json.dump(self._goodreads_author_profile, author_profile)
        except:
            self._author_profile_status.set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_WRITE_AUTHOR_PROFILE)
            return

        self._author_profile_status.status = StatusInfo.SUCCESS
        if self._send_to_device:
            filename = 'AuthorProfile.profile.{0}.asc'.format(self._asin)
            local_file = os.path.join(self._local_book_directory, filename)
            self._files_to_send['author_profile'] = {'local': local_file, 'filename': filename}

    def _write_start_actions(self):
        '''Writes start actions file using goodreads; Will save in local directory'''
        try:
            filename = os.path.join(self._local_book_directory, 'StartActions.data.{0}.asc'.format(self._asin))
            if os.path.exists(filename):
                os.remove(filename)
        except:
            self._start_actions_status.set(StatusInfo.FAIL, StatusInfo.F_REMOVE_LOCAL_START_ACTIONS)

        try:
            with open(os.path.join(self._local_book_directory, 'StartActions.data.{0}.asc'.format(self._asin)),
                      'w+') as start_actions:
                json.dump(self._goodreads_start_actions, start_actions)
        except:
            self._start_actions_status.set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_WRITE_START_ACTIONS)
            return

        self._start_actions_status.status = StatusInfo.SUCCESS
        if self._send_to_device:
            filename = 'StartActions.data.{0}.asc'.format(self._asin)
            local_file = os.path.join(self._local_book_directory, filename)
            self._files_to_send['start_actions'] = {'local': local_file, 'filename': filename}

    def _write_end_actions(self):
        '''Writes end actions file using goodreads; Will save in local directory'''
        try:
            filename = os.path.join(self._local_book_directory, 'EndActions.data.{0}.asc'.format(self._asin))
            if os.path.exists(filename):
                os.remove(filename)
        except:
            self._end_actions_status.set(StatusInfo.FAIL, StatusInfo.F_REMOVE_LOCAL_END_ACTIONS)

        try:
            with open(os.path.join(self._local_book_directory, 'EndActions.data.{0}.asc'.format(self._asin)),
                      'w+') as end_actions:
                json.dump(self._goodreads_end_actions, end_actions)
        except:
            self._end_actions_status.set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_WRITE_END_ACTIONS)
            return

        self._end_actions_status.status = StatusInfo.SUCCESS
        if self._send_to_device:
            filename = 'EndActions.data.{0}.asc'.format(self._asin)
            local_file = os.path.join(self._local_book_directory, filename)
            self._files_to_send['end_actions'] = {'local': local_file, 'filename': filename}

    def _check_fmts_for_create_event(self, device_books):
        '''Compiles dict of file type info to use when creating files'''
        if len(device_books) == 0 or len(device_books[self._book_id].keys()) == 0:
            if self._create_send_xray:
                for fmt, info in self.xray_formats_not_failing():
                    if info['status'].status == StatusInfo.SUCCESS:
                        self._xray_send_status.set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
            if self._create_send_author_profile and self._author_profile_status.status == StatusInfo.SUCCESS:
                self._author_profile_send_status.set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
                if self._files_to_send.has_key('author_profile'):
                    del self._files_to_send['author_profile']
            if self._create_send_start_actions and self._start_actions_status.status == StatusInfo.SUCCESS:
                self._start_actions_send_status.set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
                if self._files_to_send.has_key('start_actions'):
                    del self._files_to_send['start_actions']
            if self._create_send_end_actions and self._end_actions_status.status == StatusInfo.SUCCESS:
                self._end_actions_send_status.set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
                if self._files_to_send.has_key('end_actions'):
                    del self._files_to_send['end_actions']
            return

        self._device_sdr = device_books[self._book_id][device_books[self._book_id].keys()[0]]['device_sdr']
        if not os.path.exists(self._device_sdr):
            os.mkdir(self._device_sdr)

        self._formats_on_device = device_books[self._book_id].keys()

        if self._create_send_xray and self.xray_formats_not_failing_exist():
            # figure out which format to send
            formats_not_failing = [fmt for fmt, info in self.xray_formats_not_failing()]
            common_formats = list(set(self._formats_on_device).intersection(formats_not_failing))

            if len(common_formats) == 0:
                for fmt, info in self.xray_formats_not_failing():
                    info['status'].status = StatusInfo.SUCCESS
                    self._xray_send_status.set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
            else:
                format_picked = self._file_preference
                if len(common_formats) == 1:
                    format_picked = common_formats[0]

                for fmt, info in self.xray_formats_not_failing():
                    if fmt != format_picked:
                        info['status'].status = StatusInfo.SUCCESS
                        continue

                    filename = 'XRAY.entities.{0}.asc'.format(self._asin)
                    local_file = os.path.join(info['local_xray'], filename)
                    self._files_to_send['xray'] = {'local': local_file, 'filename': filename, 'format': format_picked}

    def _check_fmts_for_send_event(self, device_books):
        '''Compiles dict of file type info to use when sending files'''
        create_xray = None
        create_author_profile = False
        create_start_actions = False
        create_end_actions = False

        if len(device_books[self._book_id].keys()) == 0:
            if self._create_send_xray:
                for fmt, info in self._xray_format_information.items():
                    self._xray_send_status.set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
            if self._create_send_author_profile:
                self._author_profile_send_status.set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
            if self._create_send_start_actions:
                self._start_actions_send_status.set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
            if self._create_send_end_actions:
                self._end_actions_send_status.set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
            return create_xray, create_author_profile, create_start_actions, create_end_actions

        self._device_sdr = device_books[self._book_id][device_books[self._book_id].keys()[0]]['device_sdr']
        if not os.path.exists(self._device_sdr):
            os.mkdir(self._device_sdr)

        self._formats_on_device = device_books[self._book_id].keys()

        if self._create_send_xray:
            # figure out which format to send
            formats_not_failing = [fmt for fmt, info in self._xray_format_information.items()]
            common_formats = list(set(self._formats_on_device).intersection(formats_not_failing))

            if len(common_formats) == 0:
                for fmt, info in self._xray_format_information.items():
                    info['status'].status = StatusInfo.SUCCESS
                    self._xray_send_status.set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
            else:
                format_picked = self._file_preference
                if len(common_formats) == 1:
                    format_picked = common_formats[0]

                filename = 'XRAY.entities.{0}.asc'.format(self._asin)
                local_file = os.path.join(self._xray_format_information[format_picked]['local_xray'], filename)
                if os.path.exists(os.path.join(self._device_sdr, filename)) and not self._overwrite_device:
                    self._xray_send_status.set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_DEVICE_XRAY)
                else:
                    if os.path.exists(local_file):
                        self._files_to_send['xray'] = {'local': local_file, 'filename': filename, 'format': format_picked}
                    else:
                        if not self._create_files_when_sending:
                            self._xray_send_status.set(StatusInfo.FAIL, StatusInfo.F_PREFS_SET_TO_NOT_CREATE_XRAY)
                        else:
                            create_xray = {'local': local_file, 'filename': filename, 'format': format_picked}
        if self._create_send_author_profile:
            filename = 'AuthorProfile.profile.{0}.asc'.format(self._asin)
            local_file = os.path.join(self._local_book_directory, filename)
            if os.path.exists(os.path.join(self._device_sdr, filename)) and not self._overwrite_device:
                self._author_profile_send_status.set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_DEVICE_AUTHOR_PROFILE)
            else:
                if os.path.exists(local_file):
                    self._files_to_send['author_profile'] = {'local': local_file, 'filename': filename}
                else:
                    if not self._create_files_when_sending:
                        self._author_profile_send_status.set(StatusInfo.FAIL, StatusInfo.F_PREFS_SET_TO_NOT_CREATE_XRAY)
                    else:
                        create_author_profile = True
        if self._create_send_start_actions:
            filename = 'StartActions.data.{0}.asc'.format(self._asin)
            local_file = os.path.join(self._local_book_directory, filename)
            if os.path.exists(os.path.join(self._device_sdr, filename)) and not self._overwrite_device:
                self._start_actions_send_status.set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_DEVICE_START_ACTIONS)
            else:
                if os.path.exists(local_file):
                    self._files_to_send['start_actions'] = {'local': local_file, 'filename': filename}
                else:
                    if not self._create_files_when_sending:
                        self._start_actions_send_status.set(StatusInfo.FAIL, StatusInfo.F_PREFS_SET_TO_NOT_CREATE_XRAY)
                    else:
                        create_start_actions = True
        if self._create_send_end_actions:
            filename = 'EndActions.data.{0}.asc'.format(self._asin)
            local_file = os.path.join(self._local_book_directory, filename)
            if os.path.exists(os.path.join(self._device_sdr, filename)) and not self._overwrite_device:
                self._end_actions_send_status.set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_DEVICE_END_ACTIONS)
            else:
                if os.path.exists(local_file):
                    self._files_to_send['end_actions'] = {'local': local_file, 'filename': filename}
                else:
                    if not self._create_files_when_sending:
                        self._end_actions_send_status.set(StatusInfo.FAIL, StatusInfo.F_PREFS_SET_TO_NOT_CREATE_XRAY)
                    else:
                        create_end_actions = True

        return create_xray, create_author_profile, create_start_actions, create_end_actions

    def _send_files(self, device_books):
        '''Sends files to device depending on list compiled in self._files_to_send'''
        if len(self._files_to_send) == 0:
            return

        number_of_failed_asin_updates = 0
        try:
            for fmt in self._formats_on_device:
                with open(device_books[self._book_id][fmt]['device_book'], 'r+b') as stream:
                    mobi_updater = ASINUpdater(stream)
                    mobi_updater.update(self._asin)
        except:
            number_of_failed_asin_updates += 1
            if (self._create_send_xray and self._send_to_device.has_key('xray') and
                    fmt == self._send_to_device['xray']['format']):
                self._xray_send_status.set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_UPDATE_ASIN)
                self._xray_send_fmt = self._files_to_send['xray']['format']
                if self._files_to_send.has_key('xray'):
                    del self._files_to_send['xray']
            if number_of_failed_asin_updates == len(self._formats_on_device):
                if self._create_send_author_profile:
                    self._author_profile_send_status.set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_UPDATE_ASIN)
                if self._create_send_start_actions:
                    self._start_actions_send_status.set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_UPDATE_ASIN)
                if self._create_send_end_actions:
                    self._end_actions_send_status.set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_UPDATE_ASIN)
                return

        # temporarily rename current file in case send fails
        for filetype, info in self._files_to_send.items():
            device_filename = os.path.join(self._device_sdr, info['filename'])
            if os.path.exists(device_filename):
                os.rename(device_filename, '{0}.old'.format(device_filename))
            copy(info['local'], self._device_sdr)

            if os.path.exists(device_filename):
                if os.path.exists('{0}.old'.format(device_filename)):
                    os.remove('{0}.old'.format(device_filename))
                if filetype == 'xray':
                    self._xray_send_status.status = StatusInfo.SUCCESS
                    self._xray_send_fmt = self._files_to_send['xray']['format']
                elif filetype == 'author_profile':
                    self._author_profile_send_status.status = StatusInfo.SUCCESS
                elif filetype == 'start_actions':
                    self._start_actions_send_status.status = StatusInfo.SUCCESS
                elif filetype == 'end_actions':
                    self._end_actions_send_status.status = StatusInfo.SUCCESS
            else:
                os.rename('{0}.old'.format(device_filename), device_filename)
                if filetype == 'xray':
                    self._xray_send_status.set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_SEND_XRAY)
                    self._xray_send_fmt = self._xray_send_fmt
                elif filetype == 'author_profile':
                    self._author_profile_send_status.set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_SEND_AUTHOR_PROFILE)
                elif filetype == 'start_actions':
                    self._start_actions_send_status.set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_SEND_START_ACTIONS)
                elif filetype == 'end_actions':
                    self._end_actions_send_status.set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_SEND_END_ACTIONS)

class ASINUpdater(MetadataUpdater):
    '''Class to modify MOBI book'''
    def update(self, asin):
        '''This will update ASIN'''
        def update_exth_record(rec):
            '''Gets exth records'''
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
            return

        update_exth_record((113, asin.encode(self.codec, 'replace')))
        update_exth_record((504, asin.encode(self.codec, 'replace')))

        # Include remaining original EXTH fields
        for record_id in sorted(self.original_exth_records):
            recs.append((record_id, self.original_exth_records[record_id]))
        recs = sorted(recs, key=lambda x: (x[0], x[0]))

        exth = StringIO()
        for code, data in recs:
            exth.write(struct.pack('>II', code, len(data) + 8))
            exth.write(data)
        exth = exth.getvalue()
        trail = len(exth) % 4
        pad = '\0' * (4 - trail) # Always pad w/ at least 1 byte
        exth = ''.join(['EXTH', struct.pack('>II', len(exth) + 12, len(recs)), exth, pad])

        if getattr(self, 'exth', None) is None:
            raise MobiError('No existing EXTH record. Cannot update ASIN.')

        self.create_exth(exth=exth)

        return
