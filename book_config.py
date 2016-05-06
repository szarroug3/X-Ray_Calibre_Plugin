#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2016, Samreen Zarroug & Alex Mayer'
__docformat__ = 'restructuredtext en'

import os
from PyQt5.QtCore import *
from PyQt5.Qt import QDialog, QWidget, QVBoxLayout, QHBoxLayout
from PyQt5.Qt import QLabel, QLineEdit, QPushButton, QScrollArea

from calibre_plugins.xray_creator.lib.book import Book

from calibre.library import current_library_path
from calibre.utils.config import JSONConfig

class BookConfigWidget(QDialog):
    def __init__(self, db, ids, parent):
        QDialog.__init__(self, parent)
        self.resize(500,500)
        self._index = 0

        self._book_settings = []
        for book_id in ids:
            self._book_settings.append(BookSettings(db, book_id))

        self.v_layout = QVBoxLayout(self)

        self.setWindowTitle('title - author')

        # add asin and shelfari url text boxes
        self.asin_label = QLabel('ASIN:')
        self.asin_edit = QLineEdit('')
        self.asin_edit.textChanged.connect(self.edit_asin)
        self.v_layout.addWidget(self.asin_label)
        self.v_layout.addWidget(self.asin_edit)

        self.shelfari_url = QLabel('Shelfari URL:')
        self.shelfari_url_edit = QLineEdit('')
        self.shelfari_url_edit.textChanged.connect(self.edit_shelfari_url)
        self.v_layout.addWidget(self.shelfari_url)
        self.v_layout.addWidget(self.shelfari_url_edit)

        # add scrollable area for aliases
        self.scroll_area = QScrollArea()
        self.scroll_area_layout = QVBoxLayout(self.scroll_area)
        self.scroll_area_layout.setAlignment(Qt.AlignTop)
        self.v_layout.addWidget(self.scroll_area)
        self.alias_tuples = []

        # add previous, ok, cancel, and next buttons
        self.buttons_layout = QHBoxLayout(self)
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

        self.show_book_prefs(self._book_settings[self._index])
        self.show()

    def edit_asin(self, val):
        self._book_settings[self._index].asin = val

    def edit_shelfari_url(self, val):
        self._book_settings[self._index].shelfari_url = val

    def previous(self):
        self._index -= 1
        self.next_button.setEnabled(True)
        if self._index == 0:
            self.previous_button.setEnabled(False)
        self.show_book_prefs(self._book_settings[self._index])

    def ok(self):
        for book in self._book_settings:
            book.save()
        self.close()

    def cancel(self):
        self.close()

    def next(self):
        self._index += 1
        self.previous_button.setEnabled(True)
        if self._index == len(self._book_settings) - 1:
            self.next_button.setEnabled(False)
        self.show_book_prefs(self._book_settings[self._index])

    def show_book_prefs(self, book):
        self.setWindowTitle(book.title_and_author)
        self.asin_edit.setText(book.asin)
        self.shelfari_url_edit.setText(book.shelfari_url)

        book.aliases = ('Vin', 'Vin Venture, The Heiress')
        book.aliases = ('Elend', 'Elend Venture, Lord Venture')
        #add aliases
        self.alias_tuples = []
        for term in sorted(book.aliases.keys()):
            layout = QHBoxLayout(self)
            
            label = QLabel(term + ':')
            label.setFixedWidth(75)
            layout.addWidget(label)

            aliases = QLineEdit(', '.join(book.aliases[term]))
            layout.addWidget(aliases)

            self.scroll_area_layout.addLayout(layout)
            self.alias_tuples.append((layout, label, aliases))


class BookSettings(object):
    LIBRARY = current_library_path()

    def __init__(self, db, book_id):
        self._book_id = book_id
        book_path = db.field_for('path', book_id).replace('/', os.sep)
        self._prefs = JSONConfig(os.path.join(book_path, 'book_settings'), base_path=self.LIBRARY)
        self._prefs.setdefault('asin', 'asin here')
        self._prefs.setdefault('shelfari_url', 'shelfari url here')
        self._prefs.setdefault('aliases', {})
        self._prefs.commit()

        self._title = db.field_for('title', book_id)
        self._author = ' & '.join(db.field_for('authors', self._book_id))
        self.asin = self._prefs['asin']
        self.shelfari_url = self._prefs['shelfari_url']
        self._aliases = self._prefs['aliases']

    @property
    def prefs(self):
        return self._prefs

    @property
    def title(self):
        return self._title
    
    @property
    def author(self):
        return self._author

    @property
    def title_and_author(self):
        return '%s - %s' % (self.title, self.author)

    @property
    def asin(self):
        return self._asin
    
    @asin.setter
    def asin(self, val):
        self._asin = val

    @property
    def shelfari_url(self):
        return self._shelfari_url
    
    @shelfari_url.setter
    def shelfari_url(self, val):
        self._shelfari_url = val

    @property
    def aliases(self):
        return self._aliases

    @aliases.setter
    def aliases(self, val):
        self._aliases[val[0]] =  val[1].replace(', ', ',').split(',')

    def save(self):
        self._prefs['asin'] = self.asin
        self._prefs['shelfari_url'] = self.shelfari_url
        self._prefs['aliases'] = self.aliases