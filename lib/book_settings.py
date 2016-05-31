# book_settings.py

import os
import re
import functools
from urllib import urlencode
from httplib import HTTPConnection

from calibre_plugins.xray_creator.lib.shelfari_parser import ShelfariParser

from calibre.utils.config import JSONConfig
from calibre.library import current_library_path
from calibre.ebooks.BeautifulSoup import BeautifulSoup

class BookSettings(object):
    AMAZON_ASIN_PAT = re.compile(r'data\-asin=\"([a-zA-z0-9]+)\"')
    SHELFARI_URL_PAT = re.compile(r'href="(.+/books/.+?)"')
    HEADERS = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/html", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0"}
    LIBRARY = current_library_path()
    HONORIFICS = "mr mrs ms miss master sir madam lord dame lady prof professor doctor dr father reverend"
    HONORIFICS += "atty attorney hon honoroable president pres gov governor sen senator"
    HONORIFICS += "ofc officer pvt private cpl corporal sgt sargent maj major capt captain cmdr commander lt lieutenant col colonel gen general"
    HONORIFICS = HONORIFICS.split()
    HONORIFICS.extend([x + "." for x in HONORIFICS])

    def __init__(self, db, book_id, aConnection, sConnection):
        self._db = db
        self._book_id = book_id
        self._aConnection = aConnection
        self._sConnection = sConnection

        book_path = self._db.field_for('path', book_id).replace('/', os.sep)

        self._prefs = JSONConfig(os.path.join(book_path, 'book_settings'), base_path=self.LIBRARY)
        self._prefs.setdefault('asin', '')
        self._prefs.setdefault('shelfari_url', '')
        self._prefs.setdefault('aliases', {})
        self._prefs.commit()

        self._title = self._db.field_for('title', book_id)
        self._author = ' & '.join(self._db.field_for('authors', self._book_id))

        self.asin = self._prefs['asin']
        if self.asin == '':
            identifiers = self._db.field_for('identifiers', self._book_id)
            self.asin = self._db.field_for('identifiers', self._book_id)['mobi-asin'].decode('ascii') if 'mobi-asin' in identifiers.keys() else None
            if not self.asin:
                self.asin = self.get_asin()
            if self.asin:
                self._prefs['asin'] = self.asin

        self.shelfari_url = self._prefs['shelfari_url']
        if self.shelfari_url == '':
            url = None
            if self._prefs['asin'] != '':
                url = self.search_shelfari(self._prefs['asin'])
            if not url and self.title != 'Unknown' and self.author != 'Unknown':
                url = self.search_shelfari(self.title_and_author)

            if url:
                self.shelfari_url = url
                self._prefs['shelfari_url'] = self.shelfari_url

        self._aliases = self._prefs['aliases']
        if len(self._aliases.keys()) == 0 and self.shelfari_url != '':
            self.update_aliases()
        self.save()

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
        # 'aliases' is a string containing a comma separated list of aliases.  
        #
        # Split it, remove whitespace from each element, drop empty strings (strangely, split only does this if you don't specify a separator)
        #
        # so "" -> []  "foo,bar" and " foo   , bar " -> ["foo", "bar"]
        label, aliases = val
        aliases = [x.strip() for x in aliases.split(",") if x.strip()]
        self._aliases[label] =  aliases

    def save(self):
        self._prefs['asin'] = self.asin
        self._prefs['shelfari_url'] = self.shelfari_url
        self._prefs['aliases'] = self.aliases

    def get_asin(self):
        query = urlencode({'keywords': '%s' % self.title_and_author})
        try:
            self._aConnection.request('GET', '/s/ref=sr_qz_back?sf=qz&rh=i%3Adigital-text%2Cn%3A154606011%2Ck%3A' + query[9:] + '&' + query, headers=self.HEADERS)
            response = self._aConnection.getresponse().read()
        except:
            try:
                self._aConnection.close()
                if self._proxy:
                    self._aConnection = HTTPConnection(self._http_address, self._http_port)
                    self._aConnection.set_tunnel('www.amazon.com', 80)
                else:
                    self._aConnection = HTTPConnection('www.amazon.com')

                self._aConnection.request('GET', '/s/ref=sr_qz_back?sf=qz&rh=i%3Adigital-text%2Cn%3A154606011%2Ck%3A' + query[9:] + '&' + query, headers=self.HEADERS)
                response = self._aConnection.getresponse().read()
            except:
                return None

        # check to make sure there are results
        if 'did not match any products' in response and not 'Did you mean:' in response and not 'so we searched in All Departments' in response:
            return None

        soup = BeautifulSoup(response)
        results = soup.findAll('div', {'id': 'resultsCol'})
       
        if not results or len(results) == 0:
            return None

        for r in results:
            if 'Buy now with 1-Click' in str(r):
                asinSearch = self.AMAZON_ASIN_PAT.search(str(r))
                if asinSearch:
                    asin = asinSearch.group(1)
                    mi = self._db.get_metadata(self._book_id)
                    identifiers = mi.get_identifiers()
                    identifiers['mobi-asin'] = asin
                    mi.set_identifiers(identifiers)
                    self._db.set_metadata(self._book_id, mi)
                    return asin

    def search_shelfari(self, keywords):
        query = urlencode ({'Keywords': keywords})
        try:
            self._sConnection.request('GET', '/search/books?' + query)
            response = self._sConnection.getresponse().read()
        except:
            try:
                self._sConnection.close()
                if self._proxy:
                    self._sConnection = HTTPConnection(self._http_address, self._http_port)
                    self._sConnection.set_tunnel('www.shelfari.com', 80)
                else:
                    self._sConnection = HTTPConnection('www.shelfari.com')

                self._sConnection.request('GET', '/search/books?' + query)
                response = self._sConnection.getresponse().read()
            except:
                return None
        
        # check to make sure there are results
        if 'did not return any results' in response:
            return None

        urlsearch = self.SHELFARI_URL_PAT.search(response)
        if not urlsearch:
            return None

        return urlsearch.group(1)

    def update_aliases(self, overwrite=False):
        shelfari_parser = ShelfariParser(self.shelfari_url)
        shelfari_parser.get_characters()
        shelfari_parser.get_terms()

        if overwrite:
            self._prefs['aliases'] = {}
            self._aliases = {}
        
        characters = [char[1]['label'] for char in shelfari_parser.characters.items()]
        for char in characters:
            if char not in self.aliases.keys():
                self.aliases = (char, '')
        
        terms = [term[1]['label'] for term in shelfari_parser.terms.items()]
        for term in terms:
            if term not in self.aliases.keys():
                self.aliases = (term, '')

        aliases = self.auto_expand_aliases(characters)
        for alias, fullname in aliases.items():
            self.aliases = (fullname, alias + ',' + ','.join(self.aliases[fullname]))

    def auto_expand_aliases(self, characters):
        actual_aliases = {}
        duplicates = [x.lower() for x in characters]
        for fullname in characters:
            aliases = self.fullname_to_possible_aliases(fullname.lower())
            for alias in aliases:
                # if this alias has already been flagged as a duplicate, skip it
                if alias in duplicates:
                    continue
                # check if this alias is a duplicate but isn't in the duplicates list
                if actual_aliases.has_key(alias):
                    duplicates.append(alias)
                    actual_aliases.pop(alias)
                    continue

                # at this point, the alias is new -- add it to the dict with the alias as the key and fullname as the value
                actual_aliases[alias] = fullname

        return actual_aliases

    def fullname_to_possible_aliases(self, fullname):
        """
        Given a full name ("{Title} ChristianName {Middle Names} {Surname}"), return a list of possible aliases
        
        ie. Title Surname, ChristianName Surname, Title ChristianName, {the full name}
        
        The returned aliases are in the order they should match
        """
        aliases = []        
        parts = fullname.split()
        if parts[0].lower() in self.HONORIFICS:
            title = parts.pop(0)
        else:
            title = None
            
        if len(parts) >= 2:
            # Assume: {Title} Firstname {Middlenames} Lastname
            # Already added the full form, also add Title Lastname, and for some Title Firstname
            surname = parts.pop() # This will cover double barrel surnames, we split on whitespace only
            christian_name = parts.pop(0)
            middlenames = parts
            if title:
                aliases.append("%s %s" % (title, surname))
                if "lord" in title:
                    aliases.append("%s %s" % (title, christian_name))
            aliases.append(christian_name)
            aliases.append(surname)
            aliases.append("%s %s" % (christian_name, surname))

        elif title:
            # Odd, but got Title Name (eg. Lord Buttsworth), so see if we can alias
            aliases.append(parts[0])
        else:
            # We've got no title, so just a single word name.  No alias needed
            pass
        return aliases