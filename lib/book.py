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
    FAILED_BASIC_INFORMATION_MISSING = 'Missing title and/or author.'
    FAILED_COULD_NOT_FIND_ASIN = 'Could not find ASIN.'
    FAILED_COULD_NOT_FIND_GOODREADS_PAGE = 'Could not find Goodreads page.'
    FAILED_LOCAL_BOOK_NOT_FOUND = 'Local book not found.'
    FAILED_COULD_NOT_PARSE_GOODREADS_DATA = 'Could not parse Goodreads data.'
    FAILED_UNABLE_TO_PARSE_BOOK = 'Unable to parse book.'
    FAILED_REMOVE_LOCAL_XRAY = 'Unable to remove local x-ray.'
    FAILED_UNABLE_TO_WRITE_XRAY = 'Unable to write x-ray.'
    FAILED_UNABLE_TO_SEND_XRAY = 'Unable to send x-ray.'
    FAILED_REMOVE_LOCAL_AUTHOR_PROFILE = 'Unable to remove local author profile.'
    FAILED_UNABLE_TO_WRITE_AUTHOR_PROFILE = 'Unable to write author profile.'
    FAILED_UNABLE_TO_SEND_AUTHOR_PROFILE = 'Unable to send author profile.'
    FAILED_REMOVE_LOCAL_START_ACTIONS = 'Unable to remove local start actions.'
    FAILED_UNABLE_TO_WRITE_START_ACTIONS = 'Unable to write start actions.'
    FAILED_UNABLE_TO_SEND_START_ACTIONS = 'Unable to send start actions.'
    FAILED_REMOVE_LOCAL_END_ACTIONS = 'Unable to remove local end actions.'
    FAILED_UNABLE_TO_WRITE_END_ACTIONS = 'Unable to write end actions.'
    FAILED_UNABLE_TO_SEND_END_ACTIONS = 'Unable to send end actions.'
    FAILED_BOOK_NOT_ON_DEVICE = 'None of the passing formats are on the device.'

    # not used yet
    FAILED_UNABLE_TO_UPDATE_ASIN = 'Unable to update ASIN in book on device.'
    FAILED_PREFERENCES_SET_TO_NOT_CREATE_XRAY = 'No local x-ray found. Your preferences are set to not create one if one is not already found when sending to device.'
    FAILED_FAILED_TO_SEND_XRAY = 'Could not send x-ray to device.'

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
    def xray_send_status(self):
        return self._xray_send_status

    @property
    def xray_send_status_message(self):
        return self._xray_send_status_message

    @property
    def xray_sent_fmt(self):
        return self._xray_sent_fmt

    @property
    def author_profile_status(self):
        return self._author_profile_status

    @property
    def author_profile_status_message(self):
        return self._author_profile_status_message

    @property
    def author_profile_send_status(self):
        return self._author_profile_status

    @property
    def author_profile_send_status_message(self):
        return self._author_profile_status_message

    @property
    def start_actions_status(self):
        return self._start_actions_status

    @property
    def start_actions_status_message(self):
        return self._start_actions_status_message

    @property
    def start_actions_send_status(self):
        return self._start_actions_status

    @property
    def start_actions_send_status_message(self):
        return self._start_actions_status_message

    @property
    def end_actions_status(self):
        return self._end_actions_status

    @property
    def end_actions_status_message(self):
        return self._end_actions_status_message
        
    @property
    def end_actions_send_status(self):
        return self._end_actions_status

    @property
    def end_actions_send_status_message(self):
        return self._end_actions_status_message
    
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
        for fmt, info in self._xray_format_information.items():
            if info['status'] is self.FAIL:
                yield (fmt, info)

    def xray_formats_not_failing(self):
        for fmt, info in self._xray_format_information.items():
            if info['status'] is not self.FAIL:
                yield (fmt, info)

    def xray_formats_not_failing_exist(self):
        return any(self.xray_formats_not_failing())

    def xray_formats_failing_exist(self):
        return any(self.xray_formats_failing())

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
        self._xray_format_information = {}

        for fmt in self._formats:
            info = {'status': self.IN_PROGRESS, 'status_message': None}

            # find local book if it exists; fail if it doesn't
            local_book = self._db.format_abspath(self._book_id, fmt.upper())
            if not local_book or not os.path.exists(local_book):
                info['status'] = self.FAIL
                info['status_message'] = self.FAILED_LOCAL_BOOK_NOT_FOUND
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
            # Prep
            if abort and abort.isSet():
                return
            if notifications: notifications.put((perc/(total * actions), 'Parsing {0} Goodreads data'.format(self.title_and_author)))
            if log: log('{0}    Parsing Goodreads data...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            self._parse_goodreads_data()
            perc += 1
            if self._status is self.FAIL:
                return

            # Creating Files
            if abort and abort.isSet():
                return
            if self._create_send_xray and self.xray_formats_not_failing_exist():
                if notifications: notifications.put((perc/(total * actions), 'Parsing {0} book data'.format(self.title_and_author)))
                if log: log('{0}    Creating x-ray...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                if log: log('{0}        Parsing book data...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                for fmt, info in self.xray_formats_not_failing():
                    self._parse_book(fmt, info)
                perc += 1

                if self.xray_formats_not_failing_exist():
                    if notifications: notifications.put((perc/(total * actions), 'Writing {0} x-ray'.format(self.title_and_author)))
                    if log: log('{0}        Writing x-ray...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                    for fmt, info in self.xray_formats_not_failing():
                        self._write_xray(info)
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

            # Sending Files
            if self._send_to_device and device_books is not None:
                if abort and abort.isSet():
                    return
                file_to_send_count = 0
                if self._create_send_xray and self.xray_formats_not_failing_exist(): file_to_send_count += 1
                if self._create_send_author_profile and self._author_profile_status != self.FAIL: file_to_send_count += 1
                if self._create_send_start_actions and self._start_actions_status != self.FAIL: file_to_send_count += 1
                if self._create_send_end_actions and self._end_actions_status != self.FAIL: file_to_send_count += 1

                if file_to_send_count > 0:
                    if notifications: notifications.put((perc/(total * actions), 'Sending {0} files to device'.format(self.title_and_author)))
                    if log: log('{0}    Sending files to device...'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
                    self._send_xray(device_books)
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

    def _parse_book(self, fmt, info):
        try:
            book_parser = BookParser(fmt, info['local_book'], self._goodreads_xray, self._aliases)
            book_parser.parse()
            info['parsed_book_data'] = book_parser.parsed_data
        except:
            info['status'] = self.FAIL
            info['status_message'] = self.FAILED_UNABLE_TO_PARSE_BOOK

    def _write_xray(self, info, remove_files_from_dir=True):
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

        if not os.path.exists(os.path.join(info['local_xray'], 'XRAY.entities.{0}.asc'.format(self._asin))):
            info['status'] = self.FAIL
            info['status_message'] = self.FAILED_UNABLE_TO_WRITE_XRAY
            return            

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

    def _send_xray(self, device_books):
        files_to_send = {}
        if len(device_books[self._book_id].keys()) == 0:
            if self._create_send_xray:
                for fmt, info in self.xray_formats_not_failing():
                    if info['status'] == self.SUCCESS:
                        self._xray_send_status = self.FAIL
                        self._xray_send_status_message = self.FAILED_BOOK_NOT_ON_DEVICE
            if self._create_send_author_profile and self._author_profile_status == self.SUCCESS:
                self._author_profile_send_status = self.FAIL
                self._author_profile_send_status_message = self.FAILED_BOOK_NOT_ON_DEVICE
            if self._create_send_start_actions and self._start_actions_status == self.SUCCESS:
                self._start_actions_send_status = self.FAIL
                self._start_actions_send_status_message = self.FAILED_BOOK_NOT_ON_DEVICE
            if self._create_send_end_actions and self._end_actions_status == self.SUCCESS:
                self._end_actions_send_status = self.FAIL
                self._end_actions_send_status_message = self.FAILED_BOOK_NOT_ON_DEVICE
            return

        device_sdr = device_books[self._book_id][device_books[self._book_id].keys()[0]]['device_sdr']
        if not os.path.exists(device_sdr):
            os.mkdir(device_sdr)

        formats_on_device = device_books[self._book_id].keys()

        if self._create_send_xray and self.xray_formats_not_failing_exist():
            # figure out which format to send
            formats_not_failing = [fmt for fmt, info in self.xray_formats_not_failing()]
            common_formats = list(set(formats_on_device).intersection(formats_not_failing))

            if len(common_formats) == 0:
                for fmt, info in self.xray_formats_not_failing():
                    info['status'] = self.SUCCESS
                    self._xray_send_status = self.FAIL
                    self._xray_send_status_message = self.FAILED_BOOK_NOT_ON_DEVICE
            else:
                format_picked = self._file_preference
                if len(common_formats) == 1:
                    format_picked = common_formats[0]

                for fmt, info in self.xray_formats_not_failing():
                    if fmt != format_picked:
                        info['status'] = self.SUCCESS
                        continue

                    filename = 'XRAY.entities.{0}.asc'.format(self._asin)
                    local_file = os.path.join(info['local_xray'], filename)
                    device_file = os.path.join(device_sdr, filename)
                    files_to_send['xray'] = {'local': local_file, 'device': device_file}

        if self._create_send_author_profile and self._author_profile_status == self.SUCCESS:
                filename = 'AuthorProfile.profile.{0}.asc'.format(self._asin)
                local_file = os.path.join(self._local_book_directory, filename)
                device_file = os.path.join(device_sdr, filename)
                files_to_send['author_profile'] = {'local': local_file, 'device': device_file}

        if self._create_send_start_actions and self._start_actions_status == self.SUCCESS:
                filename = 'StartActions.data.{0}.asc'.format(self._asin)
                local_file = os.path.join(self._local_book_directory, filename)
                device_file = os.path.join(device_sdr, filename)
                files_to_send['start_actions'] = {'local': local_file, 'device': device_file}

        if self._create_send_end_actions and self._end_actions_status == self.SUCCESS:
                filename = 'EndActions.data.{0}.asc'.format(self._asin)
                local_file = os.path.join(self._local_book_directory, filename)
                device_file = os.path.join(device_sdr, filename)
                files_to_send['end_actions'] = {'local': local_file, 'device': device_file}

        if len(files_to_send) == 0:
            return

        number_of_failed_asin_updates = 0
        try:
            for fmt in formats_on_device:
                with open(device_books[self._book_id][fmt]['device_book'], 'r+b') as stream:
                    mu = ASINUpdater(stream)
                    mu.update(self._asin)
        except:
            number_of_failed_asin_updates += 1
            if self._create_send_xray and fmt == format_picked:
                self._xray_send_status = self.FAIL
                self._xray_send_status_message = self.FAILED_UNABLE_TO_UPDATE_ASIN
                self._xray_sent_fmt = format_picked
                if files_to_send.has_key('xray'): del files_to_send['xray']
            if number_of_failed_asin_updates == len(formats_on_device):
                if self._create_send_author_profile:
                    self._author_profile_send_status = self.FAIL
                    self._author_profile_send_status_message = self.FAILED_UNABLE_TO_UPDATE_ASIN
                if self._create_send_start_actions:
                    self._start_actions_send_status = self.FAIL
                    self._start_actions_send_status_message = self.FAILED_UNABLE_TO_UPDATE_ASIN
                if self._create_send_end_actions:
                    self._end_actions_send_status = self.FAIL
                    self._end_actions_send_status_message = self.FAILED_UNABLE_TO_UPDATE_ASIN
                return

        # temporarily rename current file in case send fails
        for filetype, info in files_to_send.items():
            if os.path.exists(info['device']):
                os.rename(info['device'], '{0}.old'.format(info['device']))
            copy(info['local'], device_sdr)

            if os.path.exists(info['device']):
                if os.path.exists('{0}.old'.format(info['device'])):
                    os.remove('{0}.old'.format(info['device']))
                if filetype == 'xray':
                    self._xray_send_status = self.SUCCESS
                    self._xray_sent_fmt = format_picked
                elif filetype == 'author_profile':
                    self._author_profile_send_status = self.SUCCESS
                elif filetype == 'start_actions':
                    self._start_actions_send_status = self.SUCCESS
                elif filetype == 'end_actions':
                    self._end_actions_send_status = self.SUCCESS
            else:
                os.rename('{0}.old'.format(info['device']), info['device'])
                if filetype == 'xray':
                    self._xray_send_status = self.FAIL
                    self._xray_send_status_message = self.FAILED_UNABLE_TO_SEND_XRAY
                    self._xray_sent_fmt = format_picked
                elif filetype == 'author_profile':
                    self._author_profile_send_status = self.FAIL
                    self._author_profile_send_status_message = self.FAILED_UNABLE_TO_SEND_AUTHOR_PROFILE
                elif filetype == 'start_actions':
                    self._start_actions_send_status = self.FAIL
                    self._start_actions_send_status_message = self.FAILED_UNABLE_TO_SEND_START_ACTIONS
                elif filetype == 'end_actions':
                    self._end_actions_send_status = self.FAIL
                    self._end_actions_send_status_message = self.FAILED_UNABLE_TO_SEND_END_ACTIONS

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
            return

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

        return