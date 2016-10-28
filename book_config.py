#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2016, Samreen Zarroug, Anthony Toole, & Alex Mayer'
__docformat__ = 'restructuredtext en'

import functools
import webbrowser
from httplib import HTTPSConnection

from PyQt5.QtCore import *
from PyQt5.Qt import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.Qt import QLabel, QLineEdit, QPushButton, QScrollArea

from calibre import get_proxies
from calibre_plugins.xray_creator.lib.book_settings import BookSettings

class BookConfigWidget(QDialog):
    # title case given words except for articles in the middle
    # i.e the lord ruler would become The Lord Ruler but john the great would become John the Great
    ARTICLES = ['The', 'For', 'De', 'And', 'Or', 'Of', 'La']
    TITLE_CASE = lambda self, words: ' '.join([word.lower() if word in self.ARTICLES and index != 0 else word for index, word in enumerate(words.title().split())])
    def __init__(self, db, ids, expand_aliases, parent):
        QDialog.__init__(self, parent)
        self.resize(500,500)
        self._index = 0

        self._book_settings = []

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

        for book_id in ids:
            book_settings = BookSettings(db, book_id, goodreads_conn, amazon_conn, expand_aliases)
            if len(book_settings.aliases) == 0 and book_settings.goodreads_url != "":
                book_settings.update_aliases(book_settings.goodreads_url)
                book_settings.save()
            self._book_settings.append(book_settings)

        self.v_layout = QVBoxLayout(self)

        self.setWindowTitle('title - author')

        # add ASIN and Goodreads url text boxes
        self.asin_layout = QHBoxLayout(None)
        self.asin = QLabel('ASIN:')
        self.asin.setFixedWidth(100)
        self.asin_edit = QLineEdit('')
        self.asin_edit.textEdited.connect(self.edit_asin)
        self.asin_browser_button = QPushButton("Open..")
        self.asin_browser_button.clicked.connect(self.browse_amazon_url)
        self.asin_browser_button.setToolTip("Open Amazon page for the specified ASIN")
        self.asin_layout.addWidget(self.asin)
        self.asin_layout.addWidget(self.asin_edit)
        self.asin_layout.addWidget(self.asin_browser_button)
        self.v_layout.addLayout(self.asin_layout)

        self.goodreads_layout = QHBoxLayout(None)
        self.goodreads_url = QLabel('Goodreads URL:')
        self.goodreads_url.setFixedWidth(100)
        self.goodreads_url_edit = QLineEdit('')
        self.goodreads_url_edit.textEdited.connect(self.edit_goodreads_url)
        self.goodreads_browser_button = QPushButton("Open..")
        self.goodreads_browser_button.clicked.connect(self.browse_goodreads_url)
        self.goodreads_browser_button.setToolTip("Open Goodreads page at the specified URL")
        self.goodreads_layout.addWidget(self.goodreads_url)
        self.goodreads_layout.addWidget(self.goodreads_url_edit)
        self.goodreads_layout.addWidget(self.goodreads_browser_button)
        self.v_layout.addLayout(self.goodreads_layout)

        self.update_buttons_layout = QHBoxLayout(None)
        self.update_ASIN_button = QPushButton('Search for ASIN')
        self.update_ASIN_button.setFixedWidth(175)
        self.update_ASIN_button.clicked.connect(self.search_for_ASIN)
        self.update_buttons_layout.addWidget(self.update_ASIN_button)
        self.update_goodreads_url_button = QPushButton('Search for Goodreads URL')
        self.update_goodreads_url_button.setFixedWidth(175)
        self.update_goodreads_url_button.clicked.connect(self.search_for_goodreads_url)
        self.update_buttons_layout.addWidget(self.update_goodreads_url_button)

        self.update_aliases_button = QPushButton('Update Aliases from URL')
        self.update_aliases_button.setFixedWidth(175)
        self.update_aliases_button.clicked.connect(self.update_aliases)
        self.update_buttons_layout.addWidget(self.update_aliases_button)
        self.v_layout.addLayout(self.update_buttons_layout)

        # add scrollable area for aliases
        self.aliases_label = QLabel('Aliases:')
        self.v_layout.addWidget(self.aliases_label)
        self.scroll_area = QScrollArea()
        self.v_layout.addWidget(self.scroll_area)

        # add status box
        self.status = QLabel('')
        self.v_layout.addWidget(self.status)

        # add previous, ok, cancel, and next buttons
        self.buttons_layout = QHBoxLayout(None)
        self.buttons_layout.setAlignment(Qt.AlignRight)

        if len(ids) > 1:
            self.previous_button = QPushButton("Previous")
            self.previous_button.setEnabled(False)
            self.previous_button.setFixedWidth(100)
            self.previous_button.clicked.connect(self.previous)
            self.buttons_layout.addWidget(self.previous_button)

        self.OK_button = QPushButton("OK")
        self.OK_button.setFixedWidth(100)
        self.OK_button.clicked.connect(self.ok)
        self.buttons_layout.addWidget(self.OK_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedWidth(100)
        self.cancel_button.clicked.connect(self.cancel)
        self.buttons_layout.addWidget(self.cancel_button)

        if len(ids) > 1:
            self.next_button = QPushButton("Next")
            self.next_button.setFixedWidth(100)
            self.next_button.clicked.connect(self.next)
            self.buttons_layout.addWidget(self.next_button)

        self.v_layout.addLayout(self.buttons_layout)
        self.setLayout(self.v_layout)

        self.show_book_prefs()
        self.show()

    @property
    def book(self):
        return self._book_settings[self._index]

    def set_status_and_repaint(self, message):
        self.status.setText(message)
        self.status.repaint()

    def edit_asin(self, val):
        self.book.asin = val

    def edit_goodreads_url(self, val):
        self.book.goodreads_url = val
        if 'goodreads.com' not in val:
            self.status.setText('Warning: Invalid Goodreads URL. URL must have goodreads as the domain.')

    def search_for_ASIN(self):
        asin = None
        self.set_status_and_repaint('Searching for ASIN...')
        if self.book.title != 'Unknown' and self.book.author != 'Unknown':
            asin = self.book.search_for_asin(self.book.title_and_author)
        if asin:
            self.status.setText('ASIN found.')
            self.book.asin = asin
            self.asin_edit.setText(asin)
        else:
            self.asin_edit.setText(original_text)
            self.status.setText('ASIN not found.')
            self.asin_edit.setText('')

    def browse_amazon_url(self):
        webbrowser.open("https://www.amazon.co.uk/gp/product/%s/" % (self.asin_edit.text()))

    def browse_goodreads_url(self):
        webbrowser.open(self.goodreads_url_edit.text())

    def search_for_goodreads_url(self):
        url = None
        self.set_status_and_repaint('Searching for Goodreads url...')
        if self.book.asin:
            url = self.book.search_for_goodreads(self.book.asin)
        if not url and self.book.title != 'Unknown' and self.book.author != 'Unknown':
            url = self.book.search_for_goodreads(self.book.title_and_author)
        if url:
            self.status.setText('Goodreads url found.')
            self.update_aliases_button.setEnabled(True)
            self.book.goodreads_url = url
            self.goodreads_url_edit.setText(url)
        else:
            self.status.setText('Goodreads url not found.')
            self.update_aliases_button.setEnabled(False)
            self.goodreads_url_edit.setText('')

    def update_aliases(self):
        if 'goodreads.com' not in self.goodreads_url_edit.text():
            self.status.setText('Error: Invalid Goodreads URL. URL must have goodreads as the domain.')
            return

        try:
            self.set_status_and_repaint('Updating aliases...')
            self.book.update_aliases(self.goodreads_url_edit.text(), raise_error_on_page_not_found=True)
            self.update_aliases_on_gui()
            self.status.setText('Aliases updated.')
        except:
            self.status.setText('Invalid Goodreads url.')

    def edit_aliases(self, term, val):
        self.book.aliases = (term, val)

    def previous(self):
        self.status.setText('')
        self._index -= 1
        self.next_button.setEnabled(True)
        if self._index == 0:
            self.previous_button.setEnabled(False)
        self.show_book_prefs()

    def ok(self):
        for book in self._book_settings:
            book.save()
        self.close()

    def cancel(self):
        self.close()

    def next(self):
        self.status.setText('')
        self._index += 1
        self.previous_button.setEnabled(True)
        if self._index == len(self._book_settings) - 1:
            self.next_button.setEnabled(False)
        self.show_book_prefs()

    def show_book_prefs(self):
        self.setWindowTitle(self.book.title_and_author)
        self.asin_edit.setText(self.book.asin)
        self.goodreads_url_edit.setText(self.book.goodreads_url)
        self.update_aliases_on_gui()

    def update_aliases_on_gui(self):
        self.aliases_widget = QWidget()
        self.aliases_layout = QGridLayout(self.aliases_widget)
        self.aliases_layout.setAlignment(Qt.AlignTop)

        # add aliases for current book
        for index, (character, aliases) in enumerate(sorted(self.book.aliases.items())):
            label = QLabel(character + ':')
            label.setFixedWidth(150)
            self.aliases_layout.addWidget(label, index, 0)

            line_edit = QLineEdit(', '.join([self.TITLE_CASE(alias) for alias in aliases]))
            line_edit.setFixedWidth(350)
            line_edit.textEdited.connect(functools.partial(self.edit_aliases, character))
            self.aliases_layout.addWidget(line_edit, index, 1)

        self.scroll_area.setWidget(self.aliases_widget)