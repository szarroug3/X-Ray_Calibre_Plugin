# goodreads_parser.py

import re
import json
import base64
import datetime
from lxml import html
from urllib2 import urlopen

class GoodreadsPageDoesNotExist(Exception):
    pass

# Parses Goodreads page for characters, terms, and quotes
class GoodreadsParser(object):
    BOOK_ID_PAT = re.compile(r'\/show\/([\d]+)')
    ASIN_PAT = re.compile(r'"asin":"(.+?)"')
    def __init__(self, url, connection, asin, raise_error_on_page_not_found=False, create_author_profile=False, create_end_actions=False):
        self._url = url
        self._connection = connection
        self._asin = asin
        self._create_author_profile = create_author_profile
        self._create_end_actions = create_end_actions
        self._characters = {}
        self._settings = {}
        self._quotes = []
        self._author_profile = None
        self._end_actions = None
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
    def end_actions(self):
        return self._end_actions
    
    @property
    def quotes(self):
        return self._quotes

    def parse(self):
        if self._page_source is None:
            return

        self.get_characters()
        self.get_settings()
        self.get_quotes()

        if self._create_author_profile:
            try:
                self.get_author_profile()
            except:
                pass

        if self._create_end_actions:
            try:
                self.get_end_actions()
            except:
                return

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

    def get_end_actions(self):
        if self._page_source is None:
            return

        # this is usually run if we're creating an author profile
        # if it's not, we need to run it to get the author's other books
        if not self._create_author_profile:
            self.get_author_other_books()

        self.get_book_image_url()
        self.get_book_rating()
        self.get_customer_recommendations()
        self.compile_end_actions()

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

        self._author_bio = ' '.join(author_bio.text_content().split()).encode('latin-1')

    def get_author_image(self):
        if self._author_page is None:
            return

        self._author_image_url = self._author_page.xpath('//a[contains(@href, "/photo/author/")]/img')[0].get('src')
        image = urlopen(self._author_image_url).read()
        self._author_image = base64.b64encode(image)

    def get_author_other_books(self):
        if self._author_page is None:
            return

        book_info = []
        current_book_asin = self.open_url('/buttons/glide/' + self._goodreads_book_id)

        for book in self._author_page.xpath('//tr[@itemtype="http://schema.org/Book"]'):
            book_id = book.find('td//div[@class="u-anchorTarget"]').get('id')

            # don't want to add the current book to the other books list
            if book_id == self._goodreads_book_id:
                continue

            image_url = book.find('td//img[@class="bookSmallImg"]').get('src').split('/')
            image_url = '{0}/{1}l/{2}'.format('/'.join(image_url[:-2]), image_url[-2][:-1], image_url[-1])

            book_info.append((book_id, image_url))

        self._author_recommendations = self.get_book_info_from_tooltips(book_info)
        self._author_other_books = [{'e': 1, 't': info['title'], 'a': info['asin']} for info in self._author_recommendations]

    def get_customer_recommendations(self):
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

        self._cust_recommendations = self.get_book_info_from_tooltips(book_info)


    def get_book_info_from_tooltips(self, book_info):
        book_data = []
        link_pattern = 'resources[Book.{0}][type]=Book&resources[Book.{0}][id]={0}'
        tooltips_page_url = '/tooltips?' + "&".join([link_pattern.format(book_id) for book_id, image_url in book_info])
        tooltips_page_info = json.loads(self.open_url(tooltips_page_url))['tooltips']

        for index, (book_id, image_url) in enumerate(book_info):
            book_info = html.fromstring(tooltips_page_info['Book.{0}'.format(book_id)])

            title = book_info.xpath('//a[contains(@class, "readable")]')[0].text
            authors = [book_info.xpath('//a[contains(@class, "authorName")]')[0].text]
            rating_string = book_info.xpath('//div[@class="bookRatingAndPublishing"]/span[@class="minirating"]')[0].text_content().strip().replace(',', '').split()
            rating = float(rating_string[rating_string.index('avg')-1])
            num_of_reviews = int(rating_string[-2])

            asin_data_page = self.open_url('/buttons/glide/' + book_id)
            book_asin = self.ASIN_PAT.search(asin_data_page)
            if not book_asin:
                continue
            book_asin = book_asin.group(1)

            if len(book_info.xpath('//div[@class="addBookTipDescription"]//span[not(contains(@id, "freeTextContainer"))]')) > 0:
                desc = book_info.xpath('//div[@class="addBookTipDescription"]//span[not(contains(@id, "freeTextContainer"))]')[0].text.strip()
            else:
                desc = book_info.xpath('//div[@class="addBookTipDescription"]//span[contains(@id, "freeTextContainer")]')[0].text.strip()

            book_data.append({'class': "featuredRecommendation",
                                'asin': book_asin,
                                'title': title,
                                'authors': authors,
                                'imageUrl': image_url,
                                'description': desc,
                                'hasSample': False,
                                'amazonRating': rating,
                                'numberOfReviews': num_of_reviews})

        return book_data

    def get_book_image_url(self):
        self._book_image_url = self._page_source.xpath('//div[@class="mainContent"]//div[@id="imagecol"]//img[@id="coverImage"]')[0].get('src')

    def get_book_rating(self):
        self._book_rating = float(self._page_source.xpath('//div[@class="mainContent"]//div[@id="metacol"]//span[@class="value rating"]/span')[0].text)

    def compile_author_profile(self):
        self._author_profile = {"u": [{"y": 277,
                            "l": [x["a"] for x in self._author_other_books],
                            "n": self._author_name,
                            "b": self._author_bio,
                            "i": self._author_image}],
                    "d": int((datetime.datetime.now() - datetime.datetime(1970,1,1)).total_seconds()),
                    "o": self._author_other_books,
                    "a": self._asin
                }

    def compile_end_actions(self):
        timestamp = int((datetime.datetime.now() - datetime.datetime(1970,1,1)).total_seconds())
        self._end_actions = self.BASE_END_ACTIONS

        self._end_actions['bookInfo']['asin'] = self._asin
        self._end_actions['bookInfo']['timestamp'] = timestamp
        self._end_actions['bookInfo']['imageUrl'] = self._book_image_url

        self._end_actions['data']['authorBios']['authors'].append({"class": "authorBio", "name": self._author_name, "bio": self._author_bio, "imageUrl": self._author_image_url})

        if self._author_recommendations is not None:
            self._end_actions['data']['authorRecs'] = {'class': 'featuredRecommendationList',
                                                        'recommendations': self._author_recommendations}
        if self._cust_recommendations is not None:
            self._end_actions['data']['customersWhoBoughtRecs'] = {'class': 'featuredRecommendationList',
                                                        'recommendations': self._cust_recommendations}




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