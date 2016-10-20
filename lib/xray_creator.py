# xray_creator.py

import os
import sys
import errno

from datetime import datetime
from httplib import HTTPSConnection

from calibre import get_proxies
from calibre.customize.ui import device_plugins
from calibre.devices.scanner import DeviceScanner
from calibre_plugins.xray_creator.lib.book import Book

class XRayCreator(object):
    HEADERS = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/html", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0"}

    def __init__(self, db, book_ids, formats, send_to_device, create_xray, expand_aliases, send_author_profile, send_end_actions):
        self._db = db
        self._book_ids = book_ids
        self._formats = formats
        self._send_to_device = send_to_device
        self._create_xray = create_xray
        self._expand_aliases = expand_aliases
        self._send_author_profile = send_author_profile
        self._send_end_actions = send_end_actions

    @property
    def books(self):
        return self._books
    
    def _initialize_books(self, log):
        https_proxy = get_proxies(debug=False).get('https', None)
        if https_proxy:
            https_address = ':'.join(https_proxy.split(':')[:-1])
            https_port = int(https_proxy.split(':')[-1])
            goodreads_conn = HTTPSConnection(https_address, https_port)
            goodreads_conn.set_tunnel('www.goodreads.com', 443)
            amazon_conn = HTTPSConnection(https_address, https_port)
            amazon_conn.set_tunnel('www.amazon.com', 443)
        else:
            goodreads_conn = HTTPSConnection('www.goodreads.com')
            amazon_conn = HTTPSConnection('www.amazon.com')

        self._books = []
        for book_id in self._book_ids:
            self._books.append(Book(self._db, book_id, goodreads_conn, amazon_conn, self._formats,
                self._send_to_device, self._create_xray, self._expand_aliases, self._send_author_profile,
                self._send_end_actions))
        
        self._total_not_failing = 0
        book_lookup = {}
        duplicate_uuids = []
        for book in self.books_not_failing():
            self._total_not_failing += 1
            uuid = self._db.field_for('uuid', book.book_id)
            if book_lookup.has_key(uuid):
                book._status = book.FAIL
                book._status_message = book.FAILED_DUPLICATE_UUID
                if uuid not in duplicate_uuids:
                    duplicate_uuids.append(uuid)
                continue
            book_lookup[uuid] = book
        for uuid in duplicate_uuids:
            book_lookup[uuid]._status = book.FAIL
            book_lookup[uuid]._status_message = book.FAILED_DUPLICATE_UUID
            book_lookup.pop(uuid)
        self._device_books = self._find_device_books(book_lookup, log)

    def books_not_failing(self):
        for book in self._books:
            if book.status is not book.FAIL:
                yield book

    def get_results_create(self):
        self._create_completed = []
        self._create_failed = []

        for book in self._books:
            if book.status is book.FAIL:
                if book.title and book.author:
                    known_info = book.title_and_author
                elif book.title:
                    known_info = book.title
                elif book.author:
                    known_info = 'Book by %s' % book.author
                elif not known_info:
                    known_info = 'Unknown book'
                self._create_failed.append('%s: %s' %  (known_info, book.status_message))
                continue
            fmts_completed = []
            fmts_failed = []
            for info in book.format_specific_info:
                if info['status'] is book.FAIL:
                    fmts_failed.append(info)
                else:
                    fmts_completed.append(info['format'])
            if len(fmts_completed) > 0:
                self._create_completed.append('%s: %s' % (book.title_and_author, ', '.join(fmts_completed)))
            if len(fmts_failed) > 0:
                self._create_failed.append('%s:' % book.title_and_author)
                for fmt in fmts_failed:
                    self._create_failed.append('\t%s: %s' % (fmt['format'], fmt['status_message']))

    def get_results_send(self):
        self._send_completed = []
        self._send_failed = []
        for book in self._books:
            if book.status is book.FAIL:
                self._send_failed.append('%s: %s' % (book.title_and_author, book.status_message))
                continue
            if book.format_specific_info:
                fmts_completed = []
                fmts_failed = []
                for info in book.formats_not_failing():
                    if info['send_status'] is book.FAIL:
                        fmts_failed.append(info)
                    else:
                        fmts_completed.append(info['format'])

                if len(fmts_completed) > 0:
                    self._send_completed.append('%s: %s' % (book.title_and_author, ', '.join(fmts_completed)))
                if len(fmts_failed) > 0:
                    self._send_failed.append('%s:' % book.title_and_author)
                    for fmt in fmts_failed:
                        self._send_failed.append('\t%s: %s' % (fmt['format'], fmt['status_message']))

    def _find_device_books(self, book_lookup, log):
        """
        Look for the Kindle and return the list of books on it
        """
        dev = None
        scanner = DeviceScanner()
        scanner.scan()
        connected_devices = []
        for d in device_plugins():
            dev_connected = scanner.is_device_connected(d)
            if isinstance(dev_connected, tuple):
                ok, det = dev_connected
                if ok:
                    dev = d
                    connected_devices.append((det, dev))

        if dev is None:
            return None

        for det, d in connected_devices:
            try:
                d.open(det, None)
            except:
                continue
            else:
                dev = d
                break

        books = {}
        device_root = None

        try:
            for book in dev.books():
                if not device_root:
                    device_root = self._find_device_root(book.path)
                if book_lookup.has_key(book._data['uuid']):
                    books['%s_%s' % (book_lookup[book._data['uuid']].book_id, book.path.split('.')[-1].lower())] = {'device_book': book.path,
                        'device_xray': '.'.join(book.path.split('.')[:-1]) + '.sdr', 'device_root': device_root}
            return books
        except (TypeError, AttributeError) as e:
            log('%s Device found but cannot be accessed. It may have been ejected but not unplugged.' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
            return None
        except Exception as e:
            log('%s Something unexpectedly went wrong: %s' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S'), e))

    def _find_device_root(self, device_book):
        """
        Given the full path to a book on the device, return the path to the Kindle device

        eg. "C:\", "/Volumes/Kindle"
        """
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


    def create_xrays_event(self, abort, log, notifications):
        if log: log('\n%s Initializing...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        if notifications: notifications.put((0, 'Initializing...'))
        self._initialize_books(log)
        for book_num, book in enumerate(self.books_not_failing()):
            if abort.isSet():
                return
            if log: log('%s %s' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S'), book.title_and_author))
            book.create_xray_event(self._device_books, log=log, notifications=notifications, abort=abort, book_num=book_num, total=self._total_not_failing)

        self.get_results_create()
        log('\nX-Ray Creation:')
        if len(self._create_completed) > 0:
            log('\tBooks Completed:')
            for line in self._create_completed:
                log('\t\t%s' % line)
        if len(self._create_failed) > 0:
            log('\tBooks Failed:')
            for line in self._create_failed:
                log('\t\t%s' % line)

        if self._send_to_device:
            self.get_results_send()
            if len(self._send_completed) > 0 or len(self._send_failed) > 0:
                log('\nX-Ray Sending:')
                if len(self._send_completed) > 0:
                    log('\tBooks Completed:')
                    for line in self._send_completed:
                        log('\t\t%s' % line)
                if len(self._send_failed) > 0:
                    log('\tBooks Failed:')
                    for line in self._send_failed:
                        log('\t\t%s' % line)


    def send_xrays_event(self, abort, log, notifications):
        if log: log('\n%s Initializing...' % datetime.now().strftime('%m-%d-%Y %H:%M:%S'))
        if notifications: notifications.put((0, 'Initializing...'))
        self._initialize_books(log)
        for book_num, book in enumerate(self.books_not_failing()):
            if abort.isSet():
                return
            if log: log('%s %s' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S'), book.title_and_author))
            book.send_xray_event(self._device_books, log=log, notifications=notifications, abort=abort, book_num=book_num, total=self._total_not_failing)

        self.get_results_send()
        if len(self._send_completed) > 0:
            log('\nBooks Completed:')
            for line in self._send_completed:
                log('\t%s' % line)
        if len(self._send_failed) > 0:
            log('\nBooks Failed:')
            for line in self._send_failed:
                log('\t%s' % line)
