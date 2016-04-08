# shelfari_parser.py

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
        self._get_characters()
        self._get_terms()
        self._get_quotes()

    @property
    def characters(self):
        return self._characters

    @property
    def terms(self):
        return self._terms

    @property
    def quotes(self):
        return self._quotes
    
    def _get_characters(self):
        '''get characters from sheflari page'''
        self._characters = self._get_data_from_ul('//div[@id="WikiModule_Characters"]//ul[@class="li_6"]')
        

    def _get_terms(self):
        '''get terms from shelfari page'''
        self._terms = self._get_data_from_ul('//div[@id="WikiModule_Settings"]//ul[@class="li_6"]')

    def _get_quotes(self):
        '''get quotes from shelfari page'''
        quoteList = self._html_source.xpath('//div[@id="WikiModule_Quotations"]//li//blockquote/text()')
        self._quotes = [quote[1:-1] for quote in quoteList]

    def _get_data_from_ul(self, xpath):
        '''get data from a ul and put it into a dictionary'''
        results = {}
        ul = self._html_source.xpath(xpath)
        for li in ul[0]:
            label = li.getchildren()[0].text
            labelAndDesc = li.xpath("string()")[len(label):]
            descSearch = self._LETTERS_AND_NUMBERS.search(labelAndDesc)
            desc = descSearch.group(1) if descSearch else None
            results[label] = desc
        return results