#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
'''Creates dialog to allow control of book specific settings'''

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2016, Samreen Zarroug, Anthony Toole, & Alex Mayer'
__docformat__ = 'restructuredtext en'

import os
import functools
import webbrowser

from PyQt5.QtCore import Qt
from PyQt5.Qt import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.Qt import QLabel, QLineEdit, QPushButton, QScrollArea, QFileDialog

from calibre_plugins.xray_creator.config import __prefs__ as prefs
from calibre_plugins.xray_creator.lib.exceptions import PageDoesNotExist

class BookConfigWidget(QDialog):
    '''Creates book specific preferences dialog'''

    # title case given words except for articles in the middle
    # i.e the lord ruler would become The Lord Ruler but john the great would become John the Great
    ARTICLES = ['The', 'For', 'De', 'And', 'Or', 'Of', 'La']
    TITLE_CASE = lambda self, words: ' '.join([word.lower() if word in self.ARTICLES and index != 0
                                               else word for index, word in enumerate(words.title().split())])
    def __init__(self, parent, book_settings):
        QDialog.__init__(self, parent)
        self.resize(500, 500)
        self.setWindowTitle('title - author')

        self._index = 0
        self._book_settings = book_settings

        v_layout = QVBoxLayout(self)

        # add ASIN and Goodreads url text boxes and update buttons
        asin_browser_button, goodreads_browser_button = self._initialize_general(v_layout)

        # add scrollable area for aliases
        v_layout.addWidget(QLabel('Aliases:'))
        self._scroll_area = QScrollArea()
        v_layout.addWidget(self._scroll_area)

        # add status box
        self._status = QLabel('')
        v_layout.addWidget(self._status)

        previous_button = next_button = None
        if len(self._book_settings) > 1:
            previous_button = QPushButton('Previous')
            previous_button.setEnabled(False)
            previous_button.setFixedWidth(100)
            next_button = QPushButton('Next')
            next_button.setFixedWidth(100)
            previous_button.clicked.connect(lambda: self.previous_clicked(previous_button, next_button,
                                                                          asin_browser_button, goodreads_browser_button))
            next_button.clicked.connect(lambda: self.next_clicked(previous_button, next_button,
                                                                  asin_browser_button, goodreads_browser_button))
        self._initialize_navigation_buttons(v_layout, previous_button, next_button)

        self.setLayout(v_layout)
        self.show_book_prefs(asin_browser_button, goodreads_browser_button)
        self.show()

    def _initialize_general(self, v_layout):
        '''Initialize asin/goodreads sections'''
        # Add the ASIN label, line edit, and button to dialog
        self._asin_edit = QLineEdit('')
        asin_layout = QHBoxLayout(None)
        asin_label = QLabel('ASIN:')
        asin_label.setFixedWidth(100)
        asin_browser_button = QPushButton('Open..')
        asin_browser_button.clicked.connect(self.browse_amazon_url)
        asin_browser_button.setToolTip('Open Amazon page for the specified ASIN')
        self._asin_edit.textEdited.connect(lambda: self.edit_asin(self._asin_edit.text(), asin_browser_button))
        asin_layout.addWidget(asin_label)
        asin_layout.addWidget(self._asin_edit)
        asin_layout.addWidget(asin_browser_button)
        v_layout.addLayout(asin_layout)

        # Add the Goodreads URL label, line edit, and button to dialog
        self._goodreads_url_edit = QLineEdit('')
        self._goodreads_url_edit.textEdited.connect(lambda: self.edit_goodreads_url(self._goodreads_url_edit.text(),
                                                                                    goodreads_browser_button))
        goodreads_layout = QHBoxLayout(None)
        goodreads_url_label = QLabel('Goodreads URL:')
        goodreads_url_label.setFixedWidth(100)
        goodreads_browser_button = QPushButton('Open..')
        goodreads_browser_button.clicked.connect(self.browse_goodreads_url)
        goodreads_browser_button.setToolTip('Open Goodreads page at the specified URL')
        goodreads_layout.addWidget(goodreads_url_label)
        goodreads_layout.addWidget(self._goodreads_url_edit)
        goodreads_layout.addWidget(goodreads_browser_button)
        v_layout.addLayout(goodreads_layout)

        # Add the sample xray label, line edit, and button to dialog
        self._sample_xray_edit = QLineEdit('')
        self._sample_xray_edit.textEdited.connect(lambda: self.edit_sample_xray(self._sample_xray_edit.text()))
        sample_xray_layout = QHBoxLayout(None)
        sample_xray_label = QLabel('Sample X-Ray:')
        sample_xray_label.setFixedWidth(100)
        sample_xray_button = QPushButton('Browse...')
        sample_xray_button.clicked.connect(self.browse_sample_xray)
        sample_xray_button.setToolTip('Browse for a sample x-ray file to be used')
        sample_xray_layout.addWidget(sample_xray_label)
        sample_xray_layout.addWidget(self._sample_xray_edit)
        sample_xray_layout.addWidget(sample_xray_button)
        v_layout.addLayout(sample_xray_layout)

        # Add the update buttons to dialog
        self._update_aliases_button = QPushButton('Update Aliases from URL')
        self._update_aliases_button.setFixedWidth(175)
        self._update_aliases_button.clicked.connect(self.update_aliases)
        update_buttons_layout = QHBoxLayout(None)
        update_asin_button = QPushButton('Search for ASIN')
        update_asin_button.setFixedWidth(175)
        update_asin_button.clicked.connect(lambda: self.search_for_asin_clicked(asin_browser_button))
        update_buttons_layout.addWidget(update_asin_button)
        update_goodreads_url_button = QPushButton('Search for Goodreads URL')
        update_goodreads_url_button.setFixedWidth(175)
        update_goodreads_url_button.clicked.connect(lambda: self.search_for_goodreads_url(goodreads_browser_button))
        update_buttons_layout.addWidget(update_goodreads_url_button)

        update_buttons_layout.addWidget(self._update_aliases_button)
        v_layout.addLayout(update_buttons_layout)

        return asin_browser_button, goodreads_browser_button

    def _initialize_navigation_buttons(self, v_layout, previous_button, next_button):
        '''Add previous, ok, cancel, and next buttons'''
        buttons_layout = QHBoxLayout(None)
        buttons_layout.setAlignment(Qt.AlignRight)

        if len(self._book_settings) > 1:
            buttons_layout.addWidget(previous_button)

        ok_button = QPushButton('OK')
        ok_button.setFixedWidth(100)
        ok_button.clicked.connect(self.ok_clicked)
        buttons_layout.addWidget(ok_button)

        cancel_button = QPushButton('Cancel')
        cancel_button.setFixedWidth(100)
        cancel_button.clicked.connect(self.cancel_clicked)
        buttons_layout.addWidget(cancel_button)

        if len(self._book_settings) > 1:
            buttons_layout.addWidget(next_button)

        v_layout.addLayout(buttons_layout)

    @property
    def book(self):
        return self._book_settings[self._index]

    def set_status_and_repaint(self, message):
        '''Sets the status text and redraws the status text box'''
        self._status.setText(message)
        self._status.repaint()

    def edit_asin(self, val, asin_browser_button):
        '''Set asin edit to specified value; update asin browser button accordingly'''
        self.book.asin = val
        if val == '':
            asin_browser_button.setEnabled(False)
        else:
            asin_browser_button.setEnabled(True)

    def edit_goodreads_url(self, val, goodreads_browser_button):
        '''Sets book's goodreads_url to val and warns if the url is invalid; update goodreads browser button accordingly'''
        self.book.goodreads_url = val
        if val == '':
            goodreads_browser_button.setEnabled(False)
            if self._status.text() == 'Warning: Invalid Goodreads URL. URL must have goodreads as the domain.':
                self._status.setText('')
        else:
            goodreads_browser_button.setEnabled(True)
            if 'goodreads.com' not in val:
                self._status.setText('Warning: Invalid Goodreads URL. URL must have goodreads as the domain.')

    def edit_sample_xray(self, val):
        '''Sets book's goodreads_url to val and warns if the url is invalid; update goodreads browser button accordingly'''
        self.book.sample_xray = val
        if val == '':
            if self._status.text() == 'Warning: Invalid input file.':
                self._status.setText('')
        else:
            if not os.path.isfile(val):
                self._status.setText('Warning: Invalid input file.')
                return
            self.update_aliases()

    def search_for_asin_clicked(self, asin_browser_button):
        '''Searches for current book's ASIN on amazon'''
        asin = None
        self.set_status_and_repaint('Searching for ASIN...')
        if self.book.title != 'Unknown' and self.book.author != 'Unknown':
            asin = self.book.search_for_asin_on_amazon(self.book.title_and_author)
        if asin:
            self._status.setText('ASIN found.')
            asin_browser_button.setEnabled(True)
            self.book.asin = asin
            self._asin_edit.setText(asin)
        else:
            self._status.setText('ASIN not found.')
            asin_browser_button.setEnabled(False)
            self._asin_edit.setText('')

    def browse_amazon_url(self):
        '''Opens Amazon page for current book's ASIN using user's local store'''
        # Try to use the nearest Amazon store to the user.
        # If this fails we'll default to .com, the user will have to manually
        # edit the preferences file to fix it (it is a simple text file).
        if not prefs['tld']:
            from collections import defaultdict
            import json
            from urllib2 import urlopen, URLError

            try:
                country = json.loads(urlopen('http://ipinfo.io/json').read())['country']
            except (URLError, KeyError):
                country = 'unknown'
            country_tld = defaultdict(lambda: 'com', {'AU': 'com.au', 'BR': 'com.br', 'CA': 'ca', 'CN': 'cn', 'FR': 'fr',
                                                      'DE': 'de', 'IN': 'in', 'IT': 'it', 'JP': 'co.jp', 'MX': 'com.mx',
                                                      'NL': 'nl', 'ES': 'es', 'GB': 'co.uk', 'US': 'com'})
            prefs['tld'] = country_tld[country]
        webbrowser.open('https://www.amazon.{0}/gp/product/{1}/'.format(prefs['tld'], self._asin_edit.text()))

    def browse_goodreads_url(self):
        '''Opens url for current book's goodreads url'''
        webbrowser.open(self._goodreads_url_edit.text())

    def browse_sample_xray(self):
        """Browse for a sample xray file to use during x-ray creation"""
        file_dialog = QFileDialog(self)
        sample_file = file_dialog.getOpenFileName(caption='Choose sample x-ray to use:',
                                                  filter='X-Ray (*.asc)')[0]
        self.book.sample_xray = sample_file
        self._sample_xray_edit.setText(sample_file)
        if sample_file:
            self.update_aliases()

    def search_for_goodreads_url(self, goodreads_browser_button):
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
            goodreads_browser_button.setEnabled(True)
            self.book.goodreads_url = url
            self._goodreads_url_edit.setText(url)
        else:
            self._status.setText('Goodreads url not found.')
            self._update_aliases_button.setEnabled(False)
            goodreads_browser_button.setEnabled(False)
            self._goodreads_url_edit.setText('')

    def update_aliases(self):
        '''Update aliases using given file or goodreads'''
        if self.book.sample_xray:
            if os.path.exists(self.book.sample_xray):
                self.update_aliases_from_file()
                return
            else:
                self._status.setText('Error: Sample x-ray file doesn\'t exist.')
        if 'goodreads.com' not in self._goodreads_url_edit.text():
            self._status.setText('Error: Invalid Goodreads URL. URL must have goodreads as the domain.')
            return
        self.update_aliases_from_goodreads()

    def update_aliases_from_file(self):
        '''Update aliases on the preferences dailog using the information in the specified file'''
        self.set_status_and_repaint('Updating aliases...')
        self.book.update_aliases(self.book.sample_xray, source_type='asc')
        self.update_aliases_on_gui()
        self._status.setText('Aliases updated.')

    def update_aliases_from_goodreads(self):
        '''Updates aliases on the preferences dialog using the information on the current goodreads url'''
        try:
            self.set_status_and_repaint('Updating aliases...')
            self.book.update_aliases(self._goodreads_url_edit.text())
            self.update_aliases_on_gui()
            self._status.setText('Aliases updated.')
        except PageDoesNotExist:
            self._status.setText('Invalid Goodreads url.')

    def edit_aliases(self, term, val):
        '''Sets book's aliases to tuple (term, val)'''
        self.book.set_aliases(term, val)

    def previous_clicked(self, previous_button, next_button, asin_browser_button, goodreads_browser_button):
        '''Goes to previous book'''
        self._status.setText('')
        self._index -= 1
        next_button.setEnabled(True)
        if self._index == 0:
            previous_button.setEnabled(False)
        self.show_book_prefs(asin_browser_button, goodreads_browser_button)

    def ok_clicked(self):
        '''Saves book's settings using current settings'''
        for book in self._book_settings:
            book.save()
        self.close()

    def cancel_clicked(self):
        '''Closes dialog without saving settings'''
        self.close()

    def next_clicked(self, previous_button, next_button, asin_browser_button,
                     goodreads_browser_button):
        '''Goes to next book'''
        self._status.setText('')
        self._index += 1
        previous_button.setEnabled(True)
        if self._index == len(self._book_settings) - 1:
            next_button.setEnabled(False)
        self.show_book_prefs(asin_browser_button, goodreads_browser_button)

    def show_book_prefs(self, asin_browser_button, goodreads_browser_button):
        '''Shows current book's preferences'''
        self.setWindowTitle(self.book.title_and_author)

        self._asin_edit.setText(self.book.asin)
        if self._asin_edit.text() == '':
            asin_browser_button.setEnabled(False)
        else:
            asin_browser_button.setEnabled(True)

        self._goodreads_url_edit.setText(self.book.goodreads_url)
        if self._goodreads_url_edit.text() == '':
            goodreads_browser_button.setEnabled(False)
        else:
            goodreads_browser_button.setEnabled(True)

        self._sample_xray_edit.setText(self.book.sample_xray)

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
