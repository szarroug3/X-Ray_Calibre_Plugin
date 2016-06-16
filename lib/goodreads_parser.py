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
        self._characters = {}
        self._settings = {}
        self._quotes = []
        self._entity_id = 1

    @property
    def characters(self):
        return self._characters

    @property
    def settings(self):
        return self._settings
    
    @property
    def quotes(self):
        return self._quotes

    def parse(self):
        self.get_characters()
        self.get_settings()
        self.get_quotes()
        print '-'*100
        print self._characters
        print '-'*100
        print self._settings
        print '-'*100
        print self._quotes
        print '-'*100
    
    def get_characters(self):
        characters = self._page_source.xpath('//div[@class="clearFloats" and contains(., "Characters")]//div[@class="infoBoxRowItem"]//a')
        for entity_id, char in enumerate(characters, start=self._entity_id):
            if '/characters/' not in char.get('href'):
                continue
            label = char.text
            char_page = html.fromstring(self._opener.open('https://www.goodreads.com' + char.get('href')).read())
            desc = char_page.xpath('//div[@class="workCharacterAboutClear"]/text()')
            desc = desc[0].strip() if len(desc) > 0 else ''
            aliases = [x.strip() for x in char_page.xpath('//div[@class="grey500BoxContent" and contains(.,"aliases")]/text()') if x.strip()]
            self._characters[entity_id] = {'label': label, 'description': desc, 'aliases': aliases}
            self._entity_id += 1

    def get_settings(self):
        settings = self._page_source.xpath('//div[@id="bookDataBox"]/div[@class="infoBoxRowItem"]/a[contains(@href, "/places/")]')
        for entity_id, setting in enumerate(settings, start=self._entity_id):
            if '/places/' not in setting.get('href'):
                continue
            label = setting.text
            setting_page = html.fromstring(self._opener.open('https://www.goodreads.com' + setting.get('href')).read())
            desc = setting_page.xpath('//div[@class="mainContentContainer "]/div[@class="mainContent"]/div[@class="mainContentFloat"]/div[@class="leftContainer"]/span/text()')
            desc = desc[0] if len(desc) > 0 else ''
            self._settings[entity_id] = {'label': label, 'description': desc, 'aliases': []}
            self._entity_id += 1

    def get_quotes(self):
        quotes_page = self._page_source.xpath('//a[@class="actionLink" and contains(., "More quotes")]')
        if len(quotes_page) > 0:
            quotes_page = html.fromstring(self._opener.open('https://www.goodreads.com' + quotes_page[0].get('href')).read())
            for quote in quotes_page.xpath('//div[@class="quoteText"]'):
                self._quotes.append(quote.text.encode('ascii', 'ignore').strip())
        else:
            for quote in self._page_source.xpath('//div[@class=" clearFloats bigBox" and contains(., "Quotes from")]//div[@class="bigBoxContent containerWithHeaderContent"]//span[@class="readable"]'):
                self._quotes.append(quote.text.encode('ascii', 'ignore').strip())