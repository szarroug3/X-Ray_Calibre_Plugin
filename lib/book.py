# Book.py
'''Controls book functions and holds book data'''

import os
import json
import struct
from datetime import datetime
from cStringIO import StringIO
from shutil import copy

from calibre.ebooks.mobi import MobiError
from calibre.ebooks.metadata.mobi import MetadataUpdater

from calibre_plugins.xray_creator.lib.utilities import LIBRARY
from calibre_plugins.xray_creator.lib.status_info import StatusInfo
from calibre_plugins.xray_creator.lib.book_parser import BookParser
from calibre_plugins.xray_creator.lib.book_settings import BookSettings
from calibre_plugins.xray_creator.lib.exceptions import PageDoesNotExist
from calibre_plugins.xray_creator.lib.xray_db_writer import XRayDBWriter
from calibre_plugins.xray_creator.lib.goodreads_parser import GoodreadsParser

class Book(object):
    '''Class to hold book information and creates/sends files depending on user settings'''

    def __init__(self, database, book_id, connections, settings):
        self._book_id = book_id
        self._goodreads_conn = connections['goodreads']
        self._settings = settings

        self._aliases = None
        self._device_sdr = None
        self._local_book_directory = None
        self._xray_format_information = None

        self._xray_send_fmt = None
        self._statuses = {'general': StatusInfo(status=StatusInfo.IN_PROGRESS),
                          'xray': StatusInfo(), 'xray_send': StatusInfo(),
                          'author_profile': StatusInfo(), 'author_profile_send': StatusInfo(),
                          'start_actions': StatusInfo(), 'start_actions_send': StatusInfo(),
                          'end_actions': StatusInfo(), 'end_actions_send': StatusInfo()}

        self._goodreads_author_profile = None
        self._goodreads_end_actions = None
        self._goodreads_start_actions = None
        self._goodreads_xray = None

        self._book_settings = BookSettings(database, book_id, connections)

        self._get_basic_information(database, settings['formats'])

        if self._statuses['general'].status != StatusInfo.FAIL:
            self._statuses['general'].status = StatusInfo.SUCCESS

    @property
    def status(self):
        return self._statuses['general']

    @property
    def xray_status(self):
        return self._statuses['xray']

    @property
    def xray_send_status(self):
        return self._statuses['xray_send']

    @property
    def xray_send_fmt(self):
        return self._xray_send_fmt

    @property
    def author_profile_status(self):
        return self._statuses['author_profile']

    @property
    def author_profile_send_status(self):
        return self._statuses['author_profile_send']

    @property
    def start_actions_status(self):
        return self._statuses['start_actions']

    @property
    def start_actions_send_status(self):
        return self._statuses['start_actions_send']

    @property
    def end_actions_status(self):
        return self._statuses['end_actions']

    @property
    def end_actions_send_status(self):
        return self._statuses['end_actions_send']

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

    def _get_basic_information(self, database, formats):
        '''Gets title, author, goodreads url, ASIN, and file specific info for the book'''
        self._title = database.field_for('title', self._book_id)
        self._author = ' & '.join(database.field_for('authors', self._book_id))

        if self._title == 'Unknown' or self._author == 'Unknown':
            self._statuses['general'].set(StatusInfo.FAIL, StatusInfo.F_BASIC_INFORMATION_MISSING)
            return

        if not self._book_settings.prefs['goodreads_url'] or self._book_settings.prefs['goodreads_url'] == '':
            self._statuses['general'].set(StatusInfo.FAIL, StatusInfo.F_COULD_NOT_FIND_GOODREADS_PAGE)
            return

        if not self._book_settings.prefs['asin'] or self._book_settings.prefs['asin'] == '':
            self._statuses['general'].set(StatusInfo.FAIL, StatusInfo.F_COULD_NOT_FIND_ASIN)
            return

        self._goodreads_url = self._book_settings.prefs['goodreads_url']
        self._asin = self._book_settings.prefs['asin']

        if self._settings['create_send_xray']:
            self._get_basic_xray_information(database, formats)
        if (self._settings['create_send_author_profile']
                or self._settings['create_send_start_actions']
                or self._settings['create_send_end_actions']):
            self._get_basic_non_xray_information(database)
        if self._settings['send_to_device']:
            self._files_to_send = {}

    def _get_basic_xray_information(self, database, formats):
        '''Gets aliases and format information for the book and initializes x-ray variables'''
        self._aliases = self._book_settings.prefs['aliases']
        self._xray_format_information = {}
        self._statuses['xray'].status = StatusInfo.IN_PROGRESS

        for fmt in formats:
            info = {'status': StatusInfo(status=StatusInfo.IN_PROGRESS)}

            # find local book if it exists; fail if it doesn't
            local_book = database.format_abspath(self._book_id, fmt.upper())
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

        if not self.xray_formats_not_failing_exist():
            self._statuses['xray'].set(StatusInfo.FAIL, StatusInfo.F_NO_APPROPRIATE_LOCAL_BOOK_FOUND)

    def _get_basic_non_xray_information(self, database):
        '''Gets local book's directory and initializes non-xray variables'''
        book_path = database.field_for('path', self._book_id).replace('/', os.sep)
        local_book_directory = os.path.join(LIBRARY, book_path)
        self._local_book_directory = os.path.join(local_book_directory, 'non_xray')
        if not os.path.exists(self._local_book_directory):
            os.mkdir(self._local_book_directory)

        if self._settings['create_send_author_profile']:
            self._statuses['author_profile'].status = StatusInfo.IN_PROGRESS
        if self._settings['create_send_start_actions']:
            self._statuses['start_actions'].status = StatusInfo.IN_PROGRESS
        if self._settings['create_send_end_actions']:
            self._statuses['end_actions'].status = StatusInfo.IN_PROGRESS

    def create_files_event(self, device_books, perc, total, log, notifications, abort):
        '''Creates and sends files depending on user's settings'''
        title_and_author = self.title_and_author

        # Prep
        if not self._settings['overwrite_when_creating']:
            notifications.put((self._calculate_percentage(perc, total),
                               'Checking for {0} existing files'.format(title_and_author)))
            log('{0}    Checking for existing files...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            self._check_for_existing_files()
            perc += 1

        if abort.isSet():
            return
        create_xray = self._settings['create_send_xray'] and self.xray_formats_not_failing_exist()
        author_profile = (self._settings['create_send_author_profile'] and
                          self._statuses['author_profile'].status != StatusInfo.FAIL)
        start_actions = (self._settings['create_send_start_actions'] and
                         self._statuses['start_actions'].status != StatusInfo.FAIL)
        end_actions = self._settings['create_send_end_actions'] and self._statuses['end_actions'].status != StatusInfo.FAIL
        if create_xray or author_profile or start_actions or end_actions:
            notifications.put((self._calculate_percentage(perc, total),
                               'Parsing {0} Goodreads data'.format(title_and_author)))
            log('{0}    Parsing Goodreads data...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            self._parse_goodreads_data(create_xray=create_xray, create_author_profile=author_profile,
                                       create_start_actions=start_actions, create_end_actions=end_actions)
            perc += 1
            if self._statuses['general'].status is StatusInfo.FAIL:
                return

            # Creating Files
            if abort.isSet():
                return
            self._create_files(perc, total, notifications, log)

            self._udpate_general_statuses()

            # Sending Files
            if self._settings['send_to_device'] and device_books is not None:
                send_files = False
                if self._settings['create_send_xray'] and self.xray_formats_not_failing_exist():
                    send_files = True
                elif (self._settings['create_send_author_profile'] and
                      self._statuses['author_profile'].status != StatusInfo.FAIL):
                    send_files = True
                elif (self._settings['create_send_start_actions'] and
                      self._statuses['start_actions'].status != StatusInfo.FAIL):
                    send_files = True
                elif self._settings['create_send_end_actions'] and self._statuses['end_actions'].status != StatusInfo.FAIL:
                    send_files = True

                if send_files:
                    notifications.put((self._calculate_percentage(perc, total),
                                       'Sending {0} files to device'.format(self.title_and_author)))
                    log('{0}    Sending files to device...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                    self._check_fmts_for_create_event(device_books)

                    if len(self._files_to_send) > 0:
                        self._send_files(device_books)
                perc += 1

    def _create_files(self, perc, total, notifications, log):
        '''Create files for create_files_event'''
        if self._settings['create_send_xray']:
            if self.xray_formats_not_failing_exist() and self._statuses['xray'].status != StatusInfo.FAIL:
                notifications.put((self._calculate_percentage(perc, total),
                                   'Parsing {0} book data'.format(self.title_and_author)))
                log('{0}    Creating x-ray...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                log('{0}        Parsing book data...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                for fmt, info in self.xray_formats_not_failing():
                    self._parse_book(fmt, info)
            perc += 1

            if self.xray_formats_not_failing_exist():
                notifications.put((self._calculate_percentage(perc, total),
                                   'Writing {0} x-ray'.format(self.title_and_author)))
                log('{0}        Writing x-ray...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                for fmt, info in self.xray_formats_not_failing():
                    self._write_xray(info)
            perc += 1

        if self._settings['create_send_author_profile']:
            if self._statuses['author_profile'].status != StatusInfo.FAIL:
                notifications.put((self._calculate_percentage(perc, total),
                                   'Writing {0} author profile'.format(self.title_and_author)))
                log('{0}    Writing author profile...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                self._write_author_profile()
            perc += 1

        if self._settings['create_send_start_actions']:
            if self._statuses['start_actions'].status != StatusInfo.FAIL:
                notifications.put((self._calculate_percentage(perc, total),
                                   'Writing {0} start actions'.format(self.title_and_author)))
                log('{0}    Writing start actions...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                self._write_start_actions()
            perc += 1

        if self._settings['create_send_end_actions']:
            if self._statuses['end_actions'].status != StatusInfo.FAIL:
                notifications.put((self._calculate_percentage(perc, total),
                                   'Writing {0} end actions'.format(self.title_and_author)))
                log('{0}    Writing end actions...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                self._write_end_actions()
            perc += 1

    def send_files_event(self, device_books, log, notifications, abort, book_num=None, total=None):
        '''Sends files to device depending on user's settings'''
        if abort.isSet():
            return

        notifications.put((self._calculate_percentage(book_num, total), self.title_and_author))
        checked_data = self._check_fmts_for_send_event(device_books)
        create_xray_format_info, create_author_profile, create_start_actions, create_end_actions = checked_data
        if create_xray_format_info or create_author_profile or create_start_actions or create_end_actions:
            log('{0}    Parsing {1} Goodreads data...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S'),
                                                              self.title_and_author))
            create_xray = True if create_xray_format_info != None else False
            self._parse_goodreads_data(create_xray=create_xray, create_author_profile=create_author_profile,
                                       create_start_actions=create_start_actions, create_end_actions=create_end_actions)
            if self._statuses['general'].status is StatusInfo.FAIL:
                return
            if create_xray and self._statuses['xray'].status != StatusInfo.FAIL:
                log('{0}    Creating {1} x-ray...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S'),
                                                          self.title_and_author))
                self._parse_book(create_xray_format_info['format'],
                                 self._xray_format_information[create_xray_format_info['format']])

                if self._xray_format_information[create_xray_format_info['format']]['status'].status != StatusInfo.FAIL:
                    self._write_xray(self._xray_format_information[create_xray_format_info['format']])

                    if os.path.exists(create_xray_format_info['local']):
                        self._files_to_send['xray'] = create_xray_format_info

            if create_author_profile and self._statuses['author_profile'].status != StatusInfo.FAIL:
                log('{0}    Creating {1} author profile...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S'),
                                                                   self.title_and_author))
                self._write_author_profile()
            if create_start_actions and self._statuses['start_actions'].status != StatusInfo.FAIL:
                log('{0}    Creating {1} start actions...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S'),
                                                                  self.title_and_author))
                self._write_start_actions()
            if create_end_actions and self._statuses['end_actions'].status != StatusInfo.FAIL:
                log('{0}    Creating {1} end actions...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S'),
                                                                self.title_and_author))
                self._write_end_actions()

        self._udpate_general_statuses()
        if len(self._files_to_send) > 0:
            log('{0}    Sending files to device...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            self._send_files(device_books)

    def _udpate_general_statuses(self):
        if self._settings['create_send_xray'] and self._statuses['xray'].status != StatusInfo.FAIL:
            self._statuses['xray'].status = StatusInfo.SUCCESS
        if self._settings['create_send_author_profile'] and self._statuses['author_profile'] != StatusInfo.FAIL:
            self._statuses['author_profile'].status = StatusInfo.SUCCESS
        if self._settings['create_send_start_actions'] and self._statuses['start_actions'] != StatusInfo.FAIL:
            self._statuses['start_actions'].status = StatusInfo.SUCCESS
        if self._settings['create_send_end_actions'] and self._statuses['start_actions'] != StatusInfo.FAIL:
            self._statuses['end_actions'].status = StatusInfo.SUCCESS

    @staticmethod
    def _calculate_percentage(amt_completed, total):
        '''Calculates percentage of amt_completed compared to total; Minimum returned is .01'''
        return amt_completed/total if amt_completed/total >= .01 else .01

    def _parse_goodreads_data(self, create_xray=None, create_author_profile=None,
                              create_start_actions=None, create_end_actions=None):
        if create_xray is None:
            create_xray = self._settings['create_send_xray']
        if create_author_profile is None:
            create_author_profile = self._settings['create_send_author_profile']
        if create_start_actions is None:
            create_start_actions = self._settings['create_send_start_actions']
        if create_end_actions is None:
            create_end_actions = self._settings['create_send_end_actions']

        try:
            goodreads_data = GoodreadsParser(self._goodreads_url, self._goodreads_conn, self._asin,
                                             expand_aliases=self._settings['expand_aliases'])
            results = goodreads_data.parse(create_xray=create_xray, create_author_profile=create_author_profile,
                                           create_start_actions=create_start_actions, create_end_actions=create_end_actions)
            compiled_xray, compiled_author_profile, compiled_start_actions, compiled_end_actions = results
        except PageDoesNotExist:
            self._statuses['general'].set(StatusInfo.FAIL, StatusInfo.F_COULD_NOT_PARSE_GOODREADS_DATA)
            return

        if create_xray:
            self._process_goodreads_xray_results(compiled_xray)
        if create_author_profile:
            self._process_goodreads_author_profile_results(compiled_author_profile)
        if create_start_actions:
            self._process_goodreads_start_actions_results(compiled_start_actions)
        if create_end_actions:
            self._process_goodreads_end_actions_results(compiled_end_actions)

    def _process_goodreads_xray_results(self, compiled_xray):
        '''Checks if goodreads sucessfully retrieved xray data; Updates status if not'''
        if compiled_xray:
            self._goodreads_xray = compiled_xray
            for char in self._goodreads_xray['characters'].values():
                if char['label'] not in self._aliases.keys():
                    self._aliases[char['label']] = char['aliases']

            self._book_settings.prefs['aliases'] = self._aliases
        else:
            self._statuses['xray'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_CREATE_XRAY)

    def _process_goodreads_author_profile_results(self, compiled_author_profile):
        '''Checks if goodreads sucessfully created author profile; Updates status if not'''
        if compiled_author_profile:
            self._goodreads_author_profile = compiled_author_profile
        else:
            self._statuses['author_profile'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_CREATE_AUTHOR_PROFILE)

    def _process_goodreads_start_actions_results(self, compiled_start_actions):
        '''Checks if goodreads sucessfully created start actions; Updates status if not'''
        if compiled_start_actions:
            self._goodreads_start_actions = compiled_start_actions
        else:
            self._statuses['start_actions'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_CREATE_START_ACTIONS)

    def _process_goodreads_end_actions_results(self, compiled_end_actions):
        '''Checks if goodreads sucessfully created start actions; Updates status if not'''
        if compiled_end_actions:
            self._goodreads_end_actions = compiled_end_actions
        else:
            self._statuses['end_actions'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_CREATE_END_ACTIONS)

    def _parse_book(self, fmt, info):
        '''Will parse book using the format info given'''
        try:
            book_parser = BookParser(fmt, info['local_book'], self._goodreads_xray, self._aliases)
            book_parser.parse()
            info['parsed_book_data'] = book_parser.parsed_data
        except MobiError:
            info['status'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_PARSE_BOOK)

    def _check_for_existing_files(self):
        '''Checks if files exist and fails for that type if they do'''
        if self._settings['create_send_xray']:
            for fmt_info in self.xray_formats_not_failing():
                info = fmt_info[1]
                if os.path.exists(os.path.join(info['local_xray'], 'XRAY.entities.{0}.asc'.format(self._asin))):
                    info['status'].set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_LOCAL_XRAY)
        if self._settings['create_send_author_profile']:
            if os.path.exists(os.path.join(self._local_book_directory, 'AuthorProfile.profile.{0}.asc'.format(self._asin))):
                self._statuses['author_profile'].set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_LOCAL_AUTHOR_PROFILE)
        if self._settings['create_send_start_actions']:
            if os.path.exists(os.path.join(self._local_book_directory, 'StartActions.data.{0}.asc'.format(self._asin))):
                self._statuses['start_actions'].set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_LOCAL_START_ACTIONS)
        if self._settings['create_send_end_actions']:
            if os.path.exists(os.path.join(self._local_book_directory, 'EndActions.data.{0}.asc'.format(self._asin))):
                self._statuses['end_actions'].set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_LOCAL_END_ACTIONS)

    def _write_xray(self, info):
        '''Writes x-ray file using goodreads and parsed book data; Will save in local directory'''
        try:
            filename = os.path.join(info['local_xray'], 'XRAY.entities.{0}.asc'.format(self._asin))
            if os.path.exists(filename):
                os.remove(filename)
        except OSError:
            info['status'].set(StatusInfo.FAIL, StatusInfo.F_REMOVE_LOCAL_XRAY)

        xray_db_writer = XRayDBWriter(info['local_xray'], self._goodreads_url, self._asin, info['parsed_book_data'])
        xray_db_writer.write_xray()

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
        except OSError:
            self._statuses['author_profile'].set(StatusInfo.FAIL, StatusInfo.F_REMOVE_LOCAL_AUTHOR_PROFILE)

        try:
            with open(os.path.join(self._local_book_directory, 'AuthorProfile.profile.{0}.asc'.format(self._asin)),
                      'w+') as author_profile:
                json.dump(self._goodreads_author_profile, author_profile)
        except OSError:
            self._statuses['author_profile'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_WRITE_AUTHOR_PROFILE)
            return

        if self._settings['send_to_device']:
            filename = 'AuthorProfile.profile.{0}.asc'.format(self._asin)
            local_file = os.path.join(self._local_book_directory, filename)
            self._files_to_send['author_profile'] = {'local': local_file, 'filename': filename}

    def _write_start_actions(self):
        '''Writes start actions file using goodreads; Will save in local directory'''
        try:
            filename = os.path.join(self._local_book_directory, 'StartActions.data.{0}.asc'.format(self._asin))
            if os.path.exists(filename):
                os.remove(filename)
        except OSError:
            self._statuses['start_actions'].set(StatusInfo.FAIL, StatusInfo.F_REMOVE_LOCAL_START_ACTIONS)

        try:
            with open(os.path.join(self._local_book_directory, 'StartActions.data.{0}.asc'.format(self._asin)),
                      'w+') as start_actions:
                json.dump(self._goodreads_start_actions, start_actions)
        except OSError:
            self._statuses['start_actions'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_WRITE_START_ACTIONS)
            return

        if self._settings['send_to_device']:
            filename = 'StartActions.data.{0}.asc'.format(self._asin)
            local_file = os.path.join(self._local_book_directory, filename)
            self._files_to_send['start_actions'] = {'local': local_file, 'filename': filename}

    def _write_end_actions(self):
        '''Writes end actions file using goodreads; Will save in local directory'''
        try:
            filename = os.path.join(self._local_book_directory, 'EndActions.data.{0}.asc'.format(self._asin))
            if os.path.exists(filename):
                os.remove(filename)
        except OSError:
            self._statuses['end_actions'].set(StatusInfo.FAIL, StatusInfo.F_REMOVE_LOCAL_END_ACTIONS)

        try:
            with open(os.path.join(self._local_book_directory, 'EndActions.data.{0}.asc'.format(self._asin)),
                      'w+') as end_actions:
                json.dump(self._goodreads_end_actions, end_actions)
        except OSError:
            self._statuses['end_actions'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_WRITE_END_ACTIONS)
            return

        if self._settings['send_to_device']:
            filename = 'EndActions.data.{0}.asc'.format(self._asin)
            local_file = os.path.join(self._local_book_directory, filename)
            self._files_to_send['end_actions'] = {'local': local_file, 'filename': filename}

    def _check_fmts_for_create_event(self, device_books):
        '''Compiles dict of file type info to use when creating files'''
        if len(device_books) == 0 or not device_books.has_key(self._book_id):
            if self._settings['create_send_xray'] and self.xray_formats_not_failing_exist():
                self._statuses['xray_send'].set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
            if (self._settings['create_send_author_profile'] and
                    self._statuses['author_profile'].status == StatusInfo.SUCCESS):
                self._statuses['author_profile_send'].set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
                if self._files_to_send.has_key('author_profile'):
                    del self._files_to_send['author_profile']
            if self._settings['create_send_start_actions'] and self._statuses['start_actions'].status == StatusInfo.SUCCESS:
                self._statuses['start_actions_send'].set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
                if self._files_to_send.has_key('start_actions'):
                    del self._files_to_send['start_actions']
            if self._settings['create_send_end_actions'] and self._statuses['end_actions'].status == StatusInfo.SUCCESS:
                self._statuses['end_actions_send'].set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
                if self._files_to_send.has_key('end_actions'):
                    del self._files_to_send['end_actions']
            return

        self._device_sdr = device_books[self._book_id][device_books[self._book_id].keys()[0]]['device_sdr']
        if not os.path.exists(self._device_sdr):
            os.mkdir(self._device_sdr)

        if self._settings['create_send_xray'] and self.xray_formats_not_failing_exist():
            # figure out which format to send
            self._check_xray_format_to_create(device_books)

    def _check_xray_format_to_create(self, device_books):
        formats_not_failing = [fmt for fmt, info in self.xray_formats_not_failing()]
        formats_on_device = device_books[self._book_id].keys()
        common_formats = list(set(formats_on_device).intersection(formats_not_failing))

        if len(common_formats) == 0:
            for fmt, info in self.xray_formats_not_failing():
                info['status'].status = StatusInfo.SUCCESS
                self._statuses['xray_send'].set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
        else:
            format_picked = self._settings['file_preference']
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

        if not device_books.has_key(self._book_id):
            if self._settings['create_send_xray']:
                self._statuses['xray_send'].set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
            if self._settings['create_send_author_profile']:
                self._statuses['author_profile_send'].set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
            if self._settings['create_send_start_actions']:
                self._statuses['start_actions_send'].set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
            if self._settings['create_send_end_actions']:
                self._statuses['end_actions_send'].set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
            return create_xray, create_author_profile, create_start_actions, create_end_actions

        self._device_sdr = device_books[self._book_id][device_books[self._book_id].keys()[0]]['device_sdr']
        if not os.path.exists(self._device_sdr):
            os.mkdir(self._device_sdr)

        if self._settings['create_send_xray']:
            # figure out which format to send
            create_xray = self._check_xray_fmt_for_send(device_books)
        if self._settings['create_send_author_profile']:
            create_author_profile = self._check_author_profile_for_send()
        if self._settings['create_send_start_actions']:
            create_start_actions = self._check_start_actions_for_send()
        if self._settings['create_send_end_actions']:
            create_end_actions = self._check_end_actions_for_send()

        return create_xray, create_author_profile, create_start_actions, create_end_actions

    def _check_xray_fmt_for_send(self, device_books):
        '''Check if there's a valid x-ray to send'''
        formats_not_failing = [fmt for fmt, info in self._xray_format_information.items()]
        formats_on_device = device_books[self._book_id].keys()
        common_formats = list(set(formats_on_device).intersection(formats_not_failing))

        if len(common_formats) == 0:
            for fmt, info in self._xray_format_information.items():
                info['status'].status = StatusInfo.SUCCESS
                self._statuses['xray_send'].set(StatusInfo.FAIL, StatusInfo.F_BOOK_NOT_ON_DEVICE)
        else:
            format_picked = self._settings['file_preference']
            if len(common_formats) == 1:
                format_picked = common_formats[0]

            filename = 'XRAY.entities.{0}.asc'.format(self._asin)
            local_file = os.path.join(self._xray_format_information[format_picked]['local_xray'], filename)
            if os.path.exists(os.path.join(self._device_sdr, filename)) and not self._settings['overwrite_when_sending']:
                self._statuses['xray_send'].set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_DEVICE_XRAY)
            else:
                if os.path.exists(local_file):
                    self._files_to_send['xray'] = {'local': local_file, 'filename': filename, 'format': format_picked}
                else:
                    if not self._settings['create_files_when_sending']:
                        self._statuses['xray_send'].set(StatusInfo.FAIL, StatusInfo.F_PREFS_SET_TO_NOT_CREATE_XRAY)
                    else:
                        return {'local': local_file, 'filename': filename, 'format': format_picked}
        return None

    def _check_author_profile_for_send(self):
        '''Check if there's a valid author profile to send'''
        filename = 'AuthorProfile.profile.{0}.asc'.format(self._asin)
        local_file = os.path.join(self._local_book_directory, filename)
        if os.path.exists(os.path.join(self._device_sdr, filename)) and not self._settings['overwrite_when_sending']:
            self._statuses['author_profile_send'].set(StatusInfo.FAIL,
                                                      StatusInfo.F_PREFS_NOT_OVERWRITE_DEVICE_AUTHOR_PROFILE)
        else:
            if os.path.exists(local_file):
                self._files_to_send['author_profile'] = {'local': local_file, 'filename': filename}
            else:
                if not self._settings['create_files_when_sending']:
                    self._statuses['author_profile_send'].set(StatusInfo.FAIL, StatusInfo.F_PREFS_SET_TO_NOT_CREATE_XRAY)
                else:
                    return True
        return False

    def _check_start_actions_for_send(self):
        '''Check if there's a valid start actions file to send'''
        filename = 'StartActions.data.{0}.asc'.format(self._asin)
        local_file = os.path.join(self._local_book_directory, filename)
        if os.path.exists(os.path.join(self._device_sdr, filename)) and not self._settings['overwrite_when_sending']:
            self._statuses['start_actions_send'].set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_DEVICE_START_ACTIONS)
        else:
            if os.path.exists(local_file):
                self._files_to_send['start_actions'] = {'local': local_file, 'filename': filename}
            else:
                if not self._settings['create_files_when_sending']:
                    self._statuses['start_actions_send'].set(StatusInfo.FAIL, StatusInfo.F_PREFS_SET_TO_NOT_CREATE_XRAY)
                else:
                    return True
        return False

    def _check_end_actions_for_send(self):
        '''Check if there's a valid end actions file to send'''
        filename = 'EndActions.data.{0}.asc'.format(self._asin)
        local_file = os.path.join(self._local_book_directory, filename)
        if os.path.exists(os.path.join(self._device_sdr, filename)) and not self._settings['overwrite_when_sending']:
            self._statuses['end_actions_send'].set(StatusInfo.FAIL, StatusInfo.F_PREFS_NOT_OVERWRITE_DEVICE_END_ACTIONS)
        else:
            if os.path.exists(local_file):
                self._files_to_send['end_actions'] = {'local': local_file, 'filename': filename}
            else:
                if not self._settings['create_files_when_sending']:
                    self._statuses['end_actions_send'].set(StatusInfo.FAIL, StatusInfo.F_PREFS_SET_TO_NOT_CREATE_XRAY)
                else:
                    return True
        return False

    def _send_files(self, device_books):
        '''Sends files to device depending on list compiled in self._files_to_send'''
        number_of_failed_asin_updates = 0
        formats_on_device = device_books[self._book_id].keys()
        try:
            for fmt in formats_on_device:
                with open(device_books[self._book_id][fmt]['device_book'], 'r+b') as stream:
                    mobi_updater = ASINUpdater(stream)
                    mobi_updater.update(self._asin)
        except MobiError:
            number_of_failed_asin_updates += 1
            if (self._settings['create_send_xray'] and self._settings['send_to_device'].has_key('xray') and
                    fmt == self._settings['send_to_device']['xray']['format']):
                self._statuses['xray_send'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_UPDATE_ASIN)
                self._xray_send_fmt = self._files_to_send['xray']['format']
                if self._files_to_send.has_key('xray'):
                    del self._files_to_send['xray']
            if number_of_failed_asin_updates == len(formats_on_device):
                if self._settings['create_send_author_profile']:
                    self._statuses['author_profile_send'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_UPDATE_ASIN)
                if self._settings['create_send_start_actions']:
                    self._statuses['start_actions_send'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_UPDATE_ASIN)
                if self._settings['create_send_end_actions']:
                    self._statuses['end_actions_send'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_UPDATE_ASIN)
                return

        # temporarily rename current file in case send fails
        for filetype, info in self._files_to_send.items():
            self._send_file(filetype, info['filename'], info['local'])

    def _send_file(self, filetype, filename, local_dir):
        '''Send file to device and update status accordingly'''
        device_filename = os.path.join(self._device_sdr, filename)
        if os.path.exists(device_filename):
            os.rename(device_filename, '{0}.old'.format(device_filename))
        copy(local_dir, self._device_sdr)

        if os.path.exists(device_filename):
            if os.path.exists('{0}.old'.format(device_filename)):
                os.remove('{0}.old'.format(device_filename))
            if filetype == 'xray':
                self._statuses['xray_send'].status = StatusInfo.SUCCESS
                self._xray_send_fmt = self._files_to_send['xray']['format']
            elif filetype == 'author_profile':
                self._statuses['author_profile_send'].status = StatusInfo.SUCCESS
            elif filetype == 'start_actions':
                self._statuses['start_actions_send'].status = StatusInfo.SUCCESS
            elif filetype == 'end_actions':
                self._statuses['end_actions_send'].status = StatusInfo.SUCCESS
        else:
            os.rename('{0}.old'.format(device_filename), device_filename)
            if filetype == 'xray':
                self._statuses['xray_send'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_SEND_XRAY)
                self._xray_send_fmt = self._xray_send_fmt
            elif filetype == 'author_profile':
                self._statuses['author_profile_send'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_SEND_AUTHOR_PROFILE)
            elif filetype == 'start_actions':
                self._statuses['start_actions_send'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_SEND_START_ACTIONS)
            elif filetype == 'end_actions':
                self._statuses['end_actions_send'].set(StatusInfo.FAIL, StatusInfo.F_UNABLE_TO_SEND_END_ACTIONS)

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
