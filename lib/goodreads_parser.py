# goodreads_parser.py
'''Parses goodreads data depending on user settings'''

import os
import re
import json
import copy
import base64
import datetime
import urlparse
from urllib2 import urlopen
from lxml import html

class GoodreadsPageDoesNotExist(Exception):
    '''Exception for when goodreads page does not exist'''
    pass

class GoodreadsParser(object):
    '''Parses Goodreads page for x-ray, author profile, start actions, and end actions as needed'''
    BOOK_ID_PAT = re.compile(r'\/show\/([\d]+)')
    ASIN_PAT = re.compile(r'"asin":"(.+?)"')
    def __init__(self, url, connection, asin, raise_error_on_page_not_found=False, create_xray=False,
                 create_author_profile=False, create_start_actions=False, create_end_actions=False):
        self._url = url
        self._connection = connection
        self._asin = asin
        self._create_xray = create_xray
        self._create_author_profile = create_author_profile
        self._create_start_actions = create_start_actions
        self._create_end_actions = create_end_actions
        self._characters = {}
        self._settings = {}
        self._quotes = []
        self._entity_id = 1

        self._author_info = None
        self._reading_time_hours = None
        self._reading_time_minutes = None
        self._book_image_url = None
        self._num_pages = None
        self._cust_recommendations = None

        self._xray = None
        self._characters = None
        self._settings = None
        self._author_profile = None
        self._start_actions = None
        self._end_actions = None

        book_id_search = self.BOOK_ID_PAT.search(url)
        self._goodreads_book_id = book_id_search.group(1) if book_id_search else None

        response = self._open_url(url)
        self._page_source = None
        if not response:
            return
        self._page_source = html.fromstring(response)

        self._author_recommendations = None
        self._author_other_books = []

        if create_start_actions or create_end_actions:
            dir_path = os.path.join(os.getcwd(), 'lib')
            with open(os.path.join(dir_path, 'goodreads_data_template.json'), 'r') as template:
                goodreads_templates = json.load(template)

            self._start_actions = goodreads_templates['BASE_START_ACTIONS']
            self._end_actions = goodreads_templates['BASE_END_ACTIONS']

    @property
    def xray(self):
        return self._xray

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
    def start_actions(self):
        return self._start_actions

    @property
    def end_actions(self):
        return self._end_actions

    def parse(self):
        '''Parses goodreads for x-ray, author profile, start actions, and end actions depending on user settings'''
        if self._page_source is None:
            return

        if self._create_xray:
            try:
                self._get_xray()
            except:
                pass

        if self._create_author_profile:
            try:
                self._get_author_profile()
            except:
                pass

        if self._create_start_actions:
            try:
                self._get_start_actions()
            except:
                pass

        if self._create_end_actions:
            try:
                self._get_end_actions()
            except:
                return

    def _get_xray(self):
        '''Gets x-ray data from goodreads and creates x-ray dict'''
        self.get_characters()
        self.get_settings()
        self._get_quotes()
        self._compile_xray()

    def _get_author_profile(self):
        '''Gets author profile data from goodreads and creates author profile dict'''
        if self._page_source is None:
            return

        self._get_author_info()
        if len(self._author_info) == 0:
            return

        self._read_primary_author_page()
        self._get_author_other_books()
        self._compile_author_profile()

    def _get_start_actions(self):
        '''Gets start actions data from goodreads and creates start actions dict'''
        if self._page_source is None:
            return

        if not self._create_author_profile:
            self._get_author_info()

        if len(self._author_info) == 0:
            return

        if not self._create_author_profile:
            self._read_primary_author_page()
            self._get_author_other_books()

        self._read_secondary_author_pages()
        self._get_num_pages_and_reading_time()
        self._get_book_image_url()
        self._compile_start_actions()

    def _get_end_actions(self):
        '''Gets end actions data from goodreads and creates end actions dict'''
        if self._page_source is None:
            return

        # these are usually run if we're creating an author profile
        # if it's not, we need to run it to get the author's other books
        if not self._create_author_profile and not self._create_start_actions:
            self._get_author_info()
        if len(self._author_info) == 0:
            return

        if not self._create_author_profile and not self._create_start_actions:
            self._read_primary_author_page()
            self._get_author_other_books()

        if not self._create_start_actions:
            self._read_secondary_author_pages()
            self._get_book_image_url()

        self._get_customer_recommendations()
        self._compile_end_actions()

    def _compile_xray(self):
        '''Compiles x-ray data into dict'''
        self._xray = {'characters': self._characters, 'settings': self._settings, 'quotes': self._quotes}

    def _compile_author_profile(self):
        '''Compiles author profile data into dict'''
        self._author_profile = {'u': [{'y': 277,
                                       'l': [x['a'] for x in self._author_other_books],
                                       'n': self._author_info[0]['name'],
                                       'b': self._author_info[0]['bio'],
                                       'i': self._author_info[0]['encoded_image']}],
                                'd': int((datetime.datetime.now() - datetime.datetime(1970, 1, 1)).total_seconds()),
                                'o': self._author_other_books,
                                'a': self._asin
                               }

    def _compile_start_actions(self):
        '''Compiles start actions data into dict'''
        timestamp = int((datetime.datetime.now() - datetime.datetime(1970, 1, 1)).total_seconds())

        self._start_actions['bookInfo']['asin'] = self._asin
        self._start_actions['bookInfo']['timestamp'] = timestamp
        self._start_actions['bookInfo']['imageUrl'] = self._book_image_url

        data = self._start_actions['data']

        for author in self._author_info:
            # putting fake ASIN because real one isn't needed -- idk why it's required at all
            data['authorBios']['authors'].append({'class': 'authorBio', 'name': author['name'], 'bio': author['bio'],
                                                  'imageUrl': author['image_url'], 'asin': 'XXXXXXXXXX'})

        if self._author_recommendations is not None:
            data['authorRecs'] = {'class': 'featuredRecommendationList', 'recommendations': self._author_recommendations}
            # since we're using the same recommendations from the end actions,
            # we need to replace the class to match what the kindle expects
            for rec in data['authorRecs']['recommendations']:
                rec['class'] = 'recommendation'

        data['bookDescription'] = self._get_book_info_from_tooltips((self._goodreads_book_id,
                                                                     self._book_image_url))[0]
        data['currentBook'] = data['bookDescription']

        data['grokShelfInfo']['asin'] = self._asin

        data['readingPages']['pagesInBook'] = self._num_pages
        for locale, formatted_time in data['readingTime']['formattedTime'].items():
            data['readingTime']['formattedTime'][locale] = formatted_time.format(str(self._reading_time_hours),
                                                                                 str(self._reading_time_minutes))

    def _compile_end_actions(self):
        '''Compiles end actions data into dict'''
        timestamp = int((datetime.datetime.now() - datetime.datetime(1970, 1, 1)).total_seconds())

        self._end_actions['bookInfo']['asin'] = self._asin
        self._end_actions['bookInfo']['timestamp'] = timestamp
        self._end_actions['bookInfo']['imageUrl'] = self._book_image_url

        data = self._end_actions['data']
        for author in self._author_info:
            data['authorBios']['authors'].append({'class': 'authorBio', 'name': author['name'],
                                                  'bio': author['bio'], 'imageUrl': author['image_url']})

        if self._author_recommendations is not None:
            data['authorRecs'] = {'class': 'featuredRecommendationList', 'recommendations': self._author_recommendations}
        if self._cust_recommendations is not None:
            data['customersWhoBoughtRecs'] = {'class': 'featuredRecommendationList',
                                              'recommendations': self._cust_recommendations}

    def _open_url(self, url, raise_error_on_page_not_found=False, return_redirect_url=False):
        '''Tries to open url and return page's html'''
        if 'goodreads.com' in url:
            url = url[url.find('goodreads.com') + len('goodreads.com'):]
        try:
            self._connection.request('GET', url)
            response = self._connection.getresponse()
            if response.status == 301 or response.status == 302:
                if return_redirect_url:
                    return response.msg['location']
                response = self._open_url(response.msg['location'])
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
                response = self._open_url(response.msg['location'])
            else:
                response = response.read()

        if 'Page Not Found' in response:
            raise GoodreadsPageDoesNotExist('Goodreads page not found.')

        return response

    def get_characters(self):
        '''Gets book's character data'''
        if self._page_source is None:
            return

        characters = self._page_source.xpath('//div[@class="clearFloats" and contains(., "Characters")]//div[@class="infoBoxRowItem"]//a')
        self._characters = {}
        for char in characters:
            if '/characters/' not in char.get('href'):
                continue
            label = char.text
            resp = self._open_url(char.get('href'))

            if not resp:
                continue

            char_page = html.fromstring(resp)
            if char_page is None:
                continue

            desc = char_page.xpath('//div[@class="workCharacterAboutClear"]/text()')
            if len(desc) > 0 and re.sub(r'\s+', ' ', desc[0]).strip():
                desc = re.sub(r'\s+', ' ', desc[0]).strip()
            else:
                desc = 'No description found on Goodreads.'

            aliases = [re.sub(r'\s+', ' ', x).strip() for x in char_page.xpath('//div[@class="grey500BoxContent" and contains(.,"aliases")]/text()') if re.sub(r'\s+', ' ', x).strip()]
            self._characters[self._entity_id] = {'label': label, 'description': desc, 'aliases': aliases}
            self._entity_id += 1

    def get_settings(self):
        '''Gets book's setting data'''
        if self._page_source is None:
            return

        settings = self._page_source.xpath('//div[@id="bookDataBox"]/div[@class="infoBoxRowItem"]/a[contains(@href, "/places/")]')
        self._settings = {}
        for setting in settings:
            if '/places/' not in setting.get('href'):
                continue
            label = setting.text
            resp = self._open_url(setting.get('href'))
            if not resp:
                continue
            setting_page = html.fromstring(resp)
            if setting_page is None:
                continue
            desc = setting_page.xpath('//div[@class="mainContentContainer "]/div[@class="mainContent"]/div[@class="mainContentFloat"]/div[@class="leftContainer"]/span/text()')
            desc = desc[0] if len(desc) > 0 and desc[0].strip() else 'No description found on Goodreads.'
            self._settings[self._entity_id] = {'label': label, 'description': desc, 'aliases': []}
            self._entity_id += 1

    def _get_quotes(self):
        '''Gets book's quote data'''
        if self._page_source is None:
            return

        quotes_page = self._page_source.xpath('//a[@class="actionLink" and contains(., "More quotes")]')
        self._quotes = []
        if len(quotes_page) > 0:
            resp = self._open_url(quotes_page[0].get('href'))
            if not resp:
                return
            quotes_page = html.fromstring(resp)
            if quotes_page is None:
                return
            for quote in quotes_page.xpath('//div[@class="quoteText"]'):
                self._quotes.append(re.sub(r'\s+', ' ', quote.text).strip().decode('ascii', 'ignore'))
        else:
            for quote in self._page_source.xpath('//div[@class=" clearFloats bigBox" and contains(., "Quotes from")]//div[@class="bigBoxContent containerWithHeaderContent"]//span[@class="readable"]'):
                self._quotes.append(re.sub(r'\s+', ' ', quote.text).strip().decode('ascii', 'ignore'))

    def _get_author_info(self):
        '''Gets book's author's data'''
        self._author_info = []
        if self._page_source is None:
            return

        for author in self._page_source.xpath('//div[@id="bookAuthors"]/span[@itemprop="author"]//a'):
            author_name = author.find('span[@itemprop="name"]').text.strip()
            author_page = author.get('href')
            if author_name and author_page:
                self._author_info.append({'name': author_name, 'url': author_page})

    def _read_primary_author_page(self):
        '''Rreads primary author's page and gets his/her bio, image url, and image encoded into base64'''
        if len(self._author_info) == 0:
            return

        author = self._author_info[0]
        author['page'] = html.fromstring(self._open_url(author['url']))
        author['bio'] = self._get_author_bio(author['page'])
        author['image_url'], author['encoded_image'] = self._get_author_image(author['page'], encode_image=True)

    def _read_secondary_author_pages(self):
        '''Reads secondary authors' page and gets their bios, image urls, and images encoded into base64'''
        if len(self._author_info) < 2:
            return

        for author in self._author_info[1:]:
            author['page'] = html.fromstring(self._open_url(author['url']))
            author['bio'] = self._get_author_bio(author['page'])
            author['image_url'] = self._get_author_image(author['page'])

    def _get_author_bio(self, author_page):
        '''Gets author's bio from given page'''
        if len(self._author_info) == 0:
            return

        author_bio = author_page.xpath('//div[@class="aboutAuthorInfo"]/span')
        if not author_bio:
            return None

        author_bio = author_bio[1] if len(author_bio) > 1 else author_bio[0]

        return re.sub(r'\s+', ' ', author_bio.text_content()).strip().decode('utf-8').encode('latin-1')

    def _get_author_image(self, author_page, encode_image=False):
        '''Gets author's image url and image encoded into base64 from given page'''
        if len(self._author_info) == 0:
            return

        image_url = author_page.xpath('//a[contains(@href, "/photo/author/")]/img')

        if encode_image:
            if not image_url:
                return None, None
            image = urlopen(image_url[0].get('src')).read()
            encoded_image = base64.b64encode(image)
            return image_url[0].get('src'), encoded_image
        else:
            if not image_url:
                return None
            return image_url[0].get('src')

    def _get_author_other_books(self):
        '''Gets author's other books from given page'''
        if len(self._author_info) == 0:
            return

        book_info = []

        for book in self._author_info[0]['page'].xpath('//tr[@itemtype="http://schema.org/Book"]'):
            book_id = book.find('td//div[@class="u-anchorTarget"]').get('id')

            # don't want to add the current book to the other books list
            if book_id == self._goodreads_book_id:
                continue

            image_url = book.find('td//img[@class="bookSmallImg"]').get('src').split('/')
            image_url = '{0}/{1}l/{2}'.format('/'.join(image_url[:-2]), image_url[-2][:-1], image_url[-1])

            book_info.append((book_id, image_url))

        self._author_recommendations = self._get_book_info_from_tooltips(book_info)
        self._author_other_books = [{'e': 1, 't': info['title'], 'a': info['asin']} for info in self._author_recommendations]

    def _get_customer_recommendations(self):
        '''Gets customer recommendations from current book'''
        if self._page_source is None:
            return

        book_info = []
        for book in self._page_source.xpath('//div[@class="bookCarousel"]/div[@class="carouselRow"]/ul/li/a'):
            book_url = book.get('href')
            book_id_search = self.BOOK_ID_PAT.search(book_url)
            book_id = book_id_search.group(1) if book_id_search else None

            if book_id and book_id != self._goodreads_book_id:
                image_url = book.find('img').get('src')
                book_info.append((book_id, image_url))

        self._cust_recommendations = self._get_book_info_from_tooltips(book_info)

    def _get_book_info_from_tooltips(self, book_info):
        '''Gets books ASIN, title, authors, image url, description, and rating information'''
        if isinstance(book_info, tuple):
            book_info = [book_info]
        books_data = []
        link_pattern = 'resources[Book.{0}][type]=Book&resources[Book.{0}][id]={0}'
        tooltips_page_url = '/tooltips?' + "&".join([link_pattern.format(book_id) for book_id, image_url in book_info])
        tooltips_page_info = json.loads(self._open_url(tooltips_page_url))['tooltips']

        for book_id, image_url in book_info:
            book_data = tooltips_page_info['Book.{0}'.format(book_id)]
            if not book_data:
                continue
            book_data = html.fromstring(book_data)

            title = book_data.xpath('//a[contains(@class, "readable")]')[0].text
            authors = [book_data.xpath('//a[contains(@class, "authorName")]')[0].text]
            rating_info = book_data.xpath('//div[@class="bookRatingAndPublishing"]/span[@class="minirating"]')
            if len(rating_info) > 0:
                rating_string = rating_info[0].text_content().strip().replace(',', '').split()
                rating = float(rating_string[rating_string.index('avg')-1])
                num_of_reviews = int(rating_string[-2])
            else:
                rating = None
                num_of_reviews = None

            try:
                asin_elements = book_data.xpath('//a[contains(@class, "kindlePreviewButtonIcon")]/@href')
                book_asin = urlparse.parse_qs(urlparse.urlsplit(asin_elements[0]).query)["asin"][0]
            except:
                book_asin = None

            # We should get the ASIN from the tooltips file, but just in case we'll
            # keep this as a fallback (though this only works in some regions - just USA?)
            if not book_asin:
                asin_data_page = self._open_url('/buttons/glide/' + book_id)
                book_asin = self.ASIN_PAT.search(asin_data_page)
                if not book_asin:
                    continue
                book_asin = book_asin.group(1)

            if len(book_data.xpath('//div[@class="addBookTipDescription"]//span[not(contains(@id, "freeTextContainer"))]')) > 0:
                desc = re.sub(r'\s+', ' ', book_data.xpath('//div[@class="addBookTipDescription"]//span[not(contains(@id, "freeTextContainer"))]')[0].text).strip()
            elif len(book_data.xpath('//div[@class="addBookTipDescription"]//span[contains(@id, "freeTextContainer")]')) > 0:
                desc = re.sub(r'\s+', ' ', book_data.xpath('//div[@class="addBookTipDescription"]//span[contains(@id, "freeTextContainer")]')[0].text).strip()
            else:
                continue

            books_data.append({'class': "featuredRecommendation",
                               'asin': book_asin,
                               'title': title,
                               'authors': authors,
                               'imageUrl': image_url,
                               'description': desc,
                               'hasSample': False,
                               'amazonRating': rating,
                               'numberOfReviews': num_of_reviews})

        return books_data

    def _get_book_image_url(self):
        '''Gets book's image url'''
        self._book_image_url = self._page_source.xpath('//div[@class="mainContent"]//div[@id="imagecol"]//img[@id="coverImage"]')[0].get('src')

    def _get_num_pages_and_reading_time(self):
        '''Gets book's number of pages and time to read'''
        if self._page_source is None:
            return

        self._num_pages = int(self._page_source.xpath('//span[@itemprop="numberOfPages"]')[0].text.split()[0])
        total_minutes = self._num_pages * 2
        self._reading_time_hours = total_minutes / 60
        self._reading_time_minutes = total_minutes - (self._reading_time_hours * 60)
