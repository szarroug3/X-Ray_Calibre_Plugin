# shelfari_parser.py

from urllib2 import build_opener
from lxml import html
import re

# Parses shelfari page for characters, terms, and quotes
class ShelfariParser(object):
    # ShelfariBookWikiSession {"SpoilerBookId":51683,"SpoilerShowCharacters":true,"SpoilerShowSettings":true
    DESC_PAT = re.compile(r'([a-zA-Z0-9\'"].+)')

    def __init__(self, url, spoilers=False):
        opener = build_opener()
        shelfari_book_id = url.split('/')[4]
        spoilers_string = 'true' if spoilers else 'false'
        opener.addheaders.append(('Cookie', 'ShelfariBookWikiSession={"SpoilerBookId":%s,"SpoilerShowCharacters":%s,"SpoilerShowSettings":%s}' % (shelfari_book_id, spoilers_string, spoilers_string)))

        response = opener.open('/'.join(url.split('/')[:-1]) + '/wiki/Characters')
        page_source = response.read()
        if page_source:
            self._characters_html_source = html.fromstring(page_source)
        else:
            self._characters_html_source = None

        response = opener.open('/'.join(url.split('/')[:-1]) + '/wiki/Settings')
        page_source = response.read()
        if page_source:
            self._settings_html_source = html.fromstring(page_source)
        else:
            self._settings_html_source = None

        response = opener.open('/'.join(url.split('/')[:-1]) + '/wiki/Glossary')
        page_source = response.read()
        if page_source:
            self._glossary_html_source = html.fromstring(page_source)
        else:
            self._glossary_html_source = None

        response = opener.open('/'.join(url.split('/')[:-1]) + '/wiki/Quotations')
        page_source = response.read()
        if page_source:
            self._quotations_html_source = html.fromstring(page_source)
        else:
            self._quotations_html_source = None

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
        self.get_characters()
        self.get_terms()
        self.get_quotes()

    def _get_data_from_ul(self, type):
        results = {}
        xpath = '//ul[@class="li_6"]'
        if type == 'Characters':
            if self._characters_html_source:
                ul = self._characters_html_source.xpath(xpath)
            else:
                return results
        elif type == 'Settings':
            if self._settings_html_source:
                ul = self._settings_html_source.xpath(xpath)
            else:
                return results

        elif type == 'Glossary':
            if self._glossary_html_source:
                ul = self._glossary_html_source.xpath(xpath)
            else:
                return results
        else: return results

        for li in ul[0]:
            label = li.getchildren()[0].text
            labelAndDesc = li.xpath("string()")[len(label):]
            descSearch = self.DESC_PAT.search(labelAndDesc)
            desc = descSearch.group(1) if descSearch else None
            results[self._entity_counter] = {'label': label, 'description': desc}
            self._entity_counter += 1
        return results
    
    def get_characters(self):
        self._characters = self._get_data_from_ul('Characters')
        
    def get_terms(self):
        self._terms = self._get_data_from_ul('Settings')
        self._terms.update(self._get_data_from_ul('Glossary'))

    def get_quotes(self):
        if self._quotations_html_source:
            quoteList = self._quotations_html_source.xpath('//ul[@class="li_6"]//li//blockquote/text()')
            self._quotes = [quote[1:-1].lower() for quote in quoteList]
        else:
            self._quotes = []