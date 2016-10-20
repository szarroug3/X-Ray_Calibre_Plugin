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
    def __init__(self, url, connection, asin, raise_error_on_page_not_found=False, create_author_profile=False):
        self._url = url
        self._connection = connection
        self._asin = asin
        self._create_author_profile = create_author_profile
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

        if not self._create_author_profile:
            return

        try:
            self.get_author_profile()
        except:
            pass

        # try:
        #     self.get_end_actions()
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

    def get_end_actions(self):
        if self._page_source is None:
            return

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

        self._author_other_books = []
        book_ids = []
        current_book_asin = self.open_url('/buttons/glide/' + self._goodreads_book_id)
        for book in self._author_page.xpath('//tr[@itemtype="http://schema.org/Book"]/td/a[@class="bookTitle"]'):
            
            book_data = {'e': 1, 't': book.find('span').text}
            book_url = book.get('href')

            book_id_search = self.BOOK_ID_PAT.search(book_url)
            if not book_id_search:
                continue
            book_ids.append(book_id_search.group(1))

        link_pattern = 'resources[Book.{0}][type]=Book&resources[Book.{0}][id]={0}'
        tooltips_page_url = '/tooltips?' + "&".join([link_pattern.format(x) for x in book_ids])
        tooltips_page_info = json.loads(self.open_url(tooltips_page_url))['tooltips']

        for book_id in book_ids:
            asin_data_page = self.open_url('/buttons/glide/' + book_id)
            book_asin = self.ASIN_PAT.search(asin_data_page)
            if not book_asin:
                continue
            book_asin = book_asin.group(1)

            # we dont' want to add the current book as an "other book"
            if book_asin != current_book_asin:
                book_data['a'] = book_asin
                book_info = html.fromstring(tooltips_page_info['Book.{0}'.format(book_id)])
                book_data['desc'] = book_info.xpath('//div[@class="addBookTipDescription"]//span[not(contains(@id, "freeTextContainer"))]')[0].text.strip()
                self._author_other_books.append(book_data)

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
        self._end_actions = BASE_END_ACTIONS

        self._end_actions['bookInfo']['asin'] = self._asin
        self._end_actions['bookInfo']['timestamp'] = timestamp
        self._end_actions['bookInfo']['imageUrl'] = self._book_image_url
        
        self._end_actions['data']['authorBios']['authors'].append({"class": "authorBio", "name": self._author_name, "bio": self._author_bio, "imageUrl": self._author_image_url})




    BASE_END_ACTIONS = {
        "bookInfo": {
            "class": "bookInfo",
            "contentType": "EBOK",
            "refTagSuffix": "AAAgAAB",
        },
        "widgets": [{
            "id": "ratingAndReviewWidget",
            "class": "rateAndReview",
            "metricsTag": "rr",
            "options": {
                "refTagPartial": "rr",
                "showShareComponent": False
            }
        }, {
            "id": "sharingWidget",
            "class": "sharing",
            "metricsTag": "sh"
        }, {
            "id": "ratingAndSharingWidget",
            "metricsTag": "rsh",
            "options": {
                "refTagPartial": "rsw"
            },
            "class": "ratingAndSharing"
        }, {
            "id": "authorRecsListWidgetWithTitle",
            "metricsTag": "rat",
            "options": {
                "dataKey": "authorRecs",
                "refTagPartial": "r_a"
            },
            "class": "list",
            "strings": {
                "title": {
                    "de": "Mehr von %{authorList}",
                    "en": "More by %{authorList}",
                    "en-US": "More by %{authorList}",
                    "es": "M\u00E1s de %{authorList}",
                    "fr": "Autres livres de %{authorList}",
                    "it": "Altri di %{authorList}",
                    "ja": "%{authorList}\u306E\u305D\u306E\u4ED6\u306E\u672C",
                    "nl": "Meer van %{authorList}",
                    "pt-BR": "Mais por %{authorList}",
                    "ru": "\u0411\u043E\u043B\u044C\u0448\u0435 \u043F\u0440\u043E\u0438\u0437\u0432\u0435\u0434\u0435\u043D\u0438\u0439, \u043D\u0430\u043F\u0438\u0441\u0430\u043D\u043D\u044B\u0445 %{authorList}",
                    "zh-CN": "\u66F4\u591A%{authorList}\u4F5C\u54C1"
                }
            }
        }, {
            "id": "authorRecsShovelerWidgetWithTitlePlaceholders",
            "metricsTag": "ratn",
            "options": {
                "dataKey": "authorRecs",
                "refTagPartial": "r_a"
            },
            "class": "shoveler",
            "strings": {
                "title": {
                    "de": "Mehr von %{authorList}",
                    "en": "More by %{authorList}",
                    "en-US": "More by %{authorList}",
                    "es": "M\u00E1s de %{authorList}",
                    "fr": "Autres livres de %{authorList}",
                    "it": "Altri di %{authorList}",
                    "ja": "%{authorList}\u306E\u305D\u306E\u4ED6\u306E\u672C",
                    "nl": "Meer van %{authorList}",
                    "pt-BR": "Mais por %{authorList}",
                    "ru": "\u0411\u043E\u043B\u044C\u0448\u0435 \u043F\u0440\u043E\u0438\u0437\u0432\u0435\u0434\u0435\u043D\u0438\u0439, \u043D\u0430\u043F\u0438\u0441\u0430\u043D\u043D\u044B\u0445 %{authorList}",
                    "zh-CN": "\u66F4\u591A%{authorList}\u4F5C\u54C1"
                }
            }
        }, {
            "id": "customerRecsListWidgetWithTitle",
            "metricsTag": "rpt",
            "options": {
                "dataKey": "customersWhoBoughtRecs",
                "refTagPartial": "r_p"
            },
            "class": "list",
            "strings": {
                "title": {
                    "de": "Kunden, die dieses Buch gekauft haben, kauften auch",
                    "en": "Customers who bought this book also bought",
                    "en-US": "Customers who bought this book also bought",
                    "es": "Los clientes que compraron este libro tambi\u00E9n compraron",
                    "fr": "Les clients ayant achet\u00E9 ce livre ont \u00E9galement achet\u00E9",
                    "it": "I clienti che hanno acquistato questo libro hanno acquistato anche",
                    "ja": "\u3053\u306E\u672C\u3092\u8CB7\u3063\u305F\u4EBA\u306F\u3053\u3093\u306A\u5546\u54C1\u3082\u8CB7\u3063\u3066\u3044\u307E\u3059",
                    "nl": "Klanten die dit boek kochten, kochten ook",
                    "pt-BR": "Clientes que compraram este eBook tamb\u00E9m compraram",
                    "ru": "\u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0438, \u043A\u0443\u043F\u0438\u0432\u0448\u0438\u0435 \u044D\u0442\u0443 \u043A\u043D\u0438\u0433\u0443, \u0442\u0430\u043A\u0436\u0435 \u043A\u0443\u043F\u0438\u043B\u0438",
                    "zh-CN": "\u8D2D\u4E70\u672C\u4E66\u7684\u987E\u5BA2\u8FD8\u4E70\u8FC7"
                }
            }
        }, {
            "id": "customerRecsShovelerWidgetWithTitle",
            "metricsTag": "rpt",
            "options": {
                "dataKey": "customersWhoBoughtRecs",
                "refTagPartial": "r_p"
            },
            "class": "shoveler",
            "strings": {
                "title": {
                    "de": "Kunden, die dieses Buch gekauft haben, kauften auch",
                    "en": "Customers who bought this book also bought",
                    "en-US": "Customers who bought this book also bought",
                    "es": "Los clientes que compraron este libro tambi\u00E9n compraron",
                    "fr": "Les clients ayant achet\u00E9 ce livre ont \u00E9galement achet\u00E9",
                    "it": "I clienti che hanno acquistato questo libro hanno acquistato anche",
                    "ja": "\u3053\u306E\u672C\u3092\u8CB7\u3063\u305F\u4EBA\u306F\u3053\u3093\u306A\u5546\u54C1\u3082\u8CB7\u3063\u3066\u3044\u307E\u3059",
                    "nl": "Klanten die dit boek kochten, kochten ook",
                    "pt-BR": "Clientes que compraram este eBook tamb\u00E9m compraram",
                    "ru": "\u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0438, \u043A\u0443\u043F\u0438\u0432\u0448\u0438\u0435 \u044D\u0442\u0443 \u043A\u043D\u0438\u0433\u0443, \u0442\u0430\u043A\u0436\u0435 \u043A\u0443\u043F\u0438\u043B\u0438",
                    "zh-CN": "\u8D2D\u4E70\u672C\u4E66\u7684\u987E\u5BA2\u8FD8\u4E70\u8FC7"
                }
            }
        }, {
            "id": "citationRecsListWidgetWithTitle",
            "metricsTag": "rct",
            "options": {
                "dataKey": "citationRecs",
                "refTagPartial": "r_c"
            },
            "class": "list",
            "strings": {
                "title": {
                    "de": "In diesem Buch erw\u00E4hnt",
                    "en": "Mentioned in this book",
                    "en-US": "Mentioned in this book",
                    "es": "Mencionado en este libro",
                    "fr": "Mentionn\u00E9s dans ce livre",
                    "it": "Menzionati in questo libro",
                    "ja": "\u3053\u306E\u4F5C\u54C1\u306B\u51FA\u3066\u304F\u308B\u672C",
                    "nl": "Genoemd in dit boek",
                    "pt-BR": "Mencionado neste eBook",
                    "ru": "\u0423\u043F\u043E\u043C\u0438\u043D\u0430\u0435\u0442\u0441\u044F \u0432 \u044D\u0442\u043E\u0439 \u043A\u043D\u0438\u0433\u0435",
                    "zh-CN": "\u672C\u4E66\u63D0\u53CA\u7684"
                }
            }
        }, {
            "id": "citationRecsShovelerWidgetWithTitle",
            "metricsTag": "rct",
            "options": {
                "dataKey": "citationRecs",
                "refTagPartial": "r_c"
            },
            "class": "shoveler",
            "strings": {
                "title": {
                    "de": "In diesem Buch erw\u00E4hnt",
                    "en": "Mentioned in this book",
                    "en-US": "Mentioned in this book",
                    "es": "Mencionado en este libro",
                    "fr": "Mentionn\u00E9s dans ce livre",
                    "it": "Menzionati in questo libro",
                    "ja": "\u3053\u306E\u4F5C\u54C1\u306B\u51FA\u3066\u304F\u308B\u672C",
                    "nl": "Genoemd in dit boek",
                    "pt-BR": "Mencionado neste eBook",
                    "ru": "\u0423\u043F\u043E\u043C\u0438\u043D\u0430\u0435\u0442\u0441\u044F \u0432 \u044D\u0442\u043E\u0439 \u043A\u043D\u0438\u0433\u0435",
                    "zh-CN": "\u672C\u4E66\u63D0\u53CA\u7684"
                }
            }
        }, {
            "id": "aboutTheAuthorWidgetWithTitle",
            "metricsTag": "atat",
            "options": {
                "dataKey": "authorBios",
                "refTagPartial": "r_ata",
                "subscriptionInfoDataKey": "authorSubscriptions",
                "followInfoDataKey": "followSubscriptions"
            },
            "class": "authors",
            "strings": {
                "title": {
                    "de": "\u00DCber den Autor",
                    "en": "About the author",
                    "en-US": "About the author",
                    "es": "Acerca del autor",
                    "fr": "\u00C0 propos de l'auteur",
                    "it": "Informazioni sull'autore",
                    "ja": "\u8457\u8005\u306B\u3064\u3044\u3066",
                    "nl": "Over de auteur",
                    "pt-BR": "Informa\u00E7\u00F5es do autor",
                    "ru": "\u041E\u0431 \u0430\u0432\u0442\u043E\u0440\u0435",
                    "zh-CN": "\u5173\u4E8E\u4F5C\u8005"
                }
            }
        }, {
            "id": "grokRatingAndReviewWidget",
            "class": "grokRateAndReview",
            "metricsTag": "grr",
            "options": {
                "refTagPartial": "grr",
                "showShareComponent": False
            }
        }, {
            "id": "grokRatingWidget",
            "class": "grokRate",
            "metricsTag": "gr",
            "options": {
                "refTagPartial": "gr",
                "showShareComponent": False
            }
        }, {
            "id": "askAReaderWidget",
            "metricsTag": "aar",
            "options": {
                "dataKey": "askAReaderQuestion"
            },
            "class": "askAReader",
            "strings": {
                "title": {
                    "de": "Leser-Fragen und -Antworten",
                    "en": "Reader Q&A",
                    "en-US": "Reader Q&A",
                    "es": "Preguntas frecuentes del lector",
                    "fr": "Questions-r\u00E9ponses",
                    "it": "Q&A Lettore",
                    "ja": "\u8AAD\u8005\u306B\u3088\u308B\u8CEA\u554F\u3068\u56DE\u7B54",
                    "nl": "Lezersvragen",
                    "pt-BR": "Perguntas e respostas do leitor",
                    "ru": "\u0412\u043E\u043F\u0440\u043E\u0441\u044B \u0438 \u043E\u0442\u0432\u0435\u0442\u044B \u0447\u0438\u0442\u0430\u0442\u0435\u043B\u0435\u0439",
                    "zh-CN": "\u8BFB\u8005\u95EE\u7B54"
                }
            }
        }, {
            "id": "ratingWidget",
            "class": "ratingBar",
            "metricsTag": "ro",
            "options": {
                "refTagPartial": "ro",
                "showShareComponent": False
            }
        }, {
            "id": "followTheAuthorWidgetWithTitle",
            "metricsTag": "ftat",
            "options": {
                "dataKey": "authorSubscriptions",
                "refTagPartial": "r_fta",
                "followInfoDataKey": "followSubscriptions"
            },
            "class": "followTheAuthor",
            "strings": {
                "title": {
                    "de": "Bleiben Sie auf dem neuesten Stand",
                    "en": "Stay up to date",
                    "en-US": "Stay up to date",
                    "es": "Mantente actualizado",
                    "fr": "Rester \u00E0 jour",
                    "it": "Rimani aggiornato",
                    "ja": "\u6700\u65B0\u60C5\u5831\u3092\u30D5\u30A9\u30ED\u30FC",
                    "nl": "Blijf op de hoogte",
                    "pt-BR": "Mantenha-se atualizado",
                    "ru": "\u0411\u0443\u0434\u044C\u0442\u0435 \u0432 \u043A\u0443\u0440\u0441\u0435 \u043F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0445 \u0441\u043E\u0431\u044B\u0442\u0438\u0439!",
                    "zh-CN": "\u4FDD\u6301\u66F4\u65B0"
                }
            }
        }, {
            "id": "shareWithFriendWidget",
            "metricsTag": "swf",
            "options": {
                "refTagPartial": "swf"
            },
            "class": "shareWithFriend",
            "strings": {
                "buttonText": {
                    "de": "Empfehlen",
                    "en": "Recommend",
                    "en-US": "Recommend",
                    "es": "Recomendar",
                    "fr": "Recommander",
                    "it": "Consiglia",
                    "ja": "\u7D39\u4ECB",
                    "nl": "Aanraden",
                    "pt-BR": "Recomendar",
                    "ru": "\u041F\u043E\u0440\u0435\u043A\u043E\u043C\u0435\u043D\u0434\u043E\u0432\u0430\u0442\u044C",
                    "zh-CN": "\u63A8\u8350"
                },
                "bodyText": {
                    "de": "Empfehlen Sie es einem/r Freund/in.",
                    "en": "Recommend it to a friend.",
                    "en-US": "Recommend it to a friend.",
                    "es": "Recomi\u00E9ndaselo a un amigo.",
                    "fr": "Recommandez-le \u00E0 un ami.",
                    "it": "Consiglialo a un amico.",
                    "ja": "\u53CB\u9054\u306B\u3082\u7D39\u4ECB\u3057\u307E\u3057\u3087\u3046\u3002",
                    "nl": "Raad het een vriend aan.",
                    "pt-BR": "Recomende-o a um amigo.",
                    "ru": "\u041F\u043E\u0440\u0435\u043A\u043E\u043C\u0435\u043D\u0434\u0443\u0439\u0442\u0435 \u0435\u0435 \u0434\u0440\u0443\u0433\u0443.",
                    "zh-CN": "\u5411\u597D\u53CB\u63A8\u8350\u5427\u3002"
                },
                "title": {
                    "de": "Gefiel Ihnen dieses Buch?",
                    "en": "Enjoyed this book?",
                    "en-US": "Enjoyed this book?",
                    "es": "\u00BFTe ha gustado este libro?",
                    "fr": "Vous avez aim\u00E9 ce livre\u00A0?",
                    "it": "Ti \u00E8 piaciuto questo libro?",
                    "ja": "\u3053\u306E\u672C\u3092\u304A\u697D\u3057\u307F\u3044\u305F\u3060\u3051\u307E\u3057\u305F\u304B?",
                    "nl": "Vond u dit boek leuk?",
                    "pt-BR": "Gostou deste eBook?",
                    "ru": "\u041F\u043E\u043D\u0440\u0430\u0432\u0438\u043B\u0430\u0441\u044C \u044D\u0442\u0430 \u043A\u043D\u0438\u0433\u0430?",
                    "zh-CN": "\u559C\u6B22\u672C\u4E66\uFF1F"
                }
            }
        }, {
            "id": "buyThisBookWidget",
            "metricsTag": "bn",
            "options": {
                "buyInStore": False,
                "buyButtonVisible": True,
                "dataIsCurrentBook": True,
                "refTagPartial": "bn",
                "oneClickBorrowSupported": False,
                "showWishListButton": False
            },
            "class": "singleRec"
        }, {
            "id": "nextInSeriesWidget",
            "metricsTag": "nist",
            "options": {
                "dataKey": "nextBook",
                "buyInStore": False,
                "buyButtonVisible": True,
                "dataIsCurrentBook": False,
                "refTagPartial": "r_nis",
                "oneClickBorrowSupported": False,
                "showWishListButton": False
            },
            "class": "singleRec",
            "strings": {
                "title": {
                    "de": "N\u00E4chster Teil der Serie",
                    "en": "Next in Series",
                    "en-US": "Next in series",
                    "es": "Siguiente de la serie",
                    "fr": "Prochain tome",
                    "it": "Prossimo della serie",
                    "ja": "\u30B7\u30EA\u30FC\u30BA\u306E\u6B21\u5DFB",
                    "nl": "Volgende in de reeks",
                    "pt-BR": "Pr\u00F3ximo da s\u00E9rie",
                    "ru": "\u0421\u043B\u0435\u0434\u0443\u044E\u0449\u0430\u044F \u043A\u043D\u0438\u0433\u0430 \u0441\u0435\u0440\u0438\u0438",
                    "zh-CN": "\u4E1B\u4E66\u4E0B\u4E00\u90E8"
                }
            }
        }, {
            "id": "recommendedForYouWidget",
            "metricsTag": "rfy",
            "options": {
                "dataKey": "specialRec",
                "buyInStore": False,
                "buyButtonVisible": True,
                "dataIsCurrentBook": False,
                "refTagPartial": "rfy",
                "oneClickBorrowSupported": False,
                "showWishListButton": False
            },
            "class": "singleRec",
            "strings": {
                "title": {
                    "de": "Empfehlungen f\u00FCr Sie",
                    "en": "Recommended for you",
                    "en-US": "Recommended for you",
                    "es": "Recomendaciones",
                    "fr": "Recommand\u00E9 pour vous",
                    "it": "Consigliati per te",
                    "ja": "\u304A\u3059\u3059\u3081",
                    "nl": "Aanbevolen voor u",
                    "pt-BR": "Recomendados para voc\u00EA",
                    "ru": "\u0420\u0435\u043A\u043E\u043C\u0435\u043D\u0434\u0430\u0446\u0438\u0438 \u0434\u043B\u044F \u0432\u0430\u0441",
                    "zh-CN": "\u4E3A\u60A8\u63A8\u8350"
                }
            }
        }, {
            "id": "authorRecsBookGridWidgetWithTitle",
            "metricsTag": "rat",
            "options": {
                "dataKey": "authorRecs",
                "buyInStore": False,
                "buyButtonVisible": True,
                "showBadges": True,
                "refTagPartial": "r_a",
                "oneClickBorrowSupported": False,
                "showWishListButton": False
            },
            "class": "bookGrid",
            "strings": {
                "title": {
                    "de": "Mehr von %{authorList}",
                    "en": "More by %{authorList}",
                    "en-US": "More by %{authorList}",
                    "es": "M\u00E1s de %{authorList}",
                    "fr": "Autres livres de %{authorList}",
                    "it": "Altri di %{authorList}",
                    "ja": "%{authorList}\u306E\u305D\u306E\u4ED6\u306E\u672C",
                    "nl": "Meer van %{authorList}",
                    "pt-BR": "Mais por %{authorList}",
                    "ru": "\u0411\u043E\u043B\u044C\u0448\u0435 \u043F\u0440\u043E\u0438\u0437\u0432\u0435\u0434\u0435\u043D\u0438\u0439, \u043D\u0430\u043F\u0438\u0441\u0430\u043D\u043D\u044B\u0445 %{authorList}",
                    "zh-CN": "\u66F4\u591A%{authorList}\u4F5C\u54C1"
                }
            }
        }, {
            "id": "customerRecsBookGridWidgetWithTitle",
            "metricsTag": "rpt",
            "options": {
                "dataKey": "customersWhoBoughtRecs",
                "buyInStore": False,
                "buyButtonVisible": True,
                "showBadges": True,
                "refTagPartial": "r_p",
                "oneClickBorrowSupported": False,
                "showWishListButton": False
            },
            "class": "bookGrid",
            "strings": {
                "title": {
                    "de": "Kunden, die dieses Buch gekauft haben, kauften auch",
                    "en": "Customers who bought this book also bought",
                    "en-US": "Customers who bought this book also bought",
                    "es": "Los clientes que compraron este libro tambi\u00E9n compraron",
                    "fr": "Les clients ayant achet\u00E9 ce livre ont \u00E9galement achet\u00E9",
                    "it": "I clienti che hanno acquistato questo libro hanno acquistato anche",
                    "ja": "\u3053\u306E\u672C\u3092\u8CB7\u3063\u305F\u4EBA\u306F\u3053\u3093\u306A\u5546\u54C1\u3082\u8CB7\u3063\u3066\u3044\u307E\u3059",
                    "nl": "Klanten die dit boek kochten, kochten ook",
                    "pt-BR": "Clientes que compraram este eBook tamb\u00E9m compraram",
                    "ru": "\u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0438, \u043A\u0443\u043F\u0438\u0432\u0448\u0438\u0435 \u044D\u0442\u0443 \u043A\u043D\u0438\u0433\u0443, \u0442\u0430\u043A\u0436\u0435 \u043A\u0443\u043F\u0438\u043B\u0438",
                    "zh-CN": "\u8D2D\u4E70\u672C\u4E66\u7684\u987E\u5BA2\u8FD8\u4E70\u8FC7"
                }
            }
        }, {
            "id": "citationRecsBookGridWidgetWithTitle",
            "metricsTag": "rct",
            "options": {
                "dataKey": "citationRecs",
                "buyInStore": False,
                "buyButtonVisible": True,
                "showBadges": True,
                "refTagPartial": "r_c",
                "oneClickBorrowSupported": False,
                "showWishListButton": False
            },
            "class": "bookGrid",
            "strings": {
                "title": {
                    "de": "In diesem Buch erw\u00E4hnt",
                    "en": "Mentioned in this book",
                    "en-US": "Mentioned in this book",
                    "es": "Mencionado en este libro",
                    "fr": "Mentionn\u00E9s dans ce livre",
                    "it": "Menzionati in questo libro",
                    "ja": "\u3053\u306E\u4F5C\u54C1\u306B\u51FA\u3066\u304F\u308B\u672C",
                    "nl": "Genoemd in dit boek",
                    "pt-BR": "Mencionado neste eBook",
                    "ru": "\u0423\u043F\u043E\u043C\u0438\u043D\u0430\u0435\u0442\u0441\u044F \u0432 \u044D\u0442\u043E\u0439 \u043A\u043D\u0438\u0433\u0435",
                    "zh-CN": "\u672C\u4E66\u63D0\u53CA\u7684"
                }
            }
        }],
        "layouts": [{
            "metricsTag": "vl",
            "class": "verticalList",
            "widgetPlacements": {
                "body": [
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
            "requiredWidgets": ["ratingAndReviewWidget", "sharingWidget"]
        }, {
            "metricsTag": "vl",
            "class": "verticalList",
            "widgetPlacements": {
                "body": [
                    ["grokRatingAndReviewWidget", "ratingAndReviewWidget", "grokRatingWidget", "ratingWidget"],
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
        "data": {
            "customerProfile": {
                "class": "customerProfile",
                "penName": "Anonymous",
                "realName": "Anonymous"
            },
            "authorBios": {
                "class": "authorBioList",
                "authors": []
            }
        }
    }