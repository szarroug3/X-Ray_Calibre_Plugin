# shelfari_parser.py

from urllib2 import build_opener
from lxml import html
import re

# Parses shelfari page for characters, terms, and quotes
class ShelfariParser(object):
    # ShelfariBookWikiSession {"SpoilerBookId":51683,"SpoilerShowCharacters":true,"SpoilerShowSettings":true
    _LETTERS_AND_NUMBERS = re.compile('([a-zA-Z0-9].+)')

    def __init__(self, url, spoilers=False):
        opener = build_opener()
        shelfari_book_id = url.split('/')[4]
        spoilers_string = 'true' if spoilers else 'false'
        opener.addheaders.append(('Cookie', 'ShelfariBookWikiSession={"SpoilerBookId":%s,"SpoilerShowCharacters":%s,"SpoilerShowSettings":%s}' % (shelfari_book_id, spoilers_string, spoilers_string)))

        response = opener.open('/'.join(url.split('/')[:-1]) + '/wiki/Characters')
        page_source = response.read()
        self._characters_html_source = html.fromstring(page_source)

        response = opener.open('/'.join(url.split('/')[:-1]) + '/wiki/Settings')
        page_source = response.read()
        self._settings_html_source = html.fromstring(page_source)

        response = opener.open('/'.join(url.split('/')[:-1]) + '/wiki/Glossary')
        page_source = response.read()
        self._glossary_html_source = html.fromstring(page_source)

        response = opener.open('/'.join(url.split('/')[:-1]) + '/wiki/Quotations')
        page_source = response.read()
        self._quotations_html_source = html.fromstring(page_source)

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

    def _get_data_from_ul(self, type):
        xpath = '//ul[@class="li_6"]'
        if type == 'Characters': ul = self._characters_html_source.xpath(xpath)
        elif type == 'Settings': ul = self._settings_html_source.xpath(xpath)
        elif type == 'Glossary': ul = self._glossary_html_source.xpath(xpath)
        else: return

        results = {}
        for li in ul[0]:
            label = li.getchildren()[0].text
            labelAndDesc = li.xpath("string()")[len(label):]
            descSearch = self._LETTERS_AND_NUMBERS.search(labelAndDesc)
            desc = descSearch.group(1) if descSearch else None
            results[self._entity_counter] = {'label': label, 'description': desc}
            self._entity_counter += 1
        return results
    
    def _get_characters(self):
        self._characters = self._get_data_from_ul('Characters')
        
    def _get_terms(self):
        self._terms = self._get_data_from_ul('Settings')
        self._terms.update(self._get_data_from_ul('Glossary'))

    def _get_quotes(self):
        quoteList = self._quotations_html_source.xpath('//ul[@class="li_6"]//li//blockquote/text()')
        self._quotes = [quote[1:-1].lower() for quote in quoteList]