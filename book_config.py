#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
'''Creates dialog to allow control of book specific settings'''

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2016, Samreen Zarroug, Anthony Toole, & Alex Mayer'
__docformat__ = 'restructuredtext en'

import functools
import webbrowser

from PyQt5.QtCore import Qt
from PyQt5.Qt import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.Qt import QLabel, QLineEdit, QPushButton, QScrollArea

from calibre_plugins.xray_creator.lib.book_settings import BookSettings
from calibre_plugins.xray_creator.config import __prefs__ as prefs

class BookConfigWidget(QDialog):
    '''Creates book specific preferences dialog'''

    # title case given words except for articles in the middle
    # i.e the lord ruler would become The Lord Ruler but john the great would become John the Great
    ARTICLES = ['The', 'For', 'De', 'And', 'Or', 'Of', 'La']
    TITLE_CASE = lambda self, words: ' '.join([word.lower() if word in self.ARTICLES and index != 0
                                               else word
                                               for index, word in enumerate(words.title().split())])
    def __init__(self, database, ids, expand_aliases, parent, goodreads_conn, amazon_conn):
        QDialog.__init__(self, parent)
        self.resize(500, 500)
        self._index = 0

        self._book_settings = []

        for book_id in ids:
            book_settings = BookSettings(database, book_id, goodreads_conn, amazon_conn, expand_aliases)
            if len(book_settings.aliases) == 0 and book_settings.goodreads_url != '':
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
        self.asin_browser_button = QPushButton('Open..')
        self.asin_browser_button.clicked.connect(self.browse_amazon_url)
        self.asin_browser_button.setToolTip('Open Amazon page for the specified ASIN')
        self.asin_layout.addWidget(self.asin)
        self.asin_layout.addWidget(self.asin_edit)
        self.asin_layout.addWidget(self.asin_browser_button)
        self.v_layout.addLayout(self.asin_layout)

        self.goodreads_layout = QHBoxLayout(None)
        self.goodreads_url = QLabel('Goodreads URL:')
        self.goodreads_url.setFixedWidth(100)
        self.goodreads_url_edit = QLineEdit('')
        self.goodreads_url_edit.textEdited.connect(self.edit_goodreads_url)
        self.goodreads_browser_button = QPushButton('Open..')
        self.goodreads_browser_button.clicked.connect(self.browse_goodreads_url)
        self.goodreads_browser_button.setToolTip('Open Goodreads page at the specified URL')
        self.goodreads_layout.addWidget(self.goodreads_url)
        self.goodreads_layout.addWidget(self.goodreads_url_edit)
        self.goodreads_layout.addWidget(self.goodreads_browser_button)
        self.v_layout.addLayout(self.goodreads_layout)

        self.update_buttons_layout = QHBoxLayout(None)
        self.update_asin_button = QPushButton('Search for ASIN')
        self.update_asin_button.setFixedWidth(175)
        self.update_asin_button.clicked.connect(self.search_for_asin_clicked)
        self.update_buttons_layout.addWidget(self.update_asin_button)
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
            self.previous_button = QPushButton('Previous')
            self.previous_button.setEnabled(False)
            self.previous_button.setFixedWidth(100)
            self.previous_button.clicked.connect(self.previous_clicked)
            self.buttons_layout.addWidget(self.previous_button)

        self.ok_button = QPushButton('OK')
        self.ok_button.setFixedWidth(100)
        self.ok_button.clicked.connect(self.ok_clicked)
        self.buttons_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.setFixedWidth(100)
        self.cancel_button.clicked.connect(self.cancel_clicked)
        self.buttons_layout.addWidget(self.cancel_button)

        if len(ids) > 1:
            self.next_button = QPushButton('Next')
            self.next_button.setFixedWidth(100)
            self.next_button.clicked.connect(self.next_clicked)
            self.buttons_layout.addWidget(self.next_button)

        self.v_layout.addLayout(self.buttons_layout)
        self.setLayout(self.v_layout)

        self.show_book_prefs()
        self.show()

    @property
    def book(self):
        return self._book_settings[self._index]

    def set_status_and_repaint(self, message):
        '''Sets the status text and redraws the status text box'''
        self.status.setText(message)
        self.status.repaint()

    def edit_asin(self, val):
        self.book.asin = val

    def edit_goodreads_url(self, val):
        '''Sets book's goodreads_url to val and warns if the url is invalid'''
        self.book.goodreads_url = val
        if 'goodreads.com' not in val:
            self.status.setText('Warning: Invalid Goodreads URL. URL must have goodreads as the domain.')

    def search_for_asin_clicked(self):
        '''Searches for current book's ASIN on amazon'''
        asin = None
        self.set_status_and_repaint('Searching for ASIN...')
        if self.book.title != 'Unknown' and self.book.author != 'Unknown':
            asin = self.book.search_for_asin_on_amazon(self.book.title_and_author)
        if asin:
            self.status.setText('ASIN found.')
            self.book.asin = asin
            self.asin_edit.setText(asin)
        else:
            self.status.setText('ASIN not found.')
            self.asin_edit.setText('')

    def browse_amazon_url(self):
        '''Opens Amazon page for current book's ASIN using user's local store'''
        # Try to use the nearest Amazon store to the user.
        # If this fails we'll default to .com, the user will have to manually
        # edit the preferences file to fix it (it is a simple text file).
        if not prefs['tld']:
            from collections import defaultdict
            import json
            import urllib2
            try:
                country = json.loads(urllib2.urlopen('http://ipinfo.io/json').read())['country']
            except:
                country = 'unknown'
            country_tld = defaultdict(lambda: 'com', {'AU': 'com.au', 'BR': 'com.br', 'CA': 'ca', 'CN': 'cn', 'FR': 'fr',
                                                      'DE': 'de', 'IN': 'in', 'IT': 'it', 'JP': 'co.jp', 'MX': 'com.mx',
                                                      'NL': 'nl', 'ES': 'es', 'GB': 'co.uk', 'US': 'com'})
            prefs['tld'] = country_tld[country]
        webbrowser.open('https://www.amazon.{0}/gp/product/{1}/'.format(prefs['tld'], self.asin_edit.text()))

    def browse_goodreads_url(self):
        '''Opens url for current book's goodreads url'''
        webbrowser.open(self.goodreads_url_edit.text())

    def search_for_goodreads_url(self):
        '''Searches for goodreads url using asin first then title and author if asin doesn't exist'''
        url = None
        self.set_status_and_repaint('Searching for Goodreads url...')
        if self.book.asin:
            url = self.book.search_for_goodreads_url(self.book.asin)
        if not url and self.book.title != 'Unknown' and self.book.author != 'Unknown':
            url = self.book.search_for_goodreads_url(self.book.title_and_author)
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
        '''Updates aliases on the preferences dialog using the information on the current goodreads url'''
        if 'goodreads.com' not in self.goodreads_url_edit.text():
            self.status.setText('Error: Invalid Goodreads URL. URL must have goodreads as the domain.')
            return

        try:
            self.set_status_and_repaint('Updating aliases...')
            self.book.update_aliases(self.goodreads_url_edit.text())
            self.update_aliases_on_gui()
            self.status.setText('Aliases updated.')
        except:
            self.status.setText('Invalid Goodreads url.')

    def edit_aliases(self, term, val):
        '''Sets book's aliases to tuple (term, val)'''
        self.book.set_aliases(term, val)

    def previous_clicked(self):
        '''Goes to previous book'''
        self.status.setText('')
        self._index -= 1
        self.next_button.setEnabled(True)
        if self._index == 0:
            self.previous_button.setEnabled(False)
        self.show_book_prefs()

    def ok_clicked(self):
        '''Saves book's settings using current settings'''
        for book in self._book_settings:
            book.save()
        self.close()

    def cancel_clicked(self):
        '''Closes dialog without saving settings'''
        self.close()

    def next_clicked(self):
        '''Goes to next book'''
        self.status.setText('')
        self._index += 1
        self.previous_button.setEnabled(True)
        if self._index == len(self._book_settings) - 1:
            self.next_button.setEnabled(False)
        self.show_book_prefs()

    def show_book_prefs(self):
        '''Shows current book's preferences'''
        self.setWindowTitle(self.book.title_and_author)
        self.asin_edit.setText(self.book.asin)
        self.goodreads_url_edit.setText(self.book.goodreads_url)
        self.update_aliases_on_gui()

    def update_aliases_on_gui(self):
        '''Updates aliases on the dialog using the info in the book's aliases dict'''
        aliases_widget = QWidget()
        aliases_layout = QGridLayout(aliases_widget)
        aliases_layout.setAlignment(Qt.AlignTop)

        # add aliases for current book
        for index, (character, aliases) in enumerate(sorted(self.book.aliases.items())):
            label = QLabel(character + ':')
            label.setFixedWidth(150)
            aliases_layout.addWidget(label, index, 0)

            line_edit = QLineEdit(', '.join([self.TITLE_CASE(alias) for alias in aliases]))
            line_edit.setFixedWidth(350)
            line_edit.textEdited.connect(functools.partial(self.edit_aliases, character))
            aliases_layout.addWidget(line_edit, index, 1)

        self.scroll_area.setWidget(aliases_widget)
