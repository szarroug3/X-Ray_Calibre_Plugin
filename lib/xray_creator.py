# xray_creator.py

from datetime import datetime
from httplib import HTTPConnection

from calibre import get_proxies

from calibre_plugins.xray_creator.lib.book import Book

class XRayCreator(object):
    HEADERS = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/html", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0"}

    def __init__(self, db, book_ids, formats=[], spoilers=False, send_to_device=True, create_xray=True):
        self._db = db
        self._book_ids = book_ids
        self._formats = formats
        self._spoilers = spoilers
        self._send_to_device = send_to_device
        self._create_xray = create_xray

    @property
    def books(self):
        return self._books
    
    def _initialize_books(self):
        self._proxy = False
        self._http_address = None
        self._http_port = None

        http_proxy = get_proxies().get('http', None)
        if http_proxy:
            self._proxy = True
            self._http_address = ':'.join(http_proxy.split(':')[:-1])
            self._http_port = int(http_proxy.split(':')[-1])

            self._aConnection = HTTPConnection(self._http_address, self._http_port)
            self._aConnection.set_tunnel('www.amazon.com', 80)
            self._sConnection = HTTPConnection(self._http_address, self._http_port)
            self._sConnection.set_tunnel('www.shelfari.com', 80)
        else:
            self._aConnection = HTTPConnection('www.amazon.com')
            self._sConnection = HTTPConnection('www.shelfari.com')

        self._books = []
        for book_id in self._book_ids:
            self._books.append(Book(self._db, book_id, format=self._formats, spoilers=self._spoilers,
                send_to_device=self._send_to_device, create_xray=self._create_xray, proxy=self._proxy,
                http_address=self._http_address, http_port=self._http_port))
        
        self._total_not_failing = sum([1 for book in self._books if book.status is not book.FAIL])

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

    def create_xrays_event(self, abort, log, notifications):
        log('')
        self._initialize_books()
        for book_num, book in enumerate(self.books_not_failing()):
            if abort.isSet():
                return
            if log: log('%s %s' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S'), book.title_and_author))
            self._aConnection, self._sConnection = book.create_xray_event(self._aConnection, self._sConnection, log=log, notifications=notifications, abort=abort, book_num=book_num, total=self._total_not_failing)

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
        log('')
        self._initialize_books()
        for book_num, book in enumerate(self.books_not_failing()):
            if abort.isSet():
                return
            if log: log('%s %s' % (datetime.now().strftime('%m-%d-%Y %H:%M:%S'), book.title_and_author))
            self._aConnection, self._sConnection = book.send_xray_event(self._aConnection, self._sConnection, log=log, notifications=notifications, abort=abort, book_num=book_num, total=self._total_not_failing)

        self.get_results_send()
        if len(self._send_completed) > 0:
            log('\nBooks Completed:')
            for line in self._send_completed:
                log('\t%s' % line)
        if len(self._send_failed) > 0:
            log('\nBooks Failed:')
            for line in self._send_failed:
                log('\t%s' % line)