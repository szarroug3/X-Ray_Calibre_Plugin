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

from calibre_plugins.xray_creator.config import __prefs__ as prefs
from calibre_plugins.xray_creator.lib.goodreads_parser import GoodreadsPageDoesNotExist

class BookConfigWidget(QDialog):
    '''Creates book specific preferences dialog'''

    # title case given words except for articles in the middle
    # i.e the lord ruler would become The Lord Ruler but john the great would become John the Great
    ARTICLES = ['The', 'For', 'De', 'And', 'Or', 'Of', 'La']
    TITLE_CASE = lambda self, words: ' '.join([word.lower() if word in self.ARTICLES and index != 0
                                               else word
                                               for index, word in enumerate(words.title().split())])
    def __init__(self, parent, book_settings):
        QDialog.__init__(self, parent)
        self.resize(500, 500)
        self.setWindowTitle('title - author')

        self._index = 0
        self._book_settings = book_settings

        v_layout = QVBoxLayout(self)

        # add ASIN and Goodreads url text boxes
        self._asin_edit = QLineEdit('')
        self._asin_edit.textEdited.connect(self.edit_asin)
        self._initialize_asin(v_layout)

        self._goodreads_url_edit = QLineEdit('')
        self._goodreads_url_edit.textEdited.connect(self.edit_goodreads_url)
        self._initialize_goodreads_url(v_layout)

        self._update_aliases_button = QPushButton('Update Aliases from URL')
        self._update_aliases_button.setFixedWidth(175)
        self._update_aliases_button.clicked.connect(self.update_aliases)
        self._initialize_update_buttons(v_layout)

        # add scrollable area for aliases
        v_layout.addWidget(QLabel('Aliases:'))
        self._scroll_area = QScrollArea()
        v_layout.addWidget(self._scroll_area)

        # add status box
        self._status = QLabel('')
        v_layout.addWidget(self._status)

        if len(self._book_settings) > 1:
            self._previous_button = QPushButton('Previous')
            self._previous_button.setEnabled(False)
            self._previous_button.setFixedWidth(100)
            self._previous_button.clicked.connect(self.previous_clicked)
            self._next_button = QPushButton('Next')
            self._next_button.setFixedWidth(100)
            self._next_button.clicked.connect(self.next_clicked)
        self._initialize_navigation_buttons(v_layout)

        self.setLayout(v_layout)
        self.show_book_prefs()
        self.show()

    def _initialize_asin(self, v_layout):
        '''Add the ASIN label, line edit, and button to dialog'''
        asin_layout = QHBoxLayout(None)
        asin_label = QLabel('ASIN:')
        asin_label.setFixedWidth(100)
        self._asin_browser_button = QPushButton('Open..')
        self._asin_browser_button.clicked.connect(self.browse_amazon_url)
        self._asin_browser_button.setToolTip('Open Amazon page for the specified ASIN')
        asin_layout.addWidget(asin_label)
        asin_layout.addWidget(self._asin_edit)
        asin_layout.addWidget(self._asin_browser_button)
        v_layout.addLayout(asin_layout)

    def _initialize_goodreads_url(self, v_layout):
        '''Add the Goodreads URL label, line edit, and button to dialog'''
        goodreads_layout = QHBoxLayout(None)
        goodreads_url_label = QLabel('Goodreads URL:')
        goodreads_url_label.setFixedWidth(100)
        self._goodreads_browser_button = QPushButton('Open..')
        self._goodreads_browser_button.clicked.connect(self.browse_goodreads_url)
        self._goodreads_browser_button.setToolTip('Open Goodreads page at the specified URL')
        goodreads_layout.addWidget(goodreads_url_label)
        goodreads_layout.addWidget(self._goodreads_url_edit)
        goodreads_layout.addWidget(self._goodreads_browser_button)
        v_layout.addLayout(goodreads_layout)

    def _initialize_update_buttons(self, v_layout):
        '''Add the update buttons to dialog'''
        update_buttons_layout = QHBoxLayout(None)
        update_asin_button = QPushButton('Search for ASIN')
        update_asin_button.setFixedWidth(175)
        update_asin_button.clicked.connect(self.search_for_asin_clicked)
        update_buttons_layout.addWidget(update_asin_button)
        update_goodreads_url_button = QPushButton('Search for Goodreads URL')
        update_goodreads_url_button.setFixedWidth(175)
        update_goodreads_url_button.clicked.connect(self.search_for_goodreads_url)
        update_buttons_layout.addWidget(update_goodreads_url_button)

        update_buttons_layout.addWidget(self._update_aliases_button)
        v_layout.addLayout(update_buttons_layout)

    def _initialize_navigation_buttons(self, v_layout):
        '''Add previous, ok, cancel, and next buttons'''
        buttons_layout = QHBoxLayout(None)
        buttons_layout.setAlignment(Qt.AlignRight)

        if len(self._book_settings) > 1:
            buttons_layout.addWidget(self._previous_button)

        ok_button = QPushButton('OK')
        ok_button.setFixedWidth(100)
        ok_button.clicked.connect(self.ok_clicked)
        buttons_layout.addWidget(ok_button)

        cancel_button = QPushButton('Cancel')
        cancel_button.setFixedWidth(100)
        cancel_button.clicked.connect(self.cancel_clicked)
        buttons_layout.addWidget(cancel_button)

        if len(self._book_settings) > 1:
            buttons_layout.addWidget(self._next_button)

        v_layout.addLayout(buttons_layout)

    @property
    def book(self):
        return self._book_settings[self._index]

    def set_status_and_repaint(self, message):
        '''Sets the status text and redraws the status text box'''
        self._status.setText(message)
        self._status.repaint()

    def edit_asin(self, val):
        '''Set asin edit to specified value; update asin browser button accordingly'''
        self.book.asin = val
        if val == '':
            self._asin_browser_button.setEnabled(False)
        else:
            self._asin_browser_button.setEnabled(True)

    def edit_goodreads_url(self, val):
        '''Sets book's goodreads_url to val and warns if the url is invalid; update goodreads browser button accordingly'''
        self.book.goodreads_url = val
        if val == '':
            self._goodreads_browser_button.setEnabled(False)
            if self._status.text() == 'Warning: Invalid Goodreads URL. URL must have goodreads as the domain.':
                self._status.setText('')
        else:
            self._goodreads_browser_button.setEnabled(True)
            if 'goodreads.com' not in val:
                self._status.setText('Warning: Invalid Goodreads URL. URL must have goodreads as the domain.')

    def search_for_asin_clicked(self):
        '''Searches for current book's ASIN on amazon'''
        asin = None
        self.set_status_and_repaint('Searching for ASIN...')
        if self.book.title != 'Unknown' and self.book.author != 'Unknown':
            asin = self.book.search_for_asin_on_amazon(self.book.title_and_author)
        if asin:
            self._status.setText('ASIN found.')
            self._asin_browser_button.setEnabled(True)
            self.book.asin = asin
            self._asin_edit.setText(asin)
        else:
            self._status.setText('ASIN not found.')
            self._asin_browser_button.setEnabled(False)
            self._asin_edit.setText('')

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
        webbrowser.open('https://www.amazon.{0}/gp/product/{1}/'.format(prefs['tld'], self._asin_edit.text()))

    def browse_goodreads_url(self):
        '''Opens url for current book's goodreads url'''
        webbrowser.open(self._goodreads_url_edit.text())

    def search_for_goodreads_url(self):
        '''Searches for goodreads url using asin first then title and author if asin doesn't exist'''
        url = None
        self.set_status_and_repaint('Searching for Goodreads url...')
        if self.book.asin:
            url = self.book.search_for_goodreads_url(self.book.asin)
        if not url and self.book.title != 'Unknown' and self.book.author != 'Unknown':
            url = self.book.search_for_goodreads_url(self.book.title_and_author)
        if url:
            self._status.setText('Goodreads url found.')
            self._update_aliases_button.setEnabled(True)
            self._goodreads_browser_button.setEnabled(True)
            self.book.goodreads_url = url
            self._goodreads_url_edit.setText(url)
        else:
            self._status.setText('Goodreads url not found.')
            self._update_aliases_button.setEnabled(False)
            self._goodreads_browser_button.setEnabled(False)
            self._goodreads_url_edit.setText('')

    def update_aliases(self):
        '''Updates aliases on the preferences dialog using the information on the current goodreads url'''
        if 'goodreads.com' not in self._goodreads_url_edit.text():
            self._status.setText('Error: Invalid Goodreads URL. URL must have goodreads as the domain.')
            return

        try:
            self.set_status_and_repaint('Updating aliases...')
            self.book.update_aliases(self._goodreads_url_edit.text(), raise_error_on_page_not_found=True)
            self.update_aliases_on_gui()
            self._status.setText('Aliases updated.')
        except GoodreadsPageDoesNotExist:
            self._status.setText('Invalid Goodreads url.')

    def edit_aliases(self, term, val):
        '''Sets book's aliases to tuple (term, val)'''
        self.book.set_aliases(term, val)

    def previous_clicked(self):
        '''Goes to previous book'''
        self._status.setText('')
        self._index -= 1
        self._next_button.setEnabled(True)
        if self._index == 0:
            self._previous_button.setEnabled(False)
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
        self._status.setText('')
        self._index += 1
        self._previous_button.setEnabled(True)
        if self._index == len(self._book_settings) - 1:
            self._next_button.setEnabled(False)
        self.show_book_prefs()

    def show_book_prefs(self):
        '''Shows current book's preferences'''
        self.setWindowTitle(self.book.title_and_author)

        self._asin_edit.setText(self.book.asin)
        if self._asin_edit.text() == '':
            self._asin_browser_button.setEnabled(False)
        else:
            self._asin_browser_button.setEnabled(True)

        self._goodreads_url_edit.setText(self.book.goodreads_url)
        if self._goodreads_url_edit.text() == '':
            self._goodreads_browser_button.setEnabled(False)
        else:
            self._goodreads_browser_button.setEnabled(True)

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

        self._scroll_area.setWidget(aliases_widget)
