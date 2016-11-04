# goodreads_parser.py
'''Parses goodreads data depending on user settings'''

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
    def __init__(self, url, connection, asin, raise_error_on_page_not_found=False,
                 create_xray=False, create_author_profile=False, create_end_actions=False,
                 create_start_actions=False):
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
        self._start_actions = copy.deepcopy(self.BASE_START_ACTIONS)

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
        self._end_actions = copy.deepcopy(self.BASE_END_ACTIONS)

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




    BASE_END_ACTIONS = {
        u"bookInfo": {
            u"class": u"bookInfo",
            u"contentType": u"EBOK",
            u"refTagSuffix": u"AAAgAAB",
        },
        u"widgets": [{
            u"id": u"ratingAndReviewWidget",
            u"class": u"rateAndReview",
            u"metricsTag": u"rr",
            u"options": {
                u"refTagPartial": u"rr",
                u"showShareComponent": False
            }
        }, {
            u"id": u"sharingWidget",
            u"class": u"sharing",
            u"metricsTag": u"sh"
        }, {
            u"id": u"ratingAndSharingWidget",
            u"metricsTag": u"rsh",
            u"options": {
                u"refTagPartial": u"rsw"
            },
            u"class": u"ratingAndSharing"
        }, {
            u"id": u"authorRecsListWidgetWithTitle",
            u"metricsTag": u"rat",
            u"options": {
                u"dataKey": u"authorRecs",
                u"refTagPartial": u"r_a"
            },
            u"class": u"list",
            u"strings": {
                u"title": {
                    u"de": u"Mehr von %{authorList}",
                    u"en": u"More by %{authorList}",
                    u"en-US": u"More by %{authorList}",
                    u"es": u"M\u00E1s de %{authorList}",
                    u"fr": u"Autres livres de %{authorList}",
                    u"it": u"Altri di %{authorList}",
                    u"ja": u"%{authorList}\u306E\u305D\u306E\u4ED6\u306E\u672C",
                    u"nl": u"Meer van %{authorList}",
                    u"pt-BR": u"Mais por %{authorList}",
                    u"ru": u"\u0411\u043E\u043B\u044C\u0448\u0435 \u043F\u0440\u043E\u0438\u0437\u0432\u0435\u0434\u0435\u043D\u0438\u0439, \u043D\u0430\u043F\u0438\u0441\u0430\u043D\u043D\u044B\u0445 %{authorList}",
                    u"zh-CN": u"\u66F4\u591A%{authorList}\u4F5C\u54C1"
                }
            }
        }, {
            u"id": u"authorRecsShovelerWidgetWithTitlePlaceholders",
            u"metricsTag": u"ratn",
            u"options": {
                u"dataKey": u"authorRecs",
                u"refTagPartial": u"r_a"
            },
            u"class": u"shoveler",
            u"strings": {
                u"title": {
                    u"de": u"Mehr von %{authorList}",
                    u"en": u"More by %{authorList}",
                    u"en-US": u"More by %{authorList}",
                    u"es": u"M\u00E1s de %{authorList}",
                    u"fr": u"Autres livres de %{authorList}",
                    u"it": u"Altri di %{authorList}",
                    u"ja": u"%{authorList}\u306E\u305D\u306E\u4ED6\u306E\u672C",
                    u"nl": u"Meer van %{authorList}",
                    u"pt-BR": u"Mais por %{authorList}",
                    u"ru": u"\u0411\u043E\u043B\u044C\u0448\u0435 \u043F\u0440\u043E\u0438\u0437\u0432\u0435\u0434\u0435\u043D\u0438\u0439, \u043D\u0430\u043F\u0438\u0441\u0430\u043D\u043D\u044B\u0445 %{authorList}",
                    u"zh-CN": u"\u66F4\u591A%{authorList}\u4F5C\u54C1"
                }
            }
        }, {
            u"id": u"customerRecsListWidgetWithTitle",
            u"metricsTag": u"rpt",
            u"options": {
                u"dataKey": u"customersWhoBoughtRecs",
                u"refTagPartial": u"r_p"
            },
            u"class": u"list",
            u"strings": {
                u"title": {
                    u"de": u"Kunden, die dieses Buch gekauft haben, kauften auch",
                    u"en": u"Customers who bought this book also bought",
                    u"en-US": u"Customers who bought this book also bought",
                    u"es": u"Los clientes que compraron este libro tambi\u00E9n compraron",
                    u"fr": u"Les clients ayant achet\u00E9 ce livre ont \u00E9galement achet\u00E9",
                    u"it": u"I clienti che hanno acquistato questo libro hanno acquistato anche",
                    u"ja": u"\u3053\u306E\u672C\u3092\u8CB7\u3063\u305F\u4EBA\u306F\u3053\u3093\u306A\u5546\u54C1\u3082\u8CB7\u3063\u3066\u3044\u307E\u3059",
                    u"nl": u"Klanten die dit boek kochten, kochten ook",
                    u"pt-BR": u"Clientes que compraram este eBook tamb\u00E9m compraram",
                    u"ru": u"\u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0438, \u043A\u0443\u043F\u0438\u0432\u0448\u0438\u0435 \u044D\u0442\u0443 \u043A\u043D\u0438\u0433\u0443, \u0442\u0430\u043A\u0436\u0435 \u043A\u0443\u043F\u0438\u043B\u0438",
                    u"zh-CN": u"\u8D2D\u4E70\u672C\u4E66\u7684\u987E\u5BA2\u8FD8\u4E70\u8FC7"
                }
            }
        }, {
            u"id": u"customerRecsShovelerWidgetWithTitle",
            u"metricsTag": u"rpt",
            u"options": {
                u"dataKey": u"customersWhoBoughtRecs",
                u"refTagPartial": u"r_p"
            },
            u"class": u"shoveler",
            u"strings": {
                u"title": {
                    u"de": u"Kunden, die dieses Buch gekauft haben, kauften auch",
                    u"en": u"Customers who bought this book also bought",
                    u"en-US": u"Customers who bought this book also bought",
                    u"es": u"Los clientes que compraron este libro tambi\u00E9n compraron",
                    u"fr": u"Les clients ayant achet\u00E9 ce livre ont \u00E9galement achet\u00E9",
                    u"it": u"I clienti che hanno acquistato questo libro hanno acquistato anche",
                    u"ja": u"\u3053\u306E\u672C\u3092\u8CB7\u3063\u305F\u4EBA\u306F\u3053\u3093\u306A\u5546\u54C1\u3082\u8CB7\u3063\u3066\u3044\u307E\u3059",
                    u"nl": u"Klanten die dit boek kochten, kochten ook",
                    u"pt-BR": u"Clientes que compraram este eBook tamb\u00E9m compraram",
                    u"ru": u"\u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0438, \u043A\u0443\u043F\u0438\u0432\u0448\u0438\u0435 \u044D\u0442\u0443 \u043A\u043D\u0438\u0433\u0443, \u0442\u0430\u043A\u0436\u0435 \u043A\u0443\u043F\u0438\u043B\u0438",
                    u"zh-CN": u"\u8D2D\u4E70\u672C\u4E66\u7684\u987E\u5BA2\u8FD8\u4E70\u8FC7"
                }
            }
        }, {
            u"id": u"citationRecsListWidgetWithTitle",
            u"metricsTag": u"rct",
            u"options": {
                u"dataKey": u"citationRecs",
                u"refTagPartial": u"r_c"
            },
            u"class": u"list",
            u"strings": {
                u"title": {
                    u"de": u"In diesem Buch erw\u00E4hnt",
                    u"en": u"Mentioned in this book",
                    u"en-US": u"Mentioned in this book",
                    u"es": u"Mencionado en este libro",
                    u"fr": u"Mentionn\u00E9s dans ce livre",
                    u"it": u"Menzionati in questo libro",
                    u"ja": u"\u3053\u306E\u4F5C\u54C1\u306B\u51FA\u3066\u304F\u308B\u672C",
                    u"nl": u"Genoemd in dit boek",
                    u"pt-BR": u"Mencionado neste eBook",
                    u"ru": u"\u0423\u043F\u043E\u043C\u0438\u043D\u0430\u0435\u0442\u0441\u044F \u0432 \u044D\u0442\u043E\u0439 \u043A\u043D\u0438\u0433\u0435",
                    u"zh-CN": u"\u672C\u4E66\u63D0\u53CA\u7684"
                }
            }
        }, {
            u"id": u"citationRecsShovelerWidgetWithTitle",
            u"metricsTag": u"rct",
            u"options": {
                u"dataKey": u"citationRecs",
                u"refTagPartial": u"r_c"
            },
            u"class": u"shoveler",
            u"strings": {
                u"title": {
                    u"de": u"In diesem Buch erw\u00E4hnt",
                    u"en": u"Mentioned in this book",
                    u"en-US": u"Mentioned in this book",
                    u"es": u"Mencionado en este libro",
                    u"fr": u"Mentionn\u00E9s dans ce livre",
                    u"it": u"Menzionati in questo libro",
                    u"ja": u"\u3053\u306E\u4F5C\u54C1\u306B\u51FA\u3066\u304F\u308B\u672C",
                    u"nl": u"Genoemd in dit boek",
                    u"pt-BR": u"Mencionado neste eBook",
                    u"ru": u"\u0423\u043F\u043E\u043C\u0438\u043D\u0430\u0435\u0442\u0441\u044F \u0432 \u044D\u0442\u043E\u0439 \u043A\u043D\u0438\u0433\u0435",
                    u"zh-CN": u"\u672C\u4E66\u63D0\u53CA\u7684"
                }
            }
        }, {
            u"id": u"aboutTheAuthorWidgetWithTitle",
            u"metricsTag": u"atat",
            u"options": {
                u"dataKey": u"authorBios",
                u"refTagPartial": u"r_ata",
                u"subscriptionInfoDataKey": u"authorSubscriptions",
                u"followInfoDataKey": u"followSubscriptions"
            },
            u"class": u"authors",
            u"strings": {
                u"title": {
                    u"de": u"\u00DCber den Autor",
                    u"en": u"About the author",
                    u"en-US": u"About the author",
                    u"es": u"Acerca del autor",
                    u"fr": u"\u00C0 propos de l'auteur",
                    u"it": u"Informazioni sull'autore",
                    u"ja": u"\u8457\u8005\u306B\u3064\u3044\u3066",
                    u"nl": u"Over de auteur",
                    u"pt-BR": u"Informa\u00E7\u00F5es do autor",
                    u"ru": u"\u041E\u0431 \u0430\u0432\u0442\u043E\u0440\u0435",
                    u"zh-CN": u"\u5173\u4E8E\u4F5C\u8005"
                }
            }
        }, {
            u"id": u"grokRatingAndReviewWidget",
            u"class": u"grokRateAndReview",
            u"metricsTag": u"grr",
            u"options": {
                u"refTagPartial": u"grr",
                u"showShareComponent": False
            }
        }, {
            u"id": u"grokRatingWidget",
            u"class": u"grokRate",
            u"metricsTag": u"gr",
            u"options": {
                u"refTagPartial": u"gr",
                u"showShareComponent": False
            }
        }, {
            u"id": u"askAReaderWidget",
            u"metricsTag": u"aar",
            u"options": {
                u"dataKey": u"askAReaderQuestion"
            },
            u"class": u"askAReader",
            u"strings": {
                u"title": {
                    u"de": u"Leser-Fragen und -Antworten",
                    u"en": u"Reader Q&A",
                    u"en-US": u"Reader Q&A",
                    u"es": u"Preguntas frecuentes del lector",
                    u"fr": u"Questions-r\u00E9ponses",
                    u"it": u"Q&A Lettore",
                    u"ja": u"\u8AAD\u8005\u306B\u3088\u308B\u8CEA\u554F\u3068\u56DE\u7B54",
                    u"nl": u"Lezersvragen",
                    u"pt-BR": u"Perguntas e respostas do leitor",
                    u"ru": u"\u0412\u043E\u043F\u0440\u043E\u0441\u044B \u0438 \u043E\u0442\u0432\u0435\u0442\u044B \u0447\u0438\u0442\u0430\u0442\u0435\u043B\u0435\u0439",
                    u"zh-CN": u"\u8BFB\u8005\u95EE\u7B54"
                }
            }
        }, {
            u"id": u"ratingWidget",
            u"class": u"ratingBar",
            u"metricsTag": u"ro",
            u"options": {
                u"refTagPartial": u"ro",
                u"showShareComponent": False
            }
        }, {
            u"id": u"followTheAuthorWidgetWithTitle",
            u"metricsTag": u"ftat",
            u"options": {
                u"dataKey": u"authorSubscriptions",
                u"refTagPartial": u"r_fta",
                u"followInfoDataKey": u"followSubscriptions"
            },
            u"class": u"followTheAuthor",
            u"strings": {
                u"title": {
                    u"de": u"Bleiben Sie auf dem neuesten Stand",
                    u"en": u"Stay up to date",
                    u"en-US": u"Stay up to date",
                    u"es": u"Mantente actualizado",
                    u"fr": u"Rester \u00E0 jour",
                    u"it": u"Rimani aggiornato",
                    u"ja": u"\u6700\u65B0\u60C5\u5831\u3092\u30D5\u30A9\u30ED\u30FC",
                    u"nl": u"Blijf op de hoogte",
                    u"pt-BR": u"Mantenha-se atualizado",
                    u"ru": u"\u0411\u0443\u0434\u044C\u0442\u0435 \u0432 \u043A\u0443\u0440\u0441\u0435 \u043F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0445 \u0441\u043E\u0431\u044B\u0442\u0438\u0439!",
                    u"zh-CN": u"\u4FDD\u6301\u66F4\u65B0"
                }
            }
        }, {
            u"id": u"shareWithFriendWidget",
            u"metricsTag": u"swf",
            u"options": {
                u"refTagPartial": u"swf"
            },
            u"class": u"shareWithFriend",
            u"strings": {
                u"buttonText": {
                    u"de": u"Empfehlen",
                    u"en": u"Recommend",
                    u"en-US": u"Recommend",
                    u"es": u"Recomendar",
                    u"fr": u"Recommander",
                    u"it": u"Consiglia",
                    u"ja": u"\u7D39\u4ECB",
                    u"nl": u"Aanraden",
                    u"pt-BR": u"Recomendar",
                    u"ru": u"\u041F\u043E\u0440\u0435\u043A\u043E\u043C\u0435\u043D\u0434\u043E\u0432\u0430\u0442\u044C",
                    u"zh-CN": u"\u63A8\u8350"
                },
                u"bodyText": {
                    u"de": u"Empfehlen Sie es einem/r Freund/in.",
                    u"en": u"Recommend it to a friend.",
                    u"en-US": u"Recommend it to a friend.",
                    u"es": u"Recomi\u00E9ndaselo a un amigo.",
                    u"fr": u"Recommandez-le \u00E0 un ami.",
                    u"it": u"Consiglialo a un amico.",
                    u"ja": u"\u53CB\u9054\u306B\u3082\u7D39\u4ECB\u3057\u307E\u3057\u3087\u3046\u3002",
                    u"nl": u"Raad het een vriend aan.",
                    u"pt-BR": u"Recomende-o a um amigo.",
                    u"ru": u"\u041F\u043E\u0440\u0435\u043A\u043E\u043C\u0435\u043D\u0434\u0443\u0439\u0442\u0435 \u0435\u0435 \u0434\u0440\u0443\u0433\u0443.",
                    u"zh-CN": u"\u5411\u597D\u53CB\u63A8\u8350\u5427\u3002"
                },
                u"title": {
                    u"de": u"Gefiel Ihnen dieses Buch?",
                    u"en": u"Enjoyed this book?",
                    u"en-US": u"Enjoyed this book?",
                    u"es": u"\u00BFTe ha gustado este libro?",
                    u"fr": u"Vous avez aim\u00E9 ce livre\u00A0?",
                    u"it": u"Ti \u00E8 piaciuto questo libro?",
                    u"ja": u"\u3053\u306E\u672C\u3092\u304A\u697D\u3057\u307F\u3044\u305F\u3060\u3051\u307E\u3057\u305F\u304B?",
                    u"nl": u"Vond u dit boek leuk?",
                    u"pt-BR": u"Gostou deste eBook?",
                    u"ru": u"\u041F\u043E\u043D\u0440\u0430\u0432\u0438\u043B\u0430\u0441\u044C \u044D\u0442\u0430 \u043A\u043D\u0438\u0433\u0430?",
                    u"zh-CN": u"\u559C\u6B22\u672C\u4E66\uFF1F"
                }
            }
        }, {
            u"id": u"buyThisBookWidget",
            u"metricsTag": u"bn",
            u"options": {
                u"buyInStore": False,
                u"buyButtonVisible": True,
                u"dataIsCurrentBook": True,
                u"refTagPartial": u"bn",
                u"oneClickBorrowSupported": False,
                u"showWishListButton": False
            },
            u"class": u"singleRec"
        }, {
            u"id": u"nextInSeriesWidget",
            u"metricsTag": u"nist",
            u"options": {
                u"dataKey": u"nextBook",
                u"buyInStore": False,
                u"buyButtonVisible": True,
                u"dataIsCurrentBook": False,
                u"refTagPartial": u"r_nis",
                u"oneClickBorrowSupported": False,
                u"showWishListButton": False
            },
            u"class": u"singleRec",
            u"strings": {
                u"title": {
                    u"de": u"N\u00E4chster Teil der Serie",
                    u"en": u"Next in Series",
                    u"en-US": u"Next in series",
                    u"es": u"Siguiente de la serie",
                    u"fr": u"Prochain tome",
                    u"it": u"Prossimo della serie",
                    u"ja": u"\u30B7\u30EA\u30FC\u30BA\u306E\u6B21\u5DFB",
                    u"nl": u"Volgende in de reeks",
                    u"pt-BR": u"Pr\u00F3ximo da s\u00E9rie",
                    u"ru": u"\u0421\u043B\u0435\u0434\u0443\u044E\u0449\u0430\u044F \u043A\u043D\u0438\u0433\u0430 \u0441\u0435\u0440\u0438\u0438",
                    u"zh-CN": u"\u4E1B\u4E66\u4E0B\u4E00\u90E8"
                }
            }
        }, {
            u"id": u"recommendedForYouWidget",
            u"metricsTag": u"rfy",
            u"options": {
                u"dataKey": u"specialRec",
                u"buyInStore": False,
                u"buyButtonVisible": True,
                u"dataIsCurrentBook": False,
                u"refTagPartial": u"rfy",
                u"oneClickBorrowSupported": False,
                u"showWishListButton": False
            },
            u"class": u"singleRec",
            u"strings": {
                u"title": {
                    u"de": u"Empfehlungen f\u00FCr Sie",
                    u"en": u"Recommended for you",
                    u"en-US": u"Recommended for you",
                    u"es": u"Recomendaciones",
                    u"fr": u"Recommand\u00E9 pour vous",
                    u"it": u"Consigliati per te",
                    u"ja": u"\u304A\u3059\u3059\u3081",
                    u"nl": u"Aanbevolen voor u",
                    u"pt-BR": u"Recomendados para voc\u00EA",
                    u"ru": u"\u0420\u0435\u043A\u043E\u043C\u0435\u043D\u0434\u0430\u0446\u0438\u0438 \u0434\u043B\u044F \u0432\u0430\u0441",
                    u"zh-CN": u"\u4E3A\u60A8\u63A8\u8350"
                }
            }
        }, {
            u"id": u"authorRecsBookGridWidgetWithTitle",
            u"metricsTag": u"rat",
            u"options": {
                u"dataKey": u"authorRecs",
                u"buyInStore": False,
                u"buyButtonVisible": True,
                u"showBadges": True,
                u"refTagPartial": u"r_a",
                u"oneClickBorrowSupported": False,
                u"showWishListButton": False
            },
            u"class": u"bookGrid",
            u"strings": {
                u"title": {
                    u"de": u"Mehr von %{authorList}",
                    u"en": u"More by %{authorList}",
                    u"en-US": u"More by %{authorList}",
                    u"es": u"M\u00E1s de %{authorList}",
                    u"fr": u"Autres livres de %{authorList}",
                    u"it": u"Altri di %{authorList}",
                    u"ja": u"%{authorList}\u306E\u305D\u306E\u4ED6\u306E\u672C",
                    u"nl": u"Meer van %{authorList}",
                    u"pt-BR": u"Mais por %{authorList}",
                    u"ru": u"\u0411\u043E\u043B\u044C\u0448\u0435 \u043F\u0440\u043E\u0438\u0437\u0432\u0435\u0434\u0435\u043D\u0438\u0439, \u043D\u0430\u043F\u0438\u0441\u0430\u043D\u043D\u044B\u0445 %{authorList}",
                    u"zh-CN": u"\u66F4\u591A%{authorList}\u4F5C\u54C1"
                }
            }
        }, {
            u"id": u"customerRecsBookGridWidgetWithTitle",
            u"metricsTag": u"rpt",
            u"options": {
                u"dataKey": u"customersWhoBoughtRecs",
                u"buyInStore": False,
                u"buyButtonVisible": True,
                u"showBadges": True,
                u"refTagPartial": u"r_p",
                u"oneClickBorrowSupported": False,
                u"showWishListButton": False
            },
            u"class": u"bookGrid",
            u"strings": {
                u"title": {
                    u"de": u"Kunden, die dieses Buch gekauft haben, kauften auch",
                    u"en": u"Customers who bought this book also bought",
                    u"en-US": u"Customers who bought this book also bought",
                    u"es": u"Los clientes que compraron este libro tambi\u00E9n compraron",
                    u"fr": u"Les clients ayant achet\u00E9 ce livre ont \u00E9galement achet\u00E9",
                    u"it": u"I clienti che hanno acquistato questo libro hanno acquistato anche",
                    u"ja": u"\u3053\u306E\u672C\u3092\u8CB7\u3063\u305F\u4EBA\u306F\u3053\u3093\u306A\u5546\u54C1\u3082\u8CB7\u3063\u3066\u3044\u307E\u3059",
                    u"nl": u"Klanten die dit boek kochten, kochten ook",
                    u"pt-BR": u"Clientes que compraram este eBook tamb\u00E9m compraram",
                    u"ru": u"\u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0438, \u043A\u0443\u043F\u0438\u0432\u0448\u0438\u0435 \u044D\u0442\u0443 \u043A\u043D\u0438\u0433\u0443, \u0442\u0430\u043A\u0436\u0435 \u043A\u0443\u043F\u0438\u043B\u0438",
                    u"zh-CN": u"\u8D2D\u4E70\u672C\u4E66\u7684\u987E\u5BA2\u8FD8\u4E70\u8FC7"
                }
            }
        }, {
            u"id": u"citationRecsBookGridWidgetWithTitle",
            u"metricsTag": u"rct",
            u"options": {
                u"dataKey": u"citationRecs",
                u"buyInStore": False,
                u"buyButtonVisible": True,
                u"showBadges": True,
                u"refTagPartial": u"r_c",
                u"oneClickBorrowSupported": False,
                u"showWishListButton": False
            },
            u"class": u"bookGrid",
            u"strings": {
                u"title": {
                    u"de": u"In diesem Buch erw\u00E4hnt",
                    u"en": u"Mentioned in this book",
                    u"en-US": u"Mentioned in this book",
                    u"es": u"Mencionado en este libro",
                    u"fr": u"Mentionn\u00E9s dans ce livre",
                    u"it": u"Menzionati in questo libro",
                    u"ja": u"\u3053\u306E\u4F5C\u54C1\u306B\u51FA\u3066\u304F\u308B\u672C",
                    u"nl": u"Genoemd in dit boek",
                    u"pt-BR": u"Mencionado neste eBook",
                    u"ru": u"\u0423\u043F\u043E\u043C\u0438\u043D\u0430\u0435\u0442\u0441\u044F \u0432 \u044D\u0442\u043E\u0439 \u043A\u043D\u0438\u0433\u0435",
                    u"zh-CN": u"\u672C\u4E66\u63D0\u53CA\u7684"
                }
            }
        }],
        u"layouts": [{
            u"metricsTag": u"vl",
            u"class": u"verticalList",
            u"widgetPlacements": {
                u"body": [
                    ["ratingAndReviewWidget"],
                    ["sharingWidget"],
                    ["recommendedForYouWidget"],
                    ["nextInSeriesWidget"],
                    ["authorRecsBookGridWidgetWithTitle"],
                    ["customerRecsBookGridWidgetWithTitle"],
                    ["citationRecsBookGridWidgetWithTitle"],
                    ["followTheAuthorWidgetWithTitle"],
                    ["askAReaderWidget"]
                ]
            },
            u"requiredWidgets": ["ratingAndReviewWidget", u"sharingWidget"]
        }, {
            u"metricsTag": u"vl",
            u"class": u"verticalList",
            u"widgetPlacements": {
                u"body": [
                    ["grokRatingAndReviewWidget", u"ratingAndReviewWidget", u"grokRatingWidget", u"ratingWidget"],
                    ["recommendedForYouWidget"],
                    ["nextInSeriesWidget"],
                    ["authorRecsBookGridWidgetWithTitle"],
                    ["customerRecsBookGridWidgetWithTitle"],
                    ["citationRecsBookGridWidgetWithTitle"],
                    ["followTheAuthorWidgetWithTitle"],
                    ["askAReaderWidget"]
                ]
            }
        }],
        u"data": {
            u"customerProfile": {
                u"class": u"customerProfile",
                u"penName": u"Anonymous",
                u"realName": u"Anonymous"
            },
            u"authorBios": {
                u"class": u"authorBioList",
                u"authors": []
            }
        }
    }

    BASE_START_ACTIONS = {
        u"bookInfo":{
            u"class":u"bookInfo",
            u"contentType":u"EBOK",
            u"refTagSuffix":u"AAAgAAA"
        },
        u"widgets":[
            {
                u"id":u"welcomeTextWidget",
                u"metricsTag":u"wtw",
                u"options":{
                    u"dataKey":u"welcomeText",
                    u"displayLimitKey":u"welcomeWidget",
                    u"displayLimit":1
                },
                u"class":u"simpleText"
            },
            {
                u"id":u"timeToReadWidget",
                u"metricsTag":u"ttr",
                u"options":{
                    u"timeDataKey":u"readingTime",
                    u"pageDataKey":u"readingPages"
                },
                u"class":u"readingTime"
            },
            {
                u"id":u"xray",
                u"metricsTag":u"xray",
                u"options":{
                    u"preferredTypeOrder":[
                        u"images"
                    ],
                    u"imagesThreshold":4,
                    u"imagesFormat":u"mosaic"
                },
                u"class":u"xrayTeaser",
                u"strings":{
                    u"imagesDescription":{
                        u"de":u"Bl\u00e4ttern Sie durch alle %{numImages}-Bilder in diesem Buch.",
                        u"en":u"Flip through all %{numImages} images in the book.",
                        u"en-US":u"Flip through all %{numImages} images in the book.",
                        u"es":u"Hojear todas las %{numImages} im\u00e1genes del libro.",
                        u"fr":u"Feuilleter les %{numImages} images de ce livre.",
                        u"it":u"Sfoglia tutte le %{numImages} immagini nel libro.",
                        u"ja":u"\u3053\u306e\u672c\u306e%{numImages}\u500b\u306e\u753b\u50cf\u3059\u3079\u3066\u3092\u898b\u3089\u308c\u307e\u3059\u3002",
                        u"nl":u"Blader door alle %{numImages} afbeeldingen in het boek.",
                        u"pt-BR":u"Percorrer todas as %{numImages} imagens no eBook.",
                        u"ru":u"\u041f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435 \u0432\u0441\u0435 %{numImages} \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0439 \u0432 \u043a\u043d\u0438\u0433\u0435.",
                        u"zh-CN":u"\u6d4f\u89c8\u4e66\u4e2d\u5168\u90e8 %{numImages} \u5f20\u56fe\u7247\u3002"
                    },
                    u"imagesButtonText":{
                        u"de":u"Alle Bilder ansehen",
                        u"en":u"See All Images",
                        u"en-US":u"See All Images",
                        u"es":u"Ver todas las im\u00e1genes",
                        u"fr":u"Voir toutes les images",
                        u"it":u"Vedi tutte le immagini",
                        u"ja":u"\u3059\u3079\u3066\u306e\u753b\u50cf\u3092\u898b\u308b",
                        u"nl":u"Alle afbeeldingen weergeven",
                        u"pt-BR":u"Ver todas as imagens",
                        u"ru":u"\u041f\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u0442\u044c \u0432\u0441\u0435 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f",
                        u"zh-CN":u"\u67e5\u770b\u5168\u90e8\u56fe\u7247"
                    },
                    u"entitiesButtonText":{
                        u"de":u"\u00d6ffnen Sie X-Ray",
                        u"en-US":u"Open X-Ray",
                        u"ru":u"\u041e\u0442\u043a\u0440\u044b\u0442\u044c X-Ray",
                        u"pt-BR":u"Abrir X-Ray",
                        u"ja":u"X-Ray\u3092\u958b\u304f",
                        u"en":u"Open X-Ray",
                        u"it":u"Apri X-Ray",
                        u"fr":u"Ouvrir X-Ray",
                        u"zh-CN":u"\u6253\u5f00X-Ray",
                        u"es":u"Abrir X-Ray",
                        u"nl":u"X-Ray openen"
                    },
                    u"entitiesDescription":{
                        u"de":u"Durchsuchen Sie Leute, Ausdr\u00fccke und Bilder in diesem Buch.",
                        u"en":u"Explore people, terms and images in this book.",
                        u"en-US":u"Explore people, terms, and images in this book.",
                        u"es":u"Explora personas, t\u00e9rminos e im\u00e1genes de este libro.",
                        u"fr":u"Explorer les personnages, les termes et les images de ce livre.",
                        u"it":u"Esplora persone, termini e immagini in questo libro.",
                        u"ja":u"\u3053\u306e\u672c\u306e\u767b\u5834\u4eba\u7269\u3001\u30c8\u30d4\u30c3\u30af\u3001\u753b\u50cf\u3092\u4e00\u5ea6\u306b\u78ba\u8a8d\u3067\u304d\u307e\u3059\u3002",
                        u"nl":u"Mensen, termen en afbeeldingen in dit boek ontdekken.",
                        u"pt-BR":u"Explorar pessoas, termos e imagens neste eBook.",
                        u"ru":u"\u0418\u0437\u0443\u0447\u0430\u0439\u0442\u0435 \u043b\u044e\u0434\u0435\u0439, \u0442\u0435\u0440\u043c\u0438\u043d\u044b \u0438 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f \u0432 \u044d\u0442\u043e\u0439 \u043a\u043d\u0438\u0433\u0435.",
                        u"zh-CN":u"\u63a2\u7d22\u672c\u4e66\u4e2d\u7684\u4eba\u7269\u3001\u672f\u8bed\u548c\u56fe\u7247\u3002"
                    }
                }
            },
            {
                u"id":u"kuTeaserWidget",
                u"metricsTag":u"dtb",
                u"options":{
                    u"dynamicButtonDataKey":u"kuTeaserData",
                    u"dynamicButtonActionKey":u"kuUrlAction",
                    u"displayIfClicked":True,
                    u"clickOnlyOnce":False,
                    u"displayLimitKey":u"kuTeaserWidget",
                    u"refTagPartial":u"r_kut",
                    u"featureKey":u"kuTeaser",
                    u"displayLimit":3
                },
                u"class":u"dynamicButtonWidget"
            },
            {
                u"id":u"positionInSeriesWidgetWithText",
                u"metricsTag":u"pist",
                u"options":{
                    u"seriesPositionDataKey":u"seriesPosition"
                },
                u"class":u"positionInSeries",
                u"strings":{
                    u"text":{
                        u"de":u"Dies ist das Buch Nr. %{position} von %{total} der Serie %{seriesName}",
                        u"en":u"This is book %{position} of %{total} in %{seriesName}",
                        u"en-US":u"This is book %{position} of %{total} in %{seriesName}",
                        u"es":u"Este es el libro %{position} de %{total} en %{seriesName}",
                        u"fr":u"Ce livre est le %{position}e sur %{total} de la s\u00e9rie %{seriesName}",
                        u"it":u"Questo libro \u00e8 il %{position} libro su %{total} libri nella serie %{seriesName}",
                        u"ja":u"\u3053\u306e\u672c\u306f%{seriesName}\u306e\u5168%{total}\u518a\u306e\u3046\u3061%{position}\u518a\u76ee\u3067\u3059\u3002",
                        u"nl":u"Dit is boek %{position} van %{total} van %{seriesName}",
                        u"pt-BR":u"Esse \u00e9 o eBook %{position} de %{total} em %{seriesName}",
                        u"ru":u"\u042d\u0442\u043e \u043a\u043d\u0438\u0433\u0430 %{position} \u0438\u0437 %{total} \u0432 \u0441\u0435\u0440\u0438\u0438 \u00ab%{seriesName}\u00bb",
                        u"zh-CN":u"\u8fd9\u662f %{seriesName} \u4e2d\u7684\u7b2c %{position} \u672c\u56fe\u4e66\uff08\u5171 %{total} \u672c\uff09"
                    }
                }
            },
            {
                u"id":u"previousBookInTheSeriesWidget",
                u"metricsTag":u"pbits",
                u"options":{
                    u"dataKey":u"previousBookInTheSeries",
                    u"refTagPartial":u"pbits"
                },
                u"class":u"bookDetail",
                u"strings":{
                    u"title":{
                        u"de":u"Vorherige B\u00fccher der Serie:u",
                        u"en":u"Previous book in the series:u",
                        u"en-US":u"Previous book in the series:u",
                        u"es":u"Libros anteriores de la serie:u",
                        u"fr":u"Livre pr\u00e9c\u00e9dent dans la s\u00e9rie\u00a0:u",
                        u"it":u"Libro precedente nella serie:u",
                        u"ja":u"\u30b7\u30ea\u30fc\u30ba\u306e\u524d\u5dfb:u",
                        u"nl":u"Vorige boek in de reeks:u",
                        u"pt-BR":u"eBook anterior da s\u00e9rie",
                        u"ru":u"\u041f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0430\u044f \u043a\u043d\u0438\u0433\u0430 \u0441\u0435\u0440\u0438\u0438:u",
                        u"zh-CN":u"\u7cfb\u5217\u4e2d\u7684\u4e0a\u4e00\u672c\u56fe\u4e66\uff1a"
                    }
                }
            },
            {
                u"id":u"aboutTheAuthorWidget",
                u"metricsTag":u"ata",
                u"options":{
                    u"dataKey":u"authorBios",
                    u"refTagPartial":u"r_ata",
                    u"subscriptionInfoDataKey":u"authorSubscriptions",
                    u"followInfoDataKey":u"followSubscriptions"
                },
                u"class":u"authors"
            },
            {
                u"id":u"authorNamesListWidget",
                u"metricsTag":u"anl",
                u"options":{
                    u"dataKey":u"authorNames",
                    u"refTagPartial":u"r_anl"
                },
                u"class":u"authorNames"
            },
            {
                u"id":u"authorRecsShovelerWidget",
                u"metricsTag":u"ra",
                u"options":{
                    u"dataKey":u"authorRecs",
                    u"refTagPartial":u"r_a"
                },
                u"class":u"shoveler"
            },
            {
                u"id":u"authorRecsShovelerWidgetWithTitleNoPlaceholderSingleAuthor",
                u"metricsTag":u"ratsa",
                u"options":{
                    u"dataKey":u"authorRecs",
                    u"refTagPartial":u"r_a"
                },
                u"class":u"shoveler",
                u"strings":{
                    u"title":{
                        u"de":u"Mehr vom Autor",
                        u"en":u"More by the author",
                        u"en-US":u"More by the author",
                        u"es":u"M\u00e1s por el autor",
                        u"fr":u"Autres livres du m\u00eame auteur",
                        u"it":u"Altri titoli dell'autore",
                        u"ja":u"\u3053\u306e\u8457\u8005\u306e\u305d\u306e\u4ed6\u306e\u4f5c\u54c1",
                        u"nl":u"Meer van de auteur",
                        u"pt-BR":u"Mais do autor",
                        u"ru":u"\u0411\u043e\u043b\u044c\u0448\u0435 \u043f\u0440\u043e\u0438\u0437\u0432\u0435\u0434\u0435\u043d\u0438\u0439 \u0430\u0432\u0442\u043e\u0440\u0430",
                        u"zh-CN":u"\u8be5\u4f5c\u8005\u7684\u66f4\u591a\u4f5c\u54c1"
                    }
                }
            },
            {
                u"id":u"authorRecsShovelerWidgetWithTitleNoPlaceholderMultipleAuthors",
                u"metricsTag":u"ratma",
                u"options":{
                    u"dataKey":u"authorRecs",
                    u"refTagPartial":u"r_a"
                },
                u"class":u"shoveler",
                u"strings":{
                    u"title":{
                        u"de":u"Mehr von den Autoren",
                        u"en":u"More by the authors",
                        u"en-US":u"More by the authors",
                        u"es":u"M\u00e1s por autores",
                        u"fr":u"Autres livres des m\u00eames auteurs",
                        u"it":u"Altri titoli degli autori",
                        u"ja":u"\u3053\u308c\u3089\u306e\u8457\u8005\u306e\u4ed6\u306e\u4f5c\u54c1",
                        u"nl":u"Meer van de auteurs",
                        u"pt-BR":u"Mais dos autores",
                        u"ru":u"\u0411\u043e\u043b\u044c\u0448\u0435 \u043f\u0440\u043e\u0438\u0437\u0432\u0435\u0434\u0435\u043d\u0438\u0439 \u0430\u0432\u0442\u043e\u0440\u043e\u0432",
                        u"zh-CN":u"\u8fd9\u4e9b\u4f5c\u8005\u7684\u66f4\u591a\u4f5c\u54c1"
                    }
                }
            },
            {
                u"id":u"markAsReadingWidget",
                u"metricsTag":u"gmar",
                u"options":{
                    u"dataKey":u"grokShelfInfo"
                },
                u"class":u"markReading"
            },
            {
                u"id":u"grokTeaserWidget",
                u"class":u"grokTeaser",
                u"metricsTag":u"gt",
                u"options":{
                    u"displayLimitKey":u"grokTeaser",
                    u"displayLimit":3
                }
            },
            {
                u"id":u"upsell3PPhoneAppWidget",
                u"metricsTag":u"us3pa",
                u"options":{
                    u"dynamicButtonDataKey":u"upsell3PPhoneAppData",
                    u"dynamicButtonActionKey":u"upsell3PPhoneAppUrlAction",
                    u"displayIfClicked":True,
                    u"clickOnlyOnce":False,
                    u"displayLimitKey":u"upsell3PPhoneAppWidget",
                    u"refTagPartial":u"r_us3pa",
                    u"featureKey":u"upsell3PPhoneApp",
                    u"displayLimit":3
                },
                u"class":u"dynamicButtonWidget"
            },
            {
                u"id":u"audibleNarration",
                u"metricsTag":u"audnar",
                u"options":{
                    u"refTagPartial":u"r_aud"
                },
                u"class":u"audible"
            },
            {
                u"id":u"citationRecsShovelerWidget",
                u"metricsTag":u"rc",
                u"options":{
                    u"dataKey":u"citationRecs",
                    u"refTagPartial":u"r_c"
                },
                u"class":u"shoveler"
            },
            {
                u"id":u"readerSettingsWidget",
                u"class":u"readerSettings",
                u"metricsTag":u"rs"
            },
            {
                u"id":u"leftNavCitationsFeaturedList",
                u"metricsTag":u"lnrc",
                u"options":{
                    u"dataKey":u"leftNavCitationRecs",
                    u"refTagPartial":u"ln_r_c"
                },
                u"class":u"featuredList",
                u"strings":{
                    u"panelRowTitle":{
                        u"de":u"In diesem Buch erw\u00e4hnt",
                        u"en":u"Mentioned in this Book",
                        u"en-US":u"Mentioned in this Book",
                        u"es":u"Mencionado en este libro",
                        u"fr":u"Mentionn\u00e9s dans ce livre",
                        u"it":u"Menzionati in questo libro",
                        u"ja":u"\u3053\u306e\u4f5c\u54c1\u306b\u51fa\u3066\u304f\u308b\u672c",
                        u"nl":u"Genoemd in dit boek",
                        u"pt-BR":u"Mencionado neste eBook",
                        u"ru":u"\u0423\u043f\u043e\u043c\u0438\u043d\u0430\u0435\u0442\u0441\u044f \u0432 \u044d\u0442\u043e\u0439 \u043a\u043d\u0438\u0433\u0435",
                        u"zh-CN":u"\u672c\u4e66\u63d0\u53ca\u7684"
                    },
                    u"title":{
                        u"de":u"In diesem Buch erw\u00e4hnt",
                        u"en":u"Mentioned in this Book",
                        u"en-US":u"Mentioned in this Book",
                        u"es":u"Mencionado en este libro",
                        u"fr":u"Mentionn\u00e9s dans ce livre",
                        u"it":u"Menzionati in questo libro",
                        u"ja":u"\u3053\u306e\u4f5c\u54c1\u306b\u51fa\u3066\u304f\u308b\u672c",
                        u"nl":u"Genoemd in dit boek",
                        u"pt-BR":u"Mencionado neste eBook",
                        u"ru":u"\u0423\u043f\u043e\u043c\u0438\u043d\u0430\u0435\u0442\u0441\u044f \u0432 \u044d\u0442\u043e\u0439 \u043a\u043d\u0438\u0433\u0435",
                        u"zh-CN":u"\u672c\u4e66\u63d0\u53ca\u7684"
                    }
                }
            },
            {
                u"id":u"bookDescriptionWidget",
                u"metricsTag":u"bd",
                u"options":{
                    u"dataKey":u"bookDescription",
                    u"refTagPartial":u"r_bd"
                },
                u"class":u"bookDetail",
                u"strings":{
                    u"title":{
                        u"de":u"Buchbeschreibung, Bewertungen, Rezensionen und mehr",
                        u"en":u"Book description, ratings, reviews and more",
                        u"en-US":u"Book description, ratings, reviews and more",
                        u"es":u"Descripci\u00f3n del libro, calificaciones, rese\u00f1as y m\u00e1s",
                        u"fr":u"Description du livre, \u00e9valuations, commentaires et plus",
                        u"it":u"Descrizione libro, valutazioni, recensioni e altro",
                        u"ja":u"\u672c\u306e\u8a73\u7d30\u3001\u8a55\u4fa1\u3001\u30ec\u30d3\u30e5\u30fc\u306a\u3069",
                        u"nl":u"Beschrijving van het boek, beoordelingen, recensies en meer",
                        u"pt-BR":u"Descri\u00e7\u00e3o de eBook, classifica\u00e7\u00f5es, avalia\u00e7\u00f5es e muito mais",
                        u"ru":u"\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435 \u043a\u043d\u0438\u0433\u0438, \u043e\u0446\u0435\u043d\u043a\u0438, \u043e\u0442\u0437\u044b\u0432\u044b \u0438 \u0434\u0440.",
                        u"zh-CN":u"\u56fe\u4e66\u63cf\u8ff0\u3001\u8bc4\u5206\u53ca\u5176\u4ed6"
                    }
                }
            },
            {
                u"id":u"headerWidget",
                u"metricsTag":u"hdrw",
                u"options":{
                    u"dataKey":u"currentBook",
                    u"refTagPartial":u"hdrw",
                    u"initialLines":-1,
                    u"moreLines":-1
                },
                u"class":u"header",
                u"strings":{
                    u"title":{
                        u"de":u"Beschreibung",
                        u"en":u"Description",
                        u"en-US":u"Description",
                        u"es":u"Descripci\u00f3n",
                        u"fr":u"Description",
                        u"it":u"Descrizione",
                        u"ja":u"\u8aac\u660e",
                        u"nl":u"Beschrijving",
                        u"pt-BR":u"Descri\u00e7\u00e3o",
                        u"ru":u"\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435",
                        u"zh-CN":u"\u63cf\u8ff0"
                    }
                }
            },
            {
                u"id":u"authorRecsBookGridWidgetBuyButtonNotVisible",
                u"metricsTag":u"ra",
                u"options":{
                    u"dataKey":u"authorFeaturedRecs",
                    u"buyInStore":False,
                    u"buyButtonVisible":False,
                    u"refTagPartial":u"r_a"
                },
                u"class":u"bookGrid"
            },
            {
                u"id":u"authorRecsBookGridWidgetWithTitleSingleAuthorBuyButtonNotVisible",
                u"metricsTag":u"ratsa",
                u"options":{
                    u"dataKey":u"authorFeaturedRecs",
                    u"buyInStore":False,
                    u"buyButtonVisible":False,
                    u"refTagPartial":u"r_a"
                },
                u"class":u"bookGrid",
                u"strings":{
                    u"title":{
                        u"de":u"Mehr vom Autor",
                        u"en":u"More by the author",
                        u"en-US":u"More by the author",
                        u"es":u"M\u00e1s por el autor",
                        u"fr":u"Autres livres du m\u00eame auteur",
                        u"it":u"Altri titoli dell'autore",
                        u"ja":u"\u3053\u306e\u8457\u8005\u306e\u305d\u306e\u4ed6\u306e\u4f5c\u54c1",
                        u"nl":u"Meer van de auteur",
                        u"pt-BR":u"Mais do autor",
                        u"ru":u"\u0411\u043e\u043b\u044c\u0448\u0435 \u043f\u0440\u043e\u0438\u0437\u0432\u0435\u0434\u0435\u043d\u0438\u0439 \u0430\u0432\u0442\u043e\u0440\u0430",
                        u"zh-CN":u"\u8be5\u4f5c\u8005\u7684\u66f4\u591a\u4f5c\u54c1"
                    }
                }
            },
            {
                u"id":u"authorRecsBookGridWidgetWithTitleMultipleAuthorsBuyButtonNotVisible",
                u"metricsTag":u"ratma",
                u"options":{
                    u"dataKey":u"authorFeaturedRecs",
                    u"buyInStore":False,
                    u"buyButtonVisible":False,
                    u"refTagPartial":u"r_a"
                },
                u"class":u"bookGrid",
                u"strings":{
                    u"title":{
                        u"de":u"Mehr von den Autoren",
                        u"en":u"More by the authors",
                        u"en-US":u"More by the authors",
                        u"es":u"M\u00e1s por autores",
                        u"fr":u"Autres livres des m\u00eames auteurs",
                        u"it":u"Altri titoli degli autori",
                        u"ja":u"\u3053\u308c\u3089\u306e\u8457\u8005\u306e\u4ed6\u306e\u4f5c\u54c1",
                        u"nl":u"Meer van de auteurs",
                        u"pt-BR":u"Mais dos autores",
                        u"ru":u"\u0411\u043e\u043b\u044c\u0448\u0435 \u043f\u0440\u043e\u0438\u0437\u0432\u0435\u0434\u0435\u043d\u0438\u0439 \u0430\u0432\u0442\u043e\u0440\u043e\u0432",
                        u"zh-CN":u"\u8fd9\u4e9b\u4f5c\u8005\u7684\u66f4\u591a\u4f5c\u54c1"
                    }
                }
            },
            {
                u"id":u"authorRecsBookGridWidgetBuyInApp",
                u"metricsTag":u"ra",
                u"options":{
                    u"dataKey":u"authorFeaturedRecs",
                    u"buyInStore":False,
                    u"buyButtonVisible":True,
                    u"refTagPartial":u"r_a"
                },
                u"class":u"bookGrid"
            },
            {
                u"id":u"authorRecsBookGridWidgetWithTitleSingleAuthorBuyInApp",
                u"metricsTag":u"ratsa",
                u"options":{
                    u"dataKey":u"authorFeaturedRecs",
                    u"buyInStore":False,
                    u"buyButtonVisible":True,
                    u"refTagPartial":u"r_a"
                },
                u"class":u"bookGrid",
                u"strings":{
                    u"title":{
                        u"de":u"Mehr vom Autor",
                        u"en":u"More by the author",
                        u"en-US":u"More by the author",
                        u"es":u"M\u00e1s por el autor",
                        u"fr":u"Autres livres du m\u00eame auteur",
                        u"it":u"Altri titoli dell'autore",
                        u"ja":u"\u3053\u306e\u8457\u8005\u306e\u305d\u306e\u4ed6\u306e\u4f5c\u54c1",
                        u"nl":u"Meer van de auteur",
                        u"pt-BR":u"Mais do autor",
                        u"ru":u"\u0411\u043e\u043b\u044c\u0448\u0435 \u043f\u0440\u043e\u0438\u0437\u0432\u0435\u0434\u0435\u043d\u0438\u0439 \u0430\u0432\u0442\u043e\u0440\u0430",
                        u"zh-CN":u"\u8be5\u4f5c\u8005\u7684\u66f4\u591a\u4f5c\u54c1"
                    }
                }
            },
            {
                u"id":u"authorRecsBookGridWidgetWithTitleMultipleAuthorsBuyInApp",
                u"metricsTag":u"ratma",
                u"options":{
                    u"dataKey":u"authorFeaturedRecs",
                    u"buyInStore":False,
                    u"buyButtonVisible":True,
                    u"refTagPartial":u"r_a"
                },
                u"class":u"bookGrid",
                u"strings":{
                    u"title":{
                        u"de":u"Mehr von den Autoren",
                        u"en":u"More by the authors",
                        u"en-US":u"More by the authors",
                        u"es":u"M\u00e1s por autores",
                        u"fr":u"Autres livres des m\u00eames auteurs",
                        u"it":u"Altri titoli degli autori",
                        u"ja":u"\u3053\u308c\u3089\u306e\u8457\u8005\u306e\u4ed6\u306e\u4f5c\u54c1",
                        u"nl":u"Meer van de auteurs",
                        u"pt-BR":u"Mais dos autores",
                        u"ru":u"\u0411\u043e\u043b\u044c\u0448\u0435 \u043f\u0440\u043e\u0438\u0437\u0432\u0435\u0434\u0435\u043d\u0438\u0439 \u0430\u0432\u0442\u043e\u0440\u043e\u0432",
                        u"zh-CN":u"\u8fd9\u4e9b\u4f5c\u8005\u7684\u66f4\u591a\u4f5c\u54c1"
                    }
                }
            },
            {
                u"id":u"citationRecsBookGridWidgetBuyButtonNotVisible",
                u"metricsTag":u"rc",
                u"options":{
                    u"dataKey":u"citationFeaturedRecs",
                    u"buyInStore":True,
                    u"buyButtonVisible":False,
                    u"refTagPartial":u"r_c"
                },
                u"class":u"bookGrid"
            },
            {
                u"id":u"citationRecsBookGridWidgetBuyInApp",
                u"metricsTag":u"rc",
                u"options":{
                    u"dataKey":u"citationFeaturedRecs",
                    u"buyInStore":False,
                    u"buyButtonVisible":True,
                    u"refTagPartial":u"r_c"
                },
                u"class":u"bookGrid"
            }
        ],
        u"layouts":[
            {
                u"metricsTag":u"glf",
                u"options":{
                    u"providesHeaderInfo":True
                },
                u"class":u"groupedLayoutWithFooter",
                u"strings":{
                    u"seriesGroup":{
                        u"de":u"Infos zur Serie",
                        u"en":u"About the series",
                        u"en-US":u"About the series",
                        u"es":u"Acerca de la serie",
                        u"fr":u"\u00c0 propos de cette s\u00e9rie",
                        u"it":u"Informazioni sulle serie",
                        u"ja":u"\u3053\u306e\u30b7\u30ea\u30fc\u30ba\u306b\u3064\u3044\u3066",
                        u"nl":u"Over de reeks",
                        u"pt-BR":u"Informa\u00e7\u00f5es da s\u00e9rie",
                        u"ru":u"\u041e\u0431 \u044d\u0442\u043e\u0439 \u0441\u0435\u0440\u0438\u0438",
                        u"zh-CN":u"\u5173\u4e8e\u7cfb\u5217"
                    },
                    u"xrayGroup":{
                        u"de":u"X-Ray",
                        u"en-US":u"X-Ray",
                        u"ru":u"X-Ray",
                        u"pt-BR":u"X-Ray",
                        u"ja":u"X-Ray",
                        u"en":u"X-Ray",
                        u"it":u"X-Ray",
                        u"fr":u"X-Ray",
                        u"zh-CN":u"X-Ray",
                        u"es":u"X-Ray",
                        u"nl":u"X-Ray"
                    },
                    u"authorsGroupWithSingleAuthor":{
                        u"de":u"\u00dcber den Autor",
                        u"en":u"About the author",
                        u"en-US":u"About the author",
                        u"es":u"Acerca del autor",
                        u"fr":u"\u00c0 propos de l'auteur",
                        u"it":u"Informazioni sull'autore",
                        u"ja":u"\u8457\u8005\u306b\u3064\u3044\u3066",
                        u"nl":u"Over de auteur",
                        u"pt-BR":u"Informa\u00e7\u00f5es do autor",
                        u"ru":u"\u041e\u0431 \u0430\u0432\u0442\u043e\u0440\u0435",
                        u"zh-CN":u"\u5173\u4e8e\u4f5c\u8005"
                    },
                    u"readingTimeGroup":{
                        u"de":u"Typische Lesezeit",
                        u"en":u"Typical time to read",
                        u"en-US":u"Typical time to read",
                        u"es":u"Tiempo de lectura t\u00edpico",
                        u"fr":u"Temps de lecture typique",
                        u"it":u"Tempo di lettura tipico",
                        u"ja":u"\u8aad\u307f\u7d42\u3048\u308b\u307e\u3067\u306e\u5e73\u5747\u7684\u306a\u6642\u9593",
                        u"nl":u"Gebruikelijke leestijd",
                        u"pt-BR":u"Tempo t\u00edpico para leitura",
                        u"ru":u"\u0421\u0440\u0435\u0434\u043d\u0435\u0435 \u0432\u0440\u0435\u043c\u044f \u0447\u0442\u0435\u043d\u0438\u044f",
                        u"zh-CN":u"\u5e38\u89c4\u9605\u8bfb\u65f6\u95f4"
                    },
                    u"citationsGroup":{
                        u"de":u"In diesem Buch erw\u00e4hnt",
                        u"en":u"Mentioned in this book",
                        u"en-US":u"Mentioned in this book",
                        u"es":u"Mencionado en este libro",
                        u"fr":u"Mentionn\u00e9s dans ce livre",
                        u"it":u"Menzionati in questo libro",
                        u"ja":u"\u3053\u306e\u4f5c\u54c1\u306b\u51fa\u3066\u304f\u308b\u672c",
                        u"nl":u"Genoemd in dit boek",
                        u"pt-BR":u"Mencionado neste eBook",
                        u"ru":u"\u0423\u043f\u043e\u043c\u0438\u043d\u0430\u0435\u0442\u0441\u044f \u0432 \u044d\u0442\u043e\u0439 \u043a\u043d\u0438\u0433\u0435",
                        u"zh-CN":u"\u672c\u4e66\u63d0\u53ca\u7684"
                    },
                    u"welcomeGroup":{
                        u"de":u"Willkommen!",
                        u"en":u"Welcome!",
                        u"en-US":u"Welcome!",
                        u"es":u"\u00a1Bienvenido!",
                        u"fr":u"Bienvenue\u00a0!",
                        u"it":u"Benvenuto!",
                        u"ja":u"\u3088\u3046\u3053\u305d!",
                        u"nl":u"Welkom",
                        u"pt-BR":u"Bem-vindo!",
                        u"ru":u"\u0414\u043e\u0431\u0440\u043e \u043f\u043e\u0436\u0430\u043b\u043e\u0432\u0430\u0442\u044c!",
                        u"zh-CN":u"\u6b22\u8fce\uff01"
                    },
                    u"audibleGroup":{
                        u"de":u"Auf Audible-Erz\u00e4hlung erweitern",
                        u"en":u"Upgrade to Audible Narration",
                        u"en-US":u"Upgrade to Audible Narration",
                        u"es":u"Actualizar a narraci\u00f3n Audible",
                        u"fr":u"Passer \u00e0 la narration Audible",
                        u"it":u"Passa alla narrazione Audible",
                        u"ja":u"Audible\u30ca\u30ec\u30fc\u30b7\u30e7\u30f3\u3078\u30a2\u30c3\u30d7\u30b0\u30ec\u30fc\u30c9",
                        u"nl":u"Upgraden naar Audible Narration",
                        u"pt-BR":u"Atualizar para narra\u00e7\u00e3o Audible",
                        u"ru":u"\u041f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f \u043a \u0437\u0430\u043a\u0430\u0434\u0440\u043e\u0432\u043e\u043c\u0443 \u0442\u0435\u043a\u0441\u0442\u0443 Audible",
                        u"zh-CN":u"\u5347\u7ea7\u5230\u3016Audible Narration\u3017"
                    }
                },
                u"widgetPlacements":{
                    u"footer":[
                        {
                            u"widgetSlots":[
                                [
                                    u"readerSettingsWidget"
                                ]
                            ]
                        }
                    ],
                    u"body":[
                        {
                            u"titleKey":u"welcomeGroup",
                            u"widgetSlots":[
                                [
                                    u"welcomeTextWidget"
                                ]
                            ]
                        },
                        {
                            u"widgetSlots":[
                                [
                                    u"headerWidget"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"readingTimeGroup",
                            u"widgetSlots":[
                                [
                                    u"timeToReadWidget"
                                ]
                            ]
                        },
                        {
                            u"widgetSlots":[
                                [
                                    u"markAsReadingWidget"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"audibleGroup",
                            u"widgetSlots":[
                                [
                                    u"audibleNarration"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"seriesGroup",
                            u"widgetSlots":[
                                [
                                    u"positionInSeriesWidgetWithText"
                                ],
                                [
                                    u"previousBookInTheSeriesWidget"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"authorsGroupWithSingleAuthor",
                            u"widgetSlots":[
                                [
                                    u"aboutTheAuthorWidget"
                                ],
                                [
                                    u"authorNamesListWidget"
                                ],
                                [
                                    u"authorRecsBookGridWidgetWithTitleSingleAuthorBuyInApp",
                                    u"authorRecsShovelerWidgetWithTitleNoPlaceholderSingleAuthor"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"xrayGroup",
                            u"widgetSlots":[
                                [
                                    u"xray"
                                ]
                            ]
                        },
                        {
                            u"widgetSlots":[
                                [
                                    u"grokTeaserWidget"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"citationsGroup",
                            u"widgetSlots":[
                                [
                                    u"citationRecsBookGridWidgetBuyInApp",
                                    u"citationRecsShovelerWidget"
                                ]
                            ]
                        }
                    ]
                },
                u"requiredWidgets":[
                    u"headerWidget"
                ]
            },
            {
                u"metricsTag":u"glf",
                u"class":u"groupedLayoutWithFooter",
                u"strings":{
                    u"seriesGroup":{
                        u"de":u"Infos zur Serie",
                        u"en":u"About the series",
                        u"en-US":u"About the series",
                        u"es":u"Acerca de la serie",
                        u"fr":u"\u00c0 propos de cette s\u00e9rie",
                        u"it":u"Informazioni sulle serie",
                        u"ja":u"\u3053\u306e\u30b7\u30ea\u30fc\u30ba\u306b\u3064\u3044\u3066",
                        u"nl":u"Over de reeks",
                        u"pt-BR":u"Informa\u00e7\u00f5es da s\u00e9rie",
                        u"ru":u"\u041e\u0431 \u044d\u0442\u043e\u0439 \u0441\u0435\u0440\u0438\u0438",
                        u"zh-CN":u"\u5173\u4e8e\u7cfb\u5217"
                    },
                    u"xrayGroup":{
                        u"de":u"X-Ray",
                        u"en-US":u"X-Ray",
                        u"ru":u"X-Ray",
                        u"pt-BR":u"X-Ray",
                        u"ja":u"X-Ray",
                        u"en":u"X-Ray",
                        u"it":u"X-Ray",
                        u"fr":u"X-Ray",
                        u"zh-CN":u"X-Ray",
                        u"es":u"X-Ray",
                        u"nl":u"X-Ray"
                    },
                    u"bookDescriptionEInkGroup":{
                        u"de":u"Im Shop anschauen",
                        u"en":u"See in store",
                        u"en-US":u"See in store",
                        u"es":u"Ver en tienda",
                        u"fr":u"Voir dans la boutique",
                        u"it":u"Visualizza nel Negozio",
                        u"ja":u"\u30b9\u30c8\u30a2\u3067\u898b\u308b",
                        u"nl":u"Weergeven in de winkel",
                        u"pt-BR":u"Ver na loja",
                        u"ru":u"\u041f\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u0442\u044c \u0432 \u043c\u0430\u0433\u0430\u0437\u0438\u043d\u0435",
                        u"zh-CN":u"\u5728\u5546\u5e97\u4e2d\u67e5\u770b"
                    },
                    u"authorsGroupWithSingleAuthor":{
                        u"de":u"\u00dcber den Autor",
                        u"en":u"About the author",
                        u"en-US":u"About the author",
                        u"es":u"Acerca del autor",
                        u"fr":u"\u00c0 propos de l'auteur",
                        u"it":u"Informazioni sull'autore",
                        u"ja":u"\u8457\u8005\u306b\u3064\u3044\u3066",
                        u"nl":u"Over de auteur",
                        u"pt-BR":u"Informa\u00e7\u00f5es do autor",
                        u"ru":u"\u041e\u0431 \u0430\u0432\u0442\u043e\u0440\u0435",
                        u"zh-CN":u"\u5173\u4e8e\u4f5c\u8005"
                    },
                    u"readingTimeGroup":{
                        u"de":u"Typische Lesezeit",
                        u"en":u"Typical time to read",
                        u"en-US":u"Typical time to read",
                        u"es":u"Tiempo de lectura t\u00edpico",
                        u"fr":u"Temps de lecture typique",
                        u"it":u"Tempo di lettura tipico",
                        u"ja":u"\u8aad\u307f\u7d42\u3048\u308b\u307e\u3067\u306e\u5e73\u5747\u7684\u306a\u6642\u9593",
                        u"nl":u"Gebruikelijke leestijd",
                        u"pt-BR":u"Tempo t\u00edpico para leitura",
                        u"ru":u"\u0421\u0440\u0435\u0434\u043d\u0435\u0435 \u0432\u0440\u0435\u043c\u044f \u0447\u0442\u0435\u043d\u0438\u044f",
                        u"zh-CN":u"\u5e38\u89c4\u9605\u8bfb\u65f6\u95f4"
                    },
                    u"citationsGroup":{
                        u"de":u"In diesem Buch erw\u00e4hnt",
                        u"en":u"Mentioned in this book",
                        u"en-US":u"Mentioned in this book",
                        u"es":u"Mencionado en este libro",
                        u"fr":u"Mentionn\u00e9s dans ce livre",
                        u"it":u"Menzionati in questo libro",
                        u"ja":u"\u3053\u306e\u4f5c\u54c1\u306b\u51fa\u3066\u304f\u308b\u672c",
                        u"nl":u"Genoemd in dit boek",
                        u"pt-BR":u"Mencionado neste eBook",
                        u"ru":u"\u0423\u043f\u043e\u043c\u0438\u043d\u0430\u0435\u0442\u0441\u044f \u0432 \u044d\u0442\u043e\u0439 \u043a\u043d\u0438\u0433\u0435",
                        u"zh-CN":u"\u672c\u4e66\u63d0\u53ca\u7684"
                    },
                    u"welcomeGroup":{
                        u"de":u"Willkommen!",
                        u"en":u"Welcome!",
                        u"en-US":u"Welcome!",
                        u"es":u"\u00a1Bienvenido!",
                        u"fr":u"Bienvenue\u00a0!",
                        u"it":u"Benvenuto!",
                        u"ja":u"\u3088\u3046\u3053\u305d!",
                        u"nl":u"Welkom",
                        u"pt-BR":u"Bem-vindo!",
                        u"ru":u"\u0414\u043e\u0431\u0440\u043e \u043f\u043e\u0436\u0430\u043b\u043e\u0432\u0430\u0442\u044c!",
                        u"zh-CN":u"\u6b22\u8fce\uff01"
                    },
                    u"audibleGroup":{
                        u"de":u"Auf Audible-Erz\u00e4hlung erweitern",
                        u"en":u"Upgrade to Audible Narration",
                        u"en-US":u"Upgrade to Audible Narration",
                        u"es":u"Actualizar a narraci\u00f3n Audible",
                        u"fr":u"Passer \u00e0 la narration Audible",
                        u"it":u"Passa alla narrazione Audible",
                        u"ja":u"Audible\u30ca\u30ec\u30fc\u30b7\u30e7\u30f3\u3078\u30a2\u30c3\u30d7\u30b0\u30ec\u30fc\u30c9",
                        u"nl":u"Upgraden naar Audible Narration",
                        u"pt-BR":u"Atualizar para narra\u00e7\u00e3o Audible",
                        u"ru":u"\u041f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f \u043a \u0437\u0430\u043a\u0430\u0434\u0440\u043e\u0432\u043e\u043c\u0443 \u0442\u0435\u043a\u0441\u0442\u0443 Audible",
                        u"zh-CN":u"\u5347\u7ea7\u5230\u3016Audible Narration\u3017"
                    }
                },
                u"widgetPlacements":{
                    u"footer":[
                        {
                            u"widgetSlots":[
                                [
                                    u"readerSettingsWidget"
                                ]
                            ]
                        }
                    ],
                    u"body":[
                        {
                            u"titleKey":u"welcomeGroup",
                            u"widgetSlots":[
                                [
                                    u"welcomeTextWidget"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"bookDescriptionEInkGroup",
                            u"widgetSlots":[
                                [
                                    u"bookDescriptionWidget"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"readingTimeGroup",
                            u"widgetSlots":[
                                [
                                    u"timeToReadWidget"
                                ]
                            ]
                        },
                        {
                            u"widgetSlots":[
                                [
                                    u"markAsReadingWidget"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"audibleGroup",
                            u"widgetSlots":[
                                [
                                    u"audibleNarration"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"seriesGroup",
                            u"widgetSlots":[
                                [
                                    u"positionInSeriesWidgetWithText"
                                ],
                                [
                                    u"previousBookInTheSeriesWidget"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"authorsGroupWithSingleAuthor",
                            u"widgetSlots":[
                                [
                                    u"aboutTheAuthorWidget"
                                ],
                                [
                                    u"authorNamesListWidget"
                                ],
                                [
                                    u"authorRecsBookGridWidgetWithTitleSingleAuthorBuyInApp",
                                    u"authorRecsShovelerWidgetWithTitleNoPlaceholderSingleAuthor"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"xrayGroup",
                            u"widgetSlots":[
                                [
                                    u"xray"
                                ]
                            ]
                        },
                        {
                            u"widgetSlots":[
                                [
                                    u"grokTeaserWidget"
                                ]
                            ]
                        },
                        {
                            u"titleKey":u"citationsGroup",
                            u"widgetSlots":[
                                [
                                    u"citationRecsBookGridWidgetBuyInApp",
                                    u"citationRecsShovelerWidget"
                                ]
                            ]
                        }
                    ]
                }
            }
        ],
        u"data":{
            u"welcomeText":{
                u"class":u"dynamicText",
                u"localizedText":{
                    u"de":u"\u201e\u00dcber dieses Buch\u201c zeigt Ihnen zus\u00e4tzliche Informationen \u00fcber Ihr Buch, wenn Sie es das erste mal \u00f6ffnen. Sie k\u00f6nnen es jederzeit im linken Men\u00fc \u00f6ffnen.",
                    u"en":u"About This Book shows you additional information about your book the first time you open it. You can access it at any time from the menu.",
                    u"en-US":u"About This Book shows you additional information about your book the first time you open it. You can access it at any time from the menu.",
                    u"es":u"Acerca del libro te muestra informaci\u00f3n adicional sobre un libro la primera vez que lo abres. Puedes acceder a esta funci\u00f3n en cualquier momento desde el men\u00fa.",
                    u"fr":u"\u00c0 propos du livre pr\u00e9sente des informations additionnelles sur un livre quand vous l'ouvrez pour la premi\u00e8re fois. Vous pouvez y acc\u00e9der \u00e0 tout moment depuis le menu.",
                    u"it":u"Informazioni sul libro presenta informazioni aggiuntive sul libro la prima volta che lo apri. Puoi accedervi in qualsiasi momento dal menu.",
                    u"ja":u"\u672c\u3092\u521d\u3081\u3066\u958b\u304f\u3068\u3001\u672c\u306e\u8a73\u7d30\u60c5\u5831\u3092\u8868\u793a\u3059\u308b\u300c\u3053\u306e\u672c\u306b\u3064\u3044\u3066\u300d\u30c0\u30a4\u30a2\u30ed\u30b0\u30dc\u30c3\u30af\u30b9\u304c\u958b\u304d\u307e\u3059\u3002\u3053\u306e\u30c0\u30a4\u30a2\u30ed\u30b0\u306f\u30e1\u30cb\u30e5\u30fc\u304b\u3089\u3044\u3064\u3067\u3082\u958b\u304f\u3053\u3068\u304c\u3067\u304d\u307e\u3059\u3002",
                    u"nl":u"In Over dit boek wordt aanvullende informatie weergegeven over uw boek bij de eerste keer dat u dit opent. U kunt dit op elk gewenst moment bekijken in het menu.",
                    u"pt-BR":u"O recurso Informa\u00e7\u00f5es do eBook mostra-lhe informa\u00e7\u00f5es adicionais do eBook na primeira vez que abri-lo. \u00c9 poss\u00edvel acess\u00e1-lo a qualquer momento no menu.",
                    u"ru":u"\u0421 \u043f\u043e\u043c\u043e\u0449\u044c\u044e \u0444\u0443\u043d\u043a\u0446\u0438\u0438 \u00ab\u041e \u043a\u043d\u0438\u0433\u0435\u00bb \u0432\u044b \u0432\u0438\u0434\u0438\u0442\u0435 \u0434\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u0443\u044e \u0438\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0438\u044e \u043e \u043a\u043d\u0438\u0433\u0435, \u043a\u043e\u0433\u0434\u0430 \u043e\u0442\u043a\u0440\u044b\u0432\u0430\u0435\u0442\u0435 \u043a\u043d\u0438\u0433\u0443 \u0432\u043f\u0435\u0440\u0432\u044b\u0435. \u041a\u043e\u0441\u043d\u0438\u0442\u0435\u0441\u044c \u043a\u043d\u043e\u043f\u043a\u0438 \u00ab\u041c\u0435\u043d\u044e\u00bb, \u0447\u0442\u043e\u0431\u044b \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u0444\u0443\u043d\u043a\u0446\u0438\u044e \u0432 \u043b\u044e\u0431\u043e\u0435 \u0432\u0440\u0435\u043c\u044f.",
                    u"zh-CN":u"\u3010\u5173\u4e8e\u672c\u4e66\u3011\u4f1a\u5728\u60a8\u7b2c\u4e00\u6b21\u6253\u5f00\u672c\u4e66\u65f6\u4e3a\u60a8\u663e\u793a\u76f8\u5173\u4fe1\u606f\u3002\u60a8\u53ef\u4ee5\u968f\u65f6\u901a\u8fc7\u83dc\u5355\u8fdb\u884c\u8bbf\u95ee\u3002"
                },
                u"localizedSubtext":{
                    u"de":u"Sie k\u00f6nnen Anpassungen vornehmen, wenn \u201eInfos zum Buch\u201c erscheint, indem Sie auf den den Link f\u00fcr Einstellungen tippen.",
                    u"en":u"You can adjust when About This Book appears by tapping the Settings link below.",
                    u"en-US":u"You can adjust when About This Book appears by tapping the Settings link below.",
                    u"es":u"Puedes ajustar cuando se muestra Acerca del libro pulsando en el enlace a Configuraci\u00f3n que hay a continuaci\u00f3n.",
                    u"fr":u"Vous pouvez choisir d'activer ou non l'option \u00c0 propos du livre en touchant le lien Param\u00e8tres ci-dessous.",
                    u"it":u"Puoi regolare la visualizzazione di Informazioni sul libro toccando il link Impostazioni qui sotto.",
                    u"ja":u"\u300c\u3053\u306e\u672c\u306b\u3064\u3044\u3066\u300d\u306e\u8868\u793a\u306f\u3001\u4e0b\u306e\u300c\u8a2d\u5b9a\u300d\u30ea\u30f3\u30af\u3092\u30bf\u30c3\u30d7\u3057\u3066\u5909\u66f4\u3067\u304d\u307e\u3059\u3002",
                    u"nl":u"U kunt aanpassen wanneer Over dit boek wordt weergegeven door hieronder op de link Instellingen te tikken.",
                    u"pt-BR":u"\u00c9 poss\u00edvel ajustar quando o recurso Informa\u00e7\u00f5es do eBook aparece ao tocar em Configura\u00e7\u00f5es no link abaixo.",
                    u"ru":u"\u041a\u043e\u0441\u043d\u0438\u0442\u0435\u0441\u044c \u0441\u0441\u044b\u043b\u043a\u0438 \u00ab\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438\u00bb, \u0447\u0442\u043e\u0431\u044b \u043d\u0430\u0441\u0442\u0440\u043e\u0438\u0442\u044c \u0444\u0443\u043d\u043a\u0446\u0438\u044e \u00ab\u041e \u043a\u043d\u0438\u0433\u0435\u00bb.",
                    u"zh-CN":u"\u60a8\u53ef\u4ee5\u70b9\u51fb\u4e0b\u65b9\u7684\u3010\u8bbe\u7f6e\u3011\u94fe\u63a5\u8c03\u6574\u3010\u5173\u4e8e\u672c\u4e66\u3011\u7684\u663e\u793a\u9891\u7387\u3002"
                }
            },
            u"grokShelfInfo":{
                u"class":u"goodReadsShelfInfo",
                u"shelves":[
                    u"to-read"
                ]
            },
            u"authorBios":{
                u"class":u"authorBioList",
                u"authors":[]
            },
            u"readingTime":{
                u"class":u"time",
                u"formattedTime":{
                    u"de":u"{0} Stunden und {1} Minuten",
                    u"en-US":u"{0} hours and {1} minutes",
                    u"ru":u"{0}\u00a0\u0447 \u0432 {1}\u00a0\u043c\u0432\u043d",
                    u"pt-BR":u"{0} horas e {1} minutos",
                    u"ja":u"{0}\u6642\u9593{1}\u5206",
                    u"en":u"{0} hours and {1} minutes",
                    u"it":u"{0} ore e {1} minuti",
                    u"fr":u"{0} heures et {1} minutes",
                    u"zh-CN":u"{0} \u5c0f\u65f6 {1} \u5206\u949f",
                    u"es":u"{0} horas y {1} minutos",
                    u"nl":u"{0} uur en {1} minuten"
                }
            },
            u"readingPages":{
                u"class":u"pages"
            }
        }
    }
