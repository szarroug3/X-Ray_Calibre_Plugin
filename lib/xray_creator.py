# xray_creator.py
'''Runs functions specified by user for file creation and sending'''

import os
import sys
import errno

from datetime import datetime
from collections import defaultdict

from calibre.customize.ui import device_plugins
from calibre.devices.scanner import DeviceScanner
from calibre_plugins.xray_creator.lib.status_info import StatusInfo

class XRayCreator(object):
    '''Automates x-ray, author profile, start actions, and end actions creation and sending to device'''
    def __init__(self, books, send_to_device, overwrite_local, overwrite_device, create_send_xray,
                 create_send_author_profile, create_send_start_actions, create_send_end_actions):
        self._books = books
        self._send_to_device = send_to_device
        self._overwrite_local = overwrite_local
        self._overwrite_device = overwrite_device
        self._create_send_xray = create_send_xray
        self._create_send_author_profile = create_send_author_profile
        self._create_send_start_actions = create_send_start_actions
        self._create_send_end_actions = create_send_end_actions
        self._num_of_formats_found_on_device = -1

        self._total_not_failing = None

    @property
    def books(self):
        return self._books

    def _initialize_books(self, log, database):
        self._total_not_failing = 0
        book_lookup = {}
        duplicate_uuids = []
        for book in self.books_not_failing():
            self._total_not_failing += 1
            uuid = database.field_for('uuid', book.book_id)
            if book_lookup.has_key(uuid):
                book.status.set(StatusInfo.FAIL, 'This book has the same UUID as another.')
                if uuid not in duplicate_uuids:
                    duplicate_uuids.append(uuid)
                continue
            book_lookup[uuid] = book
        for uuid in duplicate_uuids:
            book_lookup[uuid].status.set(StatusInfo.FAIL, 'This book has the same UUID as another.')
            book_lookup.pop(uuid)
        return self._find_device_books(book_lookup, log)

    def books_not_failing(self):
        '''Gets books that didn't fail'''
        for book in self._books:
            if book.status.status is not StatusInfo.FAIL:
                yield book

    def get_results_create(self):
        '''Gets create results'''
        create_completed = []
        create_failed = []

        for book in self._books:
            if book.status.status == StatusInfo.FAIL:
                known_info = self._get_general_create_results(book)
                if not known_info:
                    known_info = 'Unknown book'
                create_failed.append('{0}: {1}'.format(known_info, book.status.message))
                continue

            fmts_completed = []
            fmts_failed = []
            if self._create_send_xray:
                self._get_xray_create_results(book, fmts_failed, fmts_completed)
            if self._create_send_author_profile:
                self._get_author_profile_create_results(book, fmts_failed, fmts_completed)
            if self._create_send_start_actions:
                self._get_start_actions_create_results(book, fmts_failed, fmts_completed)
            if self._create_send_end_actions:
                self._get_end_actions_create_results(book, fmts_failed, fmts_completed)

            if len(fmts_completed) > 0:
                create_completed.append('{0}: {1}'.format(book.title_and_author, ', '.join(fmts_completed)))
            if len(fmts_failed) > 0:
                create_failed.append('{0}:'.format(book.title_and_author))
                for fmt_info in fmts_failed:
                    create_failed.append('    {0}'.format(fmt_info))
        return create_completed, create_failed

    @staticmethod
    def _get_general_create_results(book):
        '''Processes basic create results'''
        if book.title and book.author:
            known_info = book.title_and_author
        elif book.title:
            known_info = book.title
        elif book.author:
            known_info = 'Book by {0}'.format(book.author)

        return known_info

    @staticmethod
    def _get_xray_create_results(book, fmts_failed, fmts_completed):
        '''Processes xray create results'''
        if book.xray_status.status == StatusInfo.FAIL:
            fmts_failed.append('X-Ray: {0}'.format(book.xray_status.message))
        else:
            for fmt, info in book.xray_formats_failing():
                fmts_failed.append('X-Ray ({0}): {1}'.format(fmt, info['status'].message))
            if book.xray_formats_not_failing_exist():
                completed_xray_formats = [fmt for fmt, info in book.xray_formats_not_failing()]
                fmts_completed.append('X-Ray ({0})'.format(', '.join(completed_xray_formats)))

    @staticmethod
    def _get_author_profile_create_results(book, fmts_failed, fmts_completed):
        '''Processes author profile create results'''
        if book.author_profile_status.status == StatusInfo.FAIL:
            fmts_failed.append('Author Profile: {0}'.format(book.author_profile_status.message))
        else:
            fmts_completed.append('Author Profile')

    @staticmethod
    def _get_start_actions_create_results(book, fmts_failed, fmts_completed):
        '''Processes start actions create results'''
        if book.start_actions_status.status == StatusInfo.FAIL:
            fmts_failed.append('Start Actions: {0}'.format(book.start_actions_status.message))
        else:
            fmts_completed.append('Start Actions')

    @staticmethod
    def _get_end_actions_create_results(book, fmts_failed, fmts_completed):
        '''Processes end actions create results'''
        if book.end_actions_status.status == StatusInfo.FAIL:
            fmts_failed.append('End Actions: {0}'.format(book.end_actions_status.message))
        else:
            fmts_completed.append('End Actions')

    def get_results_send(self):
        '''Gets send results'''
        send_completed = []
        send_failed = []
        for book in self._books:
            if book.status.status is StatusInfo.FAIL:
                send_failed.append('{0}: {1}'.format(book.title_and_author, book.status.message))
                continue
            fmts_completed = []
            fmts_failed = []
            if self._create_send_xray:
                self._get_xray_send_results(book, fmts_failed, fmts_completed)

            if self._create_send_author_profile:
                self._get_author_profile_send_results(book, fmts_failed, fmts_completed)
            if self._create_send_start_actions:
                self._get_start_actions_send_results(book, fmts_failed, fmts_completed)
            if self._create_send_end_actions:
                self._get_end_actions_send_results(book, fmts_failed, fmts_completed)

            if len(fmts_completed) > 0:
                send_completed.append('{0}: {1}'.format(book.title_and_author, ', '.join(fmts_completed)))
            if len(fmts_failed) > 0:
                send_failed.append('{0}:'.format(book.title_and_author))
                for fmt_info in fmts_failed:
                    send_failed.append('    {0}'.format(fmt_info))
        return send_completed, send_failed

    @staticmethod
    def _get_xray_send_results(book, fmts_failed, fmts_completed):
        '''Processes xray send results'''
        if book.xray_status.status != StatusInfo.FAIL:
            if book.xray_send_status.status == StatusInfo.FAIL:
                if book.xray_send_fmt != None:
                    fmts_failed.append('X-Ray ({0}): {1}'.format(book.xray_send_fmt, book.xray_send_status.message))
                else:
                    fmts_failed.append('X-Ray: {0}'.format(book.xray_send_status.message))
            else:
                fmts_completed.append('X-Ray ({0})'.format(book.xray_send_fmt))
        else:
            fmts_failed.append('X-Ray: {0}'.format(book.xray_status.message))

    @staticmethod
    def _get_author_profile_send_results(book, fmts_failed, fmts_completed):
        '''Processes author send profile results'''
        if book.author_profile_status.status != StatusInfo.FAIL:
            if book.author_profile_send_status.status == StatusInfo.FAIL:
                fmts_failed.append('Author Profile: {0}'.format(book.author_profile_send_status.message))
            else:
                fmts_completed.append('Author Profile')
        else:
            fmts_failed.append('Author Profile: {0}'.format(book.author_profile_status.message))

    @staticmethod
    def _get_start_actions_send_results(book, fmts_failed, fmts_completed):
        '''Processes start action send results'''
        if book.start_actions_status.status != StatusInfo.FAIL:
            if book.start_actions_send_status.status == StatusInfo.FAIL:
                fmts_failed.append('Start Actions: {0}'.format(book.start_actions_send_status.message))
            else:
                fmts_completed.append('Start Actions')
        else:
            fmts_failed.append('Start Actions: {0}'.format(book.start_actions_status.message))

    @staticmethod
    def _get_end_actions_send_results(book, fmts_failed, fmts_completed):
        '''Processes end action send results'''
        if book.end_actions_status.status != StatusInfo.FAIL:
            if book.end_actions_send_status.status == StatusInfo.FAIL:
                fmts_failed.append('End Actions: {0}'.format(book.end_actions_send_status.message))
            else:
                fmts_completed.append('End Actions')
        else:
            fmts_failed.append('End Actions: {0}'.format(book.end_actions_status.message))

    def _find_device_books(self, book_lookup, log):
        '''Look for the Kindle and return the list of books on it'''
        dev = None
        scanner = DeviceScanner()
        scanner.scan()
        connected_devices = []
        for device in device_plugins():
            dev_connected = scanner.is_device_connected(device)
            if isinstance(dev_connected, tuple):
                device_ok, det = dev_connected
                if device_ok:
                    dev = device
                    connected_devices.append((det, dev))

        if dev is None:
            return None

        for det, device in connected_devices:
            try:
                device.open(det, None)
            except (NotImplementedError, TypeError):
                continue
            else:
                dev = device
                break

        self._num_of_formats_found_on_device = 0
        try:
            books = defaultdict(dict)
            for book in dev.books():
                if book_lookup.has_key(book._data['uuid']):
                    book_id = book_lookup[book._data['uuid']].book_id
                    fmt = book.path.split('.')[-1].lower()
                    if (fmt != 'mobi' and fmt != 'azw3') or fmt not in self._formats:
                        continue
                    books[book_id][fmt] = {'device_book': book.path,
                                           'device_sdr': '.'.join(book.path.split('.')[:-1]) + '.sdr'}
                    self._num_of_formats_found_on_device += 1
            return books
        except (TypeError, AttributeError):
            self._num_of_formats_found_on_device = -1
            log(('{0} Device found but cannot be accessed. '
                 'It may have been ejected but not unplugged.').format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            return None

    @staticmethod
    def _find_device_root(device_book):
        '''
        Given the full path to a book on the device, return the path to the Kindle device

        eg. "C:\", "/Volumes/Kindle"
        '''
        device_root = None

        if sys.platform == "win32":
            device_root = os.path.join(device_book.split(os.sep)[0], os.sep)
        elif sys.platform == "darwin" or "linux" in sys.platform:
            # Find "documents" in path hierarchy, we want to include the first os.sep so slice one further than we find it
            index = device_book.index("%sdocuments%s" % (os.sep, os.sep))
            device_root = device_book[:index+1]
        else:
            raise EnvironmentError(errno.EINVAL, "Unknown platform %s" % (sys.platform))
        magic_file = os.path.join(device_root, "system", "version.txt")
        if os.path.exists(magic_file) and open(magic_file).readline().startswith("Kindle"):
            return device_root
        raise EnvironmentError(errno.ENOENT, "Kindle device not found (%s)" % (device_root))

    def create_files_event(self, database, abort, log, notifications):
        '''Creates files depending on users settings'''
        log('\n%s Initializing...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        notifications.put((0.01, 'Initializing...'))
        device_books = self._initialize_books(log, database)

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
        total_not_failing_actions = self._total_not_failing * actions
        for book_num, book in enumerate(self.books_not_failing()):
            if abort.isSet():
                return
            log('%s %s' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S'), book.title_and_author))
            book.create_files_event(device_books, book_num * actions, total_not_failing_actions, log,
                                    notifications, abort)

        self.print_create_results(log, device_books)

    def print_create_results(self, log, device_books):
        '''Gets and prints create results'''
        create_completed, create_failed = self.get_results_create()
        log('\nFile Creation:')
        if len(create_completed) > 0:
            log('    Books Completed:')
            for line in create_completed:
                log('        %s' % line)
        if len(create_failed) > 0:
            log('    Books Failed:')
            for line in create_failed:
                log('        %s' % line)

        if self._send_to_device:
            if device_books is None:
                log('\nX-Ray Sending:')
                log('    No device is connected.')
            else:
                send_completed, send_failed = self.get_results_send()
                if len(send_completed) > 0 or len(send_failed) > 0:
                    log('\nX-Ray Sending:')
                    if len(send_completed) > 0:
                        log('    Books Completed:')
                        for line in send_completed:
                            log('        %s' % line)
                    if len(send_failed) > 0:
                        log('    Books Failed:')
                        for line in send_failed:
                            log('        %s' % line)

    def send_files_event(self, database, abort, log, notifications):
        '''Sends files depending on users settings'''
        log('\n%s Initializing...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        notifications.put((0.01, 'Initializing...'))
        device_books = self._initialize_books(log, database)

        # something went wrong; we've already printed a message
        if self._num_of_formats_found_on_device == -1:
            notifications.put((100, ' Unable to send files.'))
            log('{0} No device is connected.'.format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            return
        if self._num_of_formats_found_on_device == 0:
            notifications.put((100, ' Unable to send files.'))
            log(('{0} No matching books found on device. '
                 'It may have been ejected but not unplugged.').format(datetime.now().strftime('%m-%d-%Y %H:%M:%S')))
            return

        for book_num, book in enumerate(self.books_not_failing()):
            if abort.isSet():
                return
            log('%s %s' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S'), book.title_and_author))
            book.send_files_event(device_books, log, notifications, abort, book_num=float(book_num),
                                  total=self._total_not_failing)

        send_completed, send_failed = self.get_results_send()
        if len(send_completed) > 0:
            log('\nBooks Completed:')
            for line in send_completed:
                log('    %s' % line)
        if len(send_failed) > 0:
            log('\nBooks Failed:')
            for line in send_failed:
                log('    %s' % line)
