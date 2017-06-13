# book_settings.py
'''Holds book specific settings and runs functions to get book specific data'''

import os
import json
from sqlite3 import connect
from urllib import urlencode
from urllib2 import urlparse

from calibre_plugins.xray_creator.lib.exceptions import PageDoesNotExist
from calibre_plugins.xray_creator.lib.goodreads_parser import GoodreadsParser
from calibre_plugins.xray_creator.lib.utilities import GOODREADS_URL_PAT, GOODREADS_ASIN_PAT
from calibre_plugins.xray_creator.lib.utilities import open_url, LIBRARY, BOOK_ID_PAT, AMAZON_ASIN_PAT
from calibre_plugins.xray_creator.lib.utilities import auto_expand_aliases

from calibre.utils.config import JSONConfig
from calibre.ebooks.BeautifulSoup import BeautifulSoup

class BookSettings(object):
    '''Holds book specific settings'''

    def __init__(self, database, book_id, connections):
        self._connections = connections

        book_path = database.field_for('path', book_id).replace('/', os.sep)

        self._prefs = JSONConfig(os.path.join(book_path, 'book_settings'), base_path=LIBRARY)
        self._prefs.setdefault('asin', '')
        self._prefs.setdefault('goodreads_url', '')
        self._prefs.setdefault('aliases', {})
        self._prefs.setdefault('sample_xray', '')
        self._prefs.commit()

        self._title = database.field_for('title', book_id)
        self._author = ' & '.join(database.field_for('authors', book_id))

        self._asin = self._prefs['asin'] if self._prefs['asin'] != '' else None
        self._goodreads_url = self._prefs['goodreads_url']
        self._sample_xray = self._prefs['sample_xray']

        if not self._asin:
            identifiers = database.field_for('identifiers', book_id)
            if 'mobi-asin' in identifiers.keys():
                self._asin = database.field_for('identifiers', book_id)['mobi-asin'].decode('ascii')
                self._prefs['asin'] = self._asin
            else:
                self._asin = self.search_for_asin_on_amazon(self.title_and_author)
                if self._asin:
                    metadata = database.get_metadata(book_id)
                    identifiers = metadata.get_identifiers()
                    identifiers['mobi-asin'] = self._asin
                    metadata.set_identifiers(identifiers)
                    database.set_metadata(book_id, metadata)
                    self._prefs['asin'] = self._asin

        if self._goodreads_url == '':
            url = None
            if self._asin:
                url = self.search_for_goodreads_url(self._asin)
            if not url and self._title != 'Unknown' and self._author != 'Unknown':
                url = self.search_for_goodreads_url(self.title_and_author)

            if url:
                self._goodreads_url = url
                self._prefs['goodreads_url'] = self._goodreads_url
                if not self._asin:
                    self._asin = self.search_for_asin_on_goodreads(self._goodreads_url)
                    if self._asin:
                        metadata = database.get_metadata(book_id)
                        identifiers = metadata.get_identifiers()
                        identifiers['mobi-asin'] = self._asin
                        metadata.set_identifiers(identifiers)
                        database.set_metadata(book_id, metadata)
                        self._prefs['asin'] = self._asin

        self._aliases = self._prefs['aliases']

        self.save()

    @property
    def prefs(self):
        return self._prefs

    @property
    def asin(self):
        return self._asin

    @asin.setter
    def asin(self, val):
        self._asin = val

    @property
    def sample_xray(self):
        return self._sample_xray

    @sample_xray.setter
    def sample_xray(self, value):
        self._sample_xray = value

    @property
    def title(self):
        return self._title

    @property
    def author(self):
        return self._author

    @property
    def title_and_author(self):
        return '{0} - {1}'.format(self._title, self._author)

    @property
    def goodreads_url(self):
        return self._goodreads_url

    @goodreads_url.setter
    def goodreads_url(self, val):
        self._goodreads_url = val

    @property
    def aliases(self):
        return self._aliases

    def set_aliases(self, label, aliases):
        '''Sets label's aliases to aliases'''

        # 'aliases' is a string containing a comma separated list of aliases.

        # Split it, remove whitespace from each element, drop empty strings (strangely,
        # split only does this if you don't specify a separator)

        # so "" -> []  "foo,bar" and " foo   , bar " -> ["foo", "bar"]
        aliases = [x.strip() for x in aliases.split(",") if x.strip()]
        self._aliases[label] = aliases

    def save(self):
        '''Saves current settings in book's settings file'''
        self._prefs['asin'] = self._asin
        self._prefs['goodreads_url'] = self._goodreads_url
        self._prefs['aliases'] = self._aliases
        self._prefs['sample_xray'] = self._sample_xray

    def search_for_asin_on_amazon(self, query):
        '''Search for book's asin on amazon using given query'''
        query = urlencode({'keywords': query})
        url = '/s/ref=sr_qz_back?sf=qz&rh=i%3Adigital-text%2Cn%3A154606011%2Ck%3A' + query[9:] + '&' + query
        try:
            response = open_url(self._connections['amazon'], url)
        except PageDoesNotExist:
            return None

        # check to make sure there are results
        if ('did not match any products' in response and 'Did you mean:' not in response and
                'so we searched in All Departments' not in response):
            return None

        soup = BeautifulSoup(response)
        results = soup.findAll('div', {'id': 'resultsCol'})

        if not results:
            return None

        for result in results:
            if 'Buy now with 1-Click' in str(result):
                asin_search = AMAZON_ASIN_PAT.search(str(result))
                if asin_search:
                    return asin_search.group(1)

        return None

    def search_for_goodreads_url(self, keywords):
        '''Searches for book's goodreads url using given keywords'''
        query = urlencode({'q': keywords})
        try:
            response = open_url(self._connections['goodreads'], '/search?' + query)
        except PageDoesNotExist:
            return None

        # check to make sure there are results
        if 'No results' in response:
            return None

        urlsearch = GOODREADS_URL_PAT.search(response)
        if not urlsearch:
            return None

        # return the full URL with the query parameters removed
        url = 'https://www.goodreads.com' + urlsearch.group(1)
        return urlparse.urlparse(url)._replace(query=None).geturl()

    def search_for_asin_on_goodreads(self, url):
        '''Searches for ASIN of book at given url'''
        book_id_search = BOOK_ID_PAT.search(url)
        if not book_id_search:
            return None

        book_id = book_id_search.group(1)

        try:
            response = open_url(self._connections['goodreads'], '/buttons/glide/' + book_id)
        except PageDoesNotExist:
            return None

        book_asin_search = GOODREADS_ASIN_PAT.search(response)
        if not book_asin_search:
            return None

        return book_asin_search.group(1)

    def update_aliases(self, source, source_type='url'):
        if source_type.lower() == 'url':
            self.update_aliases_from_url(source)
            return
        if source_type.lower() == 'asc':
            self.update_aliases_from_asc(source)
            return
        if source_type.lower() == 'json':
            self.update_aliases_from_json(source)

    def update_aliases_from_asc(self, filename):
        '''Gets aliases from sample x-ray file and expands them if users settings say to do so'''
        cursor = connect(filename).cursor()
        characters = {x[1]: [x[1]] for x in cursor.execute('SELECT * FROM entity').fetchall() if x[3] == 1}

        self._aliases = {}
        for alias, fullname in auto_expand_aliases(characters).items():
            if fullname not in self._aliases.keys():
                self._aliases[fullname] = [alias]
                continue
            self._aliases[fullname].append(alias)

    def update_aliases_from_json(self, filename):
        '''Gets aliases from json file'''
        data = json.load(open(filename))
        self._aliases = {name: char['aliases'] for name, char in data['characters'].items()} if 'characters' in data else {}
        if 'settings' in data:
            self._aliases.update({name: setting['aliases'] for name, setting in data['settings'].items()})

    def update_aliases_from_url(self, url):
        '''Gets aliases from Goodreads and expands them if users settings say to do so'''
        try:
            goodreads_parser = GoodreadsParser(url, self._connections['goodreads'], self._asin)
            goodreads_chars = goodreads_parser.get_characters(1)
            goodreads_settings = goodreads_parser.get_settings(len(goodreads_chars))
        except PageDoesNotExist:
            goodreads_chars = {}
            goodreads_settings = {}

        self._aliases = {}
        for char_data in goodreads_chars.values() + goodreads_settings.values():
            if char_data['label'] not in self._aliases.keys():
                self._aliases[char_data['label']] = char_data['aliases']
