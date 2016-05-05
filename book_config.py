#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2016, Samreen Zarroug & Alex Mayer'
__docformat__ = 'restructuredtext en'

import os
from PyQt5.Qt import QDialog, QWidget, QVBoxLayout, QHBoxLayout
from PyQt5.Qt import QLabel, QLineEdit, QPushButton

from calibre.library import current_library_path
from calibre.utils.config import JSONConfig

class BookConfigWidget(QWidget):
    def __init__(self, db, ids, dialog):
        QWidget.__init__(self)
        self._dialog = dialog
        self._index = 0

        self._book_settings = []
        for book_id in ids:
            self._book_settings.append(BookSettings(db, book_id))

        self.v_layout = QVBoxLayout(self._dialog)

        self._dialog.setWindowTitle('title - author')

        self.asin_label = QLabel('ASIN:')
        self.asin_edit = QLineEdit('')
        self.v_layout.addWidget(self.asin_label)
        self.v_layout.addWidget(self.asin_edit)

        self.shelfari_url = QLabel('Shelfari URL:')
        self.shelfari_url_edit = QLineEdit('')
        self.v_layout.addWidget(self.shelfari_url)
        self.v_layout.addWidget(self.shelfari_url_edit)

        self.buttons_layout = QHBoxLayout(self._dialog)

        if len(ids) > 1:
            self.previous_button = QPushButton("Previous")
            self.buttons_layout.addWidget(self.previous_button)
            self.previous_button.clicked.connect(self.previous)

        self.OK_button = QPushButton("OK")
        self.OK_button.clicked.connect(self.ok)
        self.buttons_layout.addWidget(self.OK_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel)
        self.buttons_layout.addWidget(self.cancel_button)


        if len(ids) > 1:
            self.next_button = QPushButton("Next")
            self.next_button.clicked.connect(self.next)
            self.buttons_layout.addWidget(self.next_button)

        self.v_layout.addLayout(self.buttons_layout)
        self._dialog.setLayout(self.v_layout)

        self.show_book_prefs(self._book_settings[self._index])
        self._dialog.show()

    def previous(self):
        print ('-'*100)
        self._index -= 1
        self.next_button.setEnabled(True)
        if self._index == 0:
            self.previous_button.setEnabled(False)
        self.show_book_prefs(self._book_settings[self._index])

    def ok(self):
        raise NotImplementedError()

    def cancel(self):
        raise NotImplementedError()

    def next(self):
        self._index += 1
        self.previous_button.setEnabled(True)
        if self._index == len(self._book_settings) - 1:
            self.next_button.setEnabled(False)
        self.show_book_prefs(self._book_settings[self._index])

    def show_book_prefs(self, book):
        self._dialog.setWindowTitle(book.title_and_author)
        self.asin_edit.setText(book.prefs['asin'])
        self.shelfari_url_edit.setText(book.prefs['shelfari_url'])

    def save_settings(self):
        raise NotImplementedError()

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
    
    