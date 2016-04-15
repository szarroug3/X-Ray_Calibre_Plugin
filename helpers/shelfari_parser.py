# shelfari_parser.py

from sys import exit
from urllib2 import urlopen
from lxml import html
import re

# Parses shelfari page for characters, terms, and quotes
class ShelfariParser(object):
    # global variables
    _LETTERS_AND_NUMBERS = re.compile('([a-zA-Z0-9].+)')

    def __init__(self, url):
        response = urlopen(url)
        page_source = response.read()
        self._html_source = html.fromstring(page_source)
        self._characters = []
        self._terms = []
        self._quotes = []
        self._entity_counter = 1

    @property
    def characters(self):
        return self._characters

    @property
    def terms(self):
        return self._terms

    @property
    def quotes(self):
        return self._quotes

    def parse(self):
        self._get_characters()
        self._get_terms()
        self._get_quotes()

    def _get_data_from_ul(self, xpath):
        results = {}
        ul = self._html_source.xpath(xpath)
        for li in ul[0]:
            label = li.getchildren()[0].text
            labelAndDesc = li.xpath("string()")[len(label):]
            descSearch = self._LETTERS_AND_NUMBERS.search(labelAndDesc)
            desc = descSearch.group(1) if descSearch else None
            results[self._entity_counter] = {'label': label, 'description': desc}
            self._entity_counter += 1
        return results
    
    def _get_characters(self):
        self._characters = self._get_data_from_ul('//div[@id="WikiModule_Characters"]//ul[@class="li_6"]')
        

    def _get_terms(self):
        self._terms = self._get_data_from_ul('//div[@id="WikiModule_Settings"]//ul[@class="li_6"]')

    def _get_quotes(self):
        quoteList = self._html_source.xpath('//div[@id="WikiModule_Quotations"]//li//blockquote/text()')
        self._quotes = [quote[1:-1].lower() for quote in quoteList]