# goodreads_parser.py

import re
from urllib2 import build_opener

from calibre.ebooks.BeautifulSoup import BeautifulSoup

# Parses Goodreads page for characters, terms, and quotes
class GoodreadsParser(object):
    DESC_PAT = re.compile(r'([a-zA-Z0-9\'"\(].+)')

    def __init__(self, url):
        self._opener = build_opener()

        response = self._opener.open(url)
        self._soup = BeautifulSoup(response.read())
        self._characters = []
        self._quotes = []

    @property
    def characters(self):
        return self._characters

    @property
    def quotes(self):
        return self._quotes

    def parse(self):
        self.get_characters()
        self.get_quotes()
    
    def get_characters(self):
        characters_div = self._soup.findAll('div', text='Characters')[0].parent.findNextSiblings('div')[0]
        for entity_id, char in enumerate(characters_div.findAll('a', {'href': re.compile('/characters/.+')})):
            data = {'label': char.text}
            url = char['href']
            char_page = self._opener.open('https://www.goodreads.com' + url).read()
            char_page_soup = BeautifulSoup(char_page)
            desc = char_page_soup.findAll('div', {'class': 'workCharacterAboutClear'})
            if len(desc) == 0 or not desc[0].text:
                desc = ''
            else:
                desc = desc[0].text.strip()
            data['description'] = desc
            aliases = []
            if 'aliases' in char_page:
                print '-'*100
                print char_page_soup.findAll('div', {'class': 'floatingBox', 'id': re.compile('.+aliases.+')})[0].parent
                print '-'*100
                aliases = [x.strip() for x in char_page_soup.findAll('div', {'class': 'floatingBox', 'id': re.compile('.+aliases.+')})[0].text[8:].split(',')]

            data['aliases'] = aliases
            self._characters.append((entity_id, data))

    def get_quotes(self):
        pass