# goodreads_parser.py

import base64
import datetime
from lxml import html

# Parses Goodreads page for characters, terms, and quotes
class GoodreadsParser(object):
    def __init__(self, url, connection, raise_error_on_page_not_found=False, create_author_profile=False):
        self._url = url
        self._connection = connection
        self._get_author_profile = get_author_profile
        self._characters = {}
        self._settings = {}
        self._quotes = []
        self._author_profile = None
        self._entity_id = 1

        response = self.open_url(url)
        self._page_source = None
        if not response:
            return
        self._page_source = html.fromstring(response)

    @property
    def characters(self):
        return self._characters

    @property
    def settings(self):
        return self._settings

    @property
    def author_profile(self):
        return self._author_profile
    
    
    @property
    def quotes(self):
        return self._quotes

    def parse(self):
        if not self._page_source:
            return

        self.get_characters()
        self.get_settings()
        self.get_quotes()

        if not create_author_profile:
            return

        self.get_author_profile()

    def get_author_profile(self):
        if not self._page_source:
            return

        self.get_author_page()
        if not self._author_page:
            return

        self.get_author_name()
        self.get_author_bio()
        self.get_author_image()
        self.get_author_other_books()
        self.create_author_profile()

    def open_url(self, url, raise_error_on_page_not_found=False, return_redirect_url=False):
        if 'goodreads.com' in url:
            url = url[url.find('goodreads.com') + len('goodreads.com'):]
        try:
            self._connection.request('GET', url)
            response = self._connection.getresponse()
            if response.status == 300 or response.status == 301:
                if return_redirect_url:
                    return response.msg['location']
                response = self.open_url(response.msg['location'])
            else:
                response = response.read()
        except GoodreadsPageDoesNotExist as e:
            if raise_error_on_page_not_found:
                raise e
            else:
                return None
        except:
            self._connection.close()
            self._connection.connect()
            self._connection.request('GET', url)
            response = self._connection.getresponse()
            if response.status == 300 or response.status == 301:
                if return_redirect_url:
                    return response.msg['location']
                response = self.open_url(response.msg['location'])
            else:
                response = response.read()

        if 'Page Not Found' in response:
            raise GoodreadsPageDoesNotExist('Goodreads page not found.')

        return response
    
    def get_characters(self):
        if not self._page_source is None:
            return

        characters = self._page_source.xpath('//div[@class="clearFloats" and contains(., "Characters")]//div[@class="infoBoxRowItem"]//a')
        for entity_id, char in enumerate(characters, start=self._entity_id):
            if '/characters/' not in char.get('href'):
                continue
            label = char.text
            resp = self.open_url(char.get('href'))
            if not resp:
                continue
            char_page = html.fromstring(resp)
            desc = char_page.xpath('//div[@class="workCharacterAboutClear"]/text()')
            desc = desc[0].strip() if len(desc) > 0 and desc[0].strip() else 'No description found on Goodreads.'
            aliases = [x.strip() for x in char_page.xpath('//div[@class="grey500BoxContent" and contains(.,"aliases")]/text()') if x.strip()]
            self._characters[entity_id] = {'label': label, 'description': desc, 'aliases': aliases}
            self._entity_id += 1

    def get_settings(self):
        if not self._page_source:
            return
            
        settings = self._page_source.xpath('//div[@id="bookDataBox"]/div[@class="infoBoxRowItem"]/a[contains(@href, "/places/")]')
        for entity_id, setting in enumerate(settings, start=self._entity_id):
            if '/places/' not in setting.get('href'):
                continue
            label = setting.text
            resp = self.open_url(self.open_url(setting.get('href')))
            if not resp:
                continue
            setting_page = html.fromstring(resp)
            desc = setting_page.xpath('//div[@class="mainContentContainer "]/div[@class="mainContent"]/div[@class="mainContentFloat"]/div[@class="leftContainer"]/span/text()')
            desc = desc[0] if len(desc) > 0 and desc[0].strip() else 'No description found on Goodreads.'
            self._settings[entity_id] = {'label': label, 'description': desc, 'aliases': []}
            self._entity_id += 1

    def get_quotes(self):
        if not self._page_source:
            return
            
        quotes_page = self._page_source.xpath('//a[@class="actionLink" and contains(., "More quotes")]')
        if len(quotes_page) > 0:
            resp = self.open_url(quotes_page[0].get('href'))
            if not resp:
                return
            quotes_page = html.fromstring(resp)
            for quote in quotes_page.xpath('//div[@class="quoteText"]'):
                self._quotes.append(quote.text.encode('ascii', 'ignore').strip())
        else:
            for quote in self._page_source.xpath('//div[@class=" clearFloats bigBox" and contains(., "Quotes from")]//div[@class="bigBoxContent containerWithHeaderContent"]//span[@class="readable"]'):
                self._quotes.append(quote.text.encode('ascii', 'ignore').strip())

    def get_author_page(self):
        if not self._page_source:
            return

        author_url = self._page_source.xpath('//a[@class="actionLink moreLink"]')[0].get('href')
        self._author_page = html.fromstring(self.open_url(author_url))

    def get_author_name(self):
        if not self._author_page:
            return

        self._author_name = self._author_page.xpath('//div/h1/span[@itemprop="name"]')[0].text

    def get_author_bio(self):
        if not self._author_page:
            return

        self._author_bio = ' '.join(self._author_page.xpath('//div[@class="aboutAuthorInfo"]/span[contains(@id, "freeTextauthor")]')[0].text_content().split())

    def get_author_image(self):
        if not self._author_page:
            return

        image_url = self._author_page.xpath('//a[contains(@href, "/photo/author/")]/img')[0].get('src')
        image = urlopen(image_url).read()
        self._author_image = base64.b64encode(image)

    def get_author_other_books(self):
        if not self._author_page:
            return

        self._author_other_books = []
        books = self._author_page.xpath('//tr[@itemtype="http://schema.org/Book"]/td/a[@class="bookTitle"]')
        for book in books:
            book_data = {'e': 1}
            book_data['t'] = book.find('span').text
            book_page = self.open_url(book.get('href'))
            if not book_page:
                continue
            book_amazon_page = book_page.xpath('//div[@id="asyncBuyButtonContainer"]//a[contains(text(), "Amazon")]')
            if len(book_amazon_page) == 0:
                continue
            book_amazon_page = self.open_url(book_amazon_page[0], return_redirect_url=True)
            if not book_amazon_page:
                continue
            book_asin = book_amazon_page.split('/')
            book_asin = book_asin[book_asin.index('product')+1]
            book_data['a'] = book_asin
            self._author_other_books.append(book_data)

    def create_author_profile(self):
        self._author_profile = {'u': [{'y': 277,
                            'l': [x['a'] for x in self._author_other_books],
                            'n': self._author_name,
                            'b': self._author_bio,
                            'i': self._author_image}],
                    'd': int((datetime.datetime.now() - datetime.datetime(1970,1,1)).total_seconds()),
                    'o': self._author_other_books
                }

class GoodreadsPageDoesNotExist(Exception):
    pass