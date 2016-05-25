#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2016, Samreen Zarroug & Alex Mayer'
__docformat__ = 'restructuredtext en'

import os
import functools
from PyQt5.QtCore import *
from httplib import HTTPConnection

from PyQt5.Qt import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.Qt import QLabel, QLineEdit, QPushButton, QScrollArea

from calibre_plugins.xray_creator.lib.book_settings import BookSettings

from calibre import get_proxies

class BookConfigWidget(QDialog):
    def __init__(self, db, ids, parent):
        QDialog.__init__(self, parent)
        self.resize(500,500)
        self._index = 0

        self._book_settings = []

        http_proxy = get_proxies(debug=False).get('http', None)
        if http_proxy:
            self._proxy = True
            self._http_address = ':'.join(http_proxy.split(':')[:-1])
            self._http_port = int(http_proxy.split(':')[-1])

            aConnection = HTTPConnection(self._http_address, self._http_port)
            aConnection.set_tunnel('www.amazon.com', 80)
            sConnection = HTTPConnection(self._http_address, self._http_port)
            sConnection.set_tunnel('www.shelfari.com', 80)
        else:
            aConnection = HTTPConnection('www.amazon.com')
            sConnection = HTTPConnection('www.shelfari.com')

        for book_id in ids:
            self._book_settings.append(BookSettings(db, book_id, aConnection, sConnection))

        self.v_layout = QVBoxLayout(self)

        self.setWindowTitle('title - author')

        # add asin and shelfari url text boxes
        self.asin_layout = QHBoxLayout(None)
        self.asin_label = QLabel('ASIN:')
        self.asin_label.setFixedWidth(75)
        self.asin_edit = QLineEdit('')
        self.asin_edit.textEdited.connect(self.edit_asin)
        self.asin_layout.addWidget(self.asin_label)
        self.asin_layout.addWidget(self.asin_edit)
        self.v_layout.addLayout(self.asin_layout)

        self.shelfari_layout = QHBoxLayout(None)
        self.shelfari_url = QLabel('Shelfari URL:')
        self.shelfari_url.setFixedWidth(75)
        self.shelfari_url_edit = QLineEdit('')
        self.shelfari_url_edit.textEdited.connect(self.edit_shelfari_url)
        self.shelfari_layout.addWidget(self.shelfari_url)
        self.shelfari_layout.addWidget(self.shelfari_url_edit)
        self.v_layout.addLayout(self.shelfari_layout)

        self.update_buttons_layout = QHBoxLayout(None)
        self.update_asin_button = QPushButton('Search for ASIN')
        self.update_asin_button.setFixedWidth(150)
        self.update_asin_button.clicked.connect(self.search_for_asin)
        self.update_buttons_layout.addWidget(self.update_asin_button)

        self.update_shelfari_url_button = QPushButton('Search for Shelfari URL')
        self.update_shelfari_url_button.setFixedWidth(150)
        self.update_shelfari_url_button.clicked.connect(self.search_for_shelfari_url)
        self.update_buttons_layout.addWidget(self.update_shelfari_url_button)

        self.update_aliases_button = QPushButton('Update Aliases from URL')
        self.update_aliases_button.setFixedWidth(150)
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
    
    def edit_asin(self, val):
        self.book.asin = val

    def edit_shelfari_url(self, val):
        http_string = 'http://www.'
        index = 0
        if val[:len(http_string)] != http_string:
            for i, letter in enumerate(val):
                if i < len(http_string):
                    if letter == http_string[i]:
                            index += 1
                    else:
                        break
                else:
                    break
            self.shelfari_url_edit.setText(http_string + val[index:])

        self.book.shelfari_url = val

    def search_for_asin(self):
        asin = None
        asin = self.book.get_asin()
        if not asin:
            if self.book.prefs['asin'] != '':
                self.status.setText('ASIN not found. Using original asin.')
                self.asin_edit.setText(self.book.prefs['asin'])
            else:
                self.status.setText('ASIN not found.')
                self.asin_edit.setText('')
        else:
            self.status.setText('ASIN found.')
            self.book.asin = asin
            self.asin_edit.setText(asin)

    def search_for_shelfari_url(self):
        url = None
        if self.asin_edit.text() != '' and self.asin_edit.text() != 'ASIN not found':
            url = self.book.search_shelfari(self.asin_edit.text())
        if not url:
            if self.book._prefs['asin'] != '':
                url = self.book.search_shelfari(self.book._prefs['asin'])
        if not url:
            if self.book.title != 'Unknown' and self.book.author != 'Unknown':
                url = self.book.search_shelfari(self.book.title_and_author)
        if url:
            self.status.setText('Shelfari url found.')
            self.update_aliases_button.setEnabled(True)
            self.book.shelfari_url = url
            self.shelfari_url_edit.setText(url)
        else:
            self.status.setText('Shelfari url not found.')
            self.update_aliases_button.setEnabled(False)
            self.shelfari_url_edit.setText('')

    def update_aliases(self):
        url = self.shelfari_url_edit.text()
        domain_end_index = url[7:].find('/') + 7
        if domain_end_index == -1: domain_end_index = len(url)

        test_url = HTTPConnection(url[7:domain_end_index])
        test_url.request('HEAD', url[domain_end_index:])

        if test_url.getresponse().status == 200:
            self.book.update_aliases(overwrite=True)
            self.update_aliases_on_gui()
            self.status.setText('Aliases updated.')
        else:
            self.status.setText('Invalid shelfari url.')

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
        self.shelfari_url_edit.setText(self.book.shelfari_url)
        self.update_aliases_on_gui()

    def update_aliases_on_gui(self):
        self.aliases_widget = QWidget()
        self.aliases_layout = QGridLayout(self.aliases_widget)
        self.aliases_layout.setAlignment(Qt.AlignTop)

        # add aliases for current book
        for index, aliases in enumerate(sorted(self.book.aliases.items())):
            label = QLabel(aliases[0] + ':')
            label.setFixedWidth(125)
            self.aliases_layout.addWidget(label, index, 0)

            line_edit = QLineEdit(', '.join(aliases[1]))
            line_edit.setFixedWidth(300)
            line_edit.textEdited.connect(functools.partial(self.edit_aliases, aliases[0]))
            self.aliases_layout.addWidget(line_edit, index, 1)

        self.scroll_area.setWidget(self.aliases_widget)