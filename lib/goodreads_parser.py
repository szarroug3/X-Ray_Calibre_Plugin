# goodreads_parser.py

import re
import base64
import datetime
from lxml import html
from urllib2 import urlopen

# Parses Goodreads page for characters, terms, and quotes
class GoodreadsParser(object):
    BOOK_ID_PAT = re.compile(r'\/show\/([\d]+)')
    ASIN_PAT = re.compile(r'"asin":"(.+?)"')
    def __init__(self, url, connection, raise_error_on_page_not_found=False, create_author_profile=False):
        self._url = url
        self._connection = connection
        self._create_author_profile = create_author_profile
        self._characters = {}
        self._settings = {}
        self._quotes = []
        self._author_profile = None
        self._entity_id = 1

        book_id_search = self.BOOK_ID_PAT.search(url)
        self._goodreads_book_id = book_id_search.group(1) if book_id_search else None

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
        if self._page_source is None:
            return

        self.get_characters()
        self.get_settings()
        self.get_quotes()

        if not self._create_author_profile:
            return

        self.get_author_profile()
        # # don't want to fail if it's just the author profile that fails
        # try:
        #     self.get_author_profile()
        # except:
        #     return

    def get_author_profile(self):
        if self._page_source is None:
            return

        self.get_author_page()
        if self._author_page is None:
            return

        self.get_author_name()
        self.get_author_bio()
        self.get_author_image()
        self.get_author_other_books()
        self.compile_author_profile()

    def open_url(self, url, raise_error_on_page_not_found=False, return_redirect_url=False):
        if 'goodreads.com' in url:
            url = url[url.find('goodreads.com') + len('goodreads.com'):]
        try:
            self._connection.request('GET', url)
            response = self._connection.getresponse()
            if response.status == 301 or response.status == 302:
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
            if response.status == 301 or response.status == 302:
                if return_redirect_url:
                    return response.msg['location']
                response = self.open_url(response.msg['location'])
            else:
                response = response.read()

        if 'Page Not Found' in response:
            raise GoodreadsPageDoesNotExist('Goodreads page not found.')

        return response
    
    def get_characters(self):
        if self._page_source is None:
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
            if char_page is None:
                continue
            desc = char_page.xpath('//div[@class="workCharacterAboutClear"]/text()')
            desc = desc[0].strip() if len(desc) > 0 and desc[0].strip() else 'No description found on Goodreads.'
            aliases = [x.strip() for x in char_page.xpath('//div[@class="grey500BoxContent" and contains(.,"aliases")]/text()') if x.strip()]
            self._characters[entity_id] = {'label': label, 'description': desc, 'aliases': aliases}
            self._entity_id += 1

    def get_settings(self):
        if self._page_source is None:
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
            if setting_page is None:
                continue
            desc = setting_page.xpath('//div[@class="mainContentContainer "]/div[@class="mainContent"]/div[@class="mainContentFloat"]/div[@class="leftContainer"]/span/text()')
            desc = desc[0] if len(desc) > 0 and desc[0].strip() else 'No description found on Goodreads.'
            self._settings[entity_id] = {'label': label, 'description': desc, 'aliases': []}
            self._entity_id += 1

    def get_quotes(self):
        if self._page_source is None:
            return
            
        quotes_page = self._page_source.xpath('//a[@class="actionLink" and contains(., "More quotes")]')
        if len(quotes_page) > 0:
            resp = self.open_url(quotes_page[0].get('href'))
            if not resp:
                return
            quotes_page = html.fromstring(resp)
            if quotes_page is None:
                return
            for quote in quotes_page.xpath('//div[@class="quoteText"]'):
                self._quotes.append(quote.text.encode('ascii', 'ignore').strip())
        else:
            for quote in self._page_source.xpath('//div[@class=" clearFloats bigBox" and contains(., "Quotes from")]//div[@class="bigBoxContent containerWithHeaderContent"]//span[@class="readable"]'):
                self._quotes.append(quote.text.encode('ascii', 'ignore').strip())

    def get_author_page(self):
        if self._page_source is None:
            return

        author_url = self._page_source.xpath('//a[@class="actionLink moreLink"]')[0].get('href')
        self._author_page = html.fromstring(self.open_url(author_url))

    def get_author_name(self):
        if self._author_page is None:
            return

        self._author_name = self._author_page.xpath('//div/h1/span[@itemprop="name"]')[0].text

    def get_author_bio(self):
        if self._author_page is None:
            return

        author_bio = self._author_page.xpath('//div[@class="aboutAuthorInfo"]/span')
        author_bio = author_bio[1] if len(author_bio) > 1 else author_bio[0]

        self._author_bio = ' '.join(author_bio.text_content().split())

    def get_author_image(self):
        if self._author_page is None:
            return

        image_url = self._author_page.xpath('//a[contains(@href, "/photo/author/")]/img')[0].get('src')
        image = urlopen(image_url).read()
        self._author_image = base64.b64encode(image)

    def get_author_other_books(self):
        if self._author_page is None:
            return

        self._author_other_books = []
        current_book_asin = self.open_url('/buttons/glide/' + self._goodreads_book_id)
        for book in self._author_page.xpath('//tr[@itemtype="http://schema.org/Book"]/td/a[@class="bookTitle"]'):
            book_data = {'e': 1, 't': book.find('span').text}
            book_url = book.get('href')

            book_id_search = self.BOOK_ID_PAT.search(book_url)
            if not book_id_search:
                continue
            asin_data_page = self.open_url('/buttons/glide/' + book_id_search.group(1))
            book_asin = self.ASIN_PAT.search(asin_data_page)
            if not book_asin:
                continue
            book_asin = book_asin.group(1)

            # we dont' want to add the current book as an "other book"
            if book_asin != current_book_asin:
                book_data['a'] = book_asin
                self._author_other_books.append(book_data)

    def compile_author_profile(self):
        self._author_profile = {"u": [{"y": 277,
                            "l": [x["a"] for x in self._author_other_books],
                            "n": self._author_name,
                            "b": self._author_bio,
                            "i": self._author_image}],
                    "d": int((datetime.datetime.now() - datetime.datetime(1970,1,1)).total_seconds()),
                    "o": self._author_other_books,
                    "a": book_asin
                }

class GoodreadsPageDoesNotExist(Exception):
    pass