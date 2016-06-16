# goodreads_parser.py

import re
from lxml import html
from urllib2 import build_opener

# Parses Goodreads page for characters, terms, and quotes
class GoodreadsParser(object):

    def __init__(self, url):
        self._opener = build_opener()

        response = self._opener.open(url)
        self._page_source = html.fromstring(response.read())
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
        characters = self._page_source.xpath('//div[@class="clearFloats" and contains(., "Characters")]//div[@class="infoBoxRowItem"]//a')
        for entity_id, char in enumerate(characters):
            if '/characters/' not in char.get('href'):
                continue
            label = char.text
            char_page = html.fromstring(self._opener.open('https://www.goodreads.com' + char.get('href')).read())
            desc = char_page.xpath('//div[@class="workCharacterAboutClear"]/text()')[0].strip()
            aliases = [x.strip() for x in char_page.xpath('//div[@class="grey500BoxContent" and contains(.,"aliases")]/text()') if x.strip()]
            self_characters[entity_id] = {'label': label, 'description': desc, 'aliases': aliases}
    
    def get_quotes(self):
        pass