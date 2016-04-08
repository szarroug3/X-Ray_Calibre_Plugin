#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com>'
__docformat__ = 'restructuredtext en'

import time
from urllib import quote
from Queue import Queue, Empty

from lxml.html import fromstring, tostring

from calibre import as_unicode
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source, fixcase, fixauthors
from calibre.utils.icu import lower
from calibre.utils.cleantext import clean_ascii_chars

class Goodreads(Source):

    name = 'Goodreads'
    description = _('Downloads metadata and covers from Goodreads')
    author = 'Grant Drake'
    version = (1, 1, 11)
    minimum_calibre_version = (0, 8, 0)

    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'identifier:goodreads',
        'identifier:isbn', 'rating', 'comments', 'publisher', 'pubdate',
        'tags', 'series', 'languages'])
    has_html_comments = True
    supports_gzip_transfer_encoding = True

    BASE_URL = 'http://www.goodreads.com'
    MAX_EDITIONS = 5

    def config_widget(self):
        '''
        Overriding the default configuration screen for our own custom configuration
        '''
        from calibre_plugins.goodreads.config import ConfigWidget
        return ConfigWidget(self)

    def get_book_url(self, identifiers):
        goodreads_id = identifiers.get('goodreads', None)
        if goodreads_id:
            return ('goodreads', goodreads_id,
                    '%s/book/show/%s' % (Goodreads.BASE_URL, goodreads_id))

    def create_query(self, log, title=None, authors=None, identifiers={}):

        isbn = check_isbn(identifiers.get('isbn', None))
        q = ''
        if isbn is not None:
            q = 'search_type=books&search[query]=' + isbn
        elif title or authors:
            tokens = []
            title_tokens = list(self.get_title_tokens(title,
                                strip_joiners=False, strip_subtitle=True))
            tokens += title_tokens
            author_tokens = self.get_author_tokens(authors,
                    only_first_author=True)
            tokens += author_tokens
            tokens = [quote(t.encode('utf-8') if isinstance(t, unicode) else t) for t in tokens]
            q = '+'.join(tokens)
            q = 'search_type=books&search[query]=' + q

        if not q:
            return None
        if isinstance(q, unicode):
            q = q.encode('utf-8')
        return Goodreads.BASE_URL + '/search?' + q

    def get_cached_cover_url(self, identifiers):
        url = None
        goodreads_id = identifiers.get('goodreads', None)
        if goodreads_id is None:
            isbn = identifiers.get('isbn', None)
            if isbn is not None:
                goodreads_id = self.cached_isbn_to_identifier(isbn)
        if goodreads_id is not None:
            url = self.cached_identifier_to_cover_url(goodreads_id)

        return url

    def clean_downloaded_metadata(self, mi):
        '''
        Overridden from the calibre default so that we can stop this plugin messing
        with the tag casing coming from Goodreads
        '''
        docase = mi.language == 'eng' or mi.is_null('language')
        if docase and mi.title:
            mi.title = fixcase(mi.title)
        mi.authors = fixauthors(mi.authors)
        mi.isbn = check_isbn(mi.isbn)

    def identify(self, log, result_queue, abort, title=None, authors=None,
            identifiers={}, timeout=30):
        '''
        Note this method will retry without identifiers automatically if no
        match is found with identifiers.
        '''
        matches = []
        # Unlike the other metadata sources, if we have a goodreads id then we
        # do not need to fire a "search" at Goodreads.com. Instead we will be
        # able to go straight to the URL for that book.
        goodreads_id = identifiers.get('goodreads', None)
        isbn = check_isbn(identifiers.get('isbn', None))
        br = self.browser
        if goodreads_id:
            matches.append('%s/book/show/%s' % (Goodreads.BASE_URL, goodreads_id))
        else:
            query = self.create_query(log, title=title, authors=authors,
                    identifiers=identifiers)
            if query is None:
                log.error('Insufficient metadata to construct query')
                return
            try:
                log.info('Querying: %s' % query)
                response = br.open_novisit(query, timeout=timeout)
                if isbn:
                    # Check whether we got redirected to a book page for ISBN searches.
                    # If we did, will use the url.
                    # If we didn't then treat it as no matches on Goodreads
                    location = response.geturl()
                    if '/book/show/' in location:
                        log.info('ISBN match location: %r' % location)
                        matches.append(location)
            except Exception as e:
                err = 'Failed to make identify query: %r' % query
                log.exception(err)
                return as_unicode(e)

            # For ISBN based searches we have already done everything we need to
            # So anything from this point below is for title/author based searches.
            if not isbn:
                log.info('no isbn')
                try:
                    raw = response.read().strip()
                    #open('E:\\t.html', 'wb').write(raw)
                    raw = raw.decode('utf-8', errors='replace')
                    if not raw:
                        log.error('Failed to get raw result for query: %r' % query)
                        return
                    root = fromstring(clean_ascii_chars(raw))
                    log.info('response: %s' % root)
                except:
                    msg = 'Failed to parse goodreads page for query: %r' % query
                    log.exception(msg)
                    return msg
                # Now grab the first value from the search results, provided the
                # title and authors appear to be for the same book
                self._parse_search_results(log, title, authors, root, matches, timeout)

        if abort.is_set():
            return

        if not matches:
            if identifiers and title and authors:
                log.info('No matches found with identifiers, retrying using only'
                        ' title and authors')
                return self.identify(log, result_queue, abort, title=title,
                        authors=authors, timeout=timeout)
            log.error('No matches found with query: %r' % query)
            return

        from calibre_plugins.goodreads.worker import Worker
        workers = [Worker(url, result_queue, br, log, i, self) for i, url in
                enumerate(matches)]

        for w in workers:
            w.start()
            # Don't send all requests at the same time
            time.sleep(0.1)

        while not abort.is_set():
            a_worker_is_alive = False
            for w in workers:
                w.join(0.2)
                if abort.is_set():
                    break
                if w.is_alive():
                    a_worker_is_alive = True
            if not a_worker_is_alive:
                break

        return None

    def _parse_search_results(self, log, orig_title, orig_authors, root, matches, timeout):
        first_result = root.xpath('//table[@class="tableList"]/tr/td[2]')
        if not first_result:
            return
        title_tokens = list(self.get_title_tokens(orig_title))
        author_tokens = list(self.get_author_tokens(orig_authors))

        def ismatch(title, authors):
            authors = lower(' '.join(authors))
            title = lower(title)
            match = not title_tokens
            for t in title_tokens:
                if lower(t) in title:
                    match = True
                    break
            amatch = not author_tokens
            for a in author_tokens:
                if lower(a) in authors:
                    amatch = True
                    break
            if not author_tokens: amatch = True
            return match and amatch

        title = first_result[0].xpath('./a')[0].text_content().strip()
        authors = first_result[0].xpath('./span[@itemprop="author"]/a/span')[0].text_content().strip().split(',')
        if not ismatch(title, authors):
            log.error('Rejecting as not close enough match: %s %s' % (title, authors))
            return

        first_result_url_node = root.xpath('//table[@class="tableList"]/tr/td[1]/a[1]/@href')
        if first_result_url_node:
            import calibre_plugins.goodreads.config as cfg
            c = cfg.plugin_prefs[cfg.STORE_NAME]
            if c[cfg.KEY_GET_EDITIONS]:
                # We need to read the editions for this book and get the matches from those
                for editions_text in root.xpath('//table[@class="tableList"]/tr/td[2]/span/a[@href]/text()'):
                    #editions_text = tostring(editions_node, method='text').strip()
                    if editions_text == '1 edition':
                        # There is no point in doing the extra hop
                        log.info('Not scanning editions as only one edition found')
                        break
                    #editions_url = Goodreads.BASE_URL + editions_node.get('href')
                    editions_url = Goodreads.BASE_URL + editions_text.getparent().get('href')
                    if '/work/editions/' in editions_url:
                        log.info('Examining up to %s: %s' % (editions_text, editions_url))
                        self._parse_editions_for_book(log, editions_url, matches, timeout, title_tokens)
                        return
            result_url = Goodreads.BASE_URL + first_result_url_node[0]
            matches.append(result_url)

    def _parse_editions_for_book(self, log, editions_url, matches, timeout, title_tokens):

        def ismatch(title):
            title = lower(title)
            match = not title_tokens
            for t in title_tokens:
                if lower(t) in title:
                    match = True
                    break
            return match

        br = self.browser
        try:
            raw = br.open_novisit(editions_url, timeout=timeout).read().strip()
        except Exception as e:
            err = 'Failed identify editions query: %r' % editions_url
            log.exception(err)
            return as_unicode(e)
        try:
            raw = raw.decode('utf-8', errors='replace')
            if not raw:
                log.error('Failed to get raw result for query: %r' % editions_url)
                return
            #open('E:\\s.html', 'wb').write(raw)
            root = fromstring(clean_ascii_chars(raw))
        except:
            msg = 'Failed to parse goodreads page for query: %r' % editions_url
            log.exception(msg)
            return msg

        first_non_valid = None
        for div_link in root.xpath('//div[@class="editionData"]/div[1]/a[@class="bookTitle"]'):
            title = tostring(div_link, 'text').strip().lower()
            if title:
                # Verify it is not an audio edition
                valid_title = True
                for exclusion in ['(audio cd)', '(compact disc)', '(audio cassette)']:
                    if exclusion in title:
                        log.info('Skipping audio edition: %s' % title)
                        valid_title = False
                        if first_non_valid is None:
                            first_non_valid = Goodreads.BASE_URL + div_link.get('href')
                        break
                if valid_title:
                    # Verify it is not a foreign language edition
                    if not ismatch(title):
                        log.info('Skipping alternate title:', title)
                        continue
                    matches.append(Goodreads.BASE_URL + div_link.get('href'))
                    if len(matches) >= Goodreads.MAX_EDITIONS:
                        return
        if len(matches) == 0 and first_non_valid:
            # We have found only audio editions. In which case return the first match
            # rather than tell the user there are no matches.
            log.info('Choosing the first audio edition as no others found.')
            matches.append(first_non_valid)

    def download_cover(self, log, result_queue, abort,
            title=None, authors=None, identifiers={}, timeout=30):
        cached_url = self.get_cached_cover_url(identifiers)
        if cached_url is None:
            log.info('No cached cover found, running identify')
            rq = Queue()
            self.identify(log, rq, abort, title=title, authors=authors,
                    identifiers=identifiers)
            if abort.is_set():
                return
            results = []
            while True:
                try:
                    results.append(rq.get_nowait())
                except Empty:
                    break
            results.sort(key=self.identify_results_keygen(
                title=title, authors=authors, identifiers=identifiers))
            for mi in results:
                cached_url = self.get_cached_cover_url(mi.identifiers)
                if cached_url is not None:
                    break
        if cached_url is None:
            log.info('No cover found')
            return

        if abort.is_set():
            return
        br = self.browser
        log('Downloading cover from:', cached_url)
        try:
            cdata = br.open_novisit(cached_url, timeout=timeout).read()
            result_queue.put((self, cdata))
        except:
            log.exception('Failed to download cover from:', cached_url)


if __name__ == '__main__': # tests
    # To run these test use:
    # calibre-debug -e __init__.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin,
            title_test, authors_test, series_test)

    test_identify_plugin(Goodreads.name,
        [
            (# A book with an ISBN
                {'identifiers':{'isbn': '9780385340588'},
                    'title':'61 Hours', 'authors':['Lee Child']},
                [title_test('61 Hours', exact=True),
                 authors_test(['Lee Child']),
                 series_test('Jack Reacher', 14.0)]
            ),

            (# A book throwing an index error
                {'title':'The Girl Hunters', 'authors':['Mickey Spillane']},
                [title_test('The Girl Hunters', exact=True),
                 authors_test(['Mickey Spillane']),
                 series_test('Mike Hammer', 7.0)]
            ),

            (# A book with no ISBN specified
                {'title':"Playing with Fire", 'authors':['Derek Landy']},
                [title_test("Playing with Fire", exact=True),
                 authors_test(['Derek Landy']),
                 series_test('Skulduggery Pleasant', 2.0)]
            ),

            (# A book with a Goodreads id
                {'identifiers':{'goodreads': '6977769'},
                    'title':'61 Hours', 'authors':['Lee Child']},
                [title_test('61 Hours', exact=True),
                 authors_test(['Lee Child']),
                 series_test('Jack Reacher', 14.0)]
            ),

        ])


