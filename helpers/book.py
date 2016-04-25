# Book.py

class Book(object):
	# Status'
	SUCCESS = 0
	IN_PROGRESS = 1
	FAIL = 2

	# Status Messages
	FAILED_BASIC_INFORMATION_MISSING = 'Missing title, title sort, author, and/or author sort.'
	FAILED_COULD_NOT_FIND_SHELFARI_PAGE = 'Could not find shelfari page.'

	def __init__(self, db, book_id, formats, spoilers=False, send_to_device=True, create_xray=True):
		self._db = db
		self._book_id = book_id
		self._formats = formats
		self._spoilers = spoilers
		self._send_to_device = send_to_device
		self._create_xray = create_xray
    	self._status = self.IN_PROGRESS
    	self._status_message = None

		self._get_basic_information()
		if self._status is self.FAIL:
			return

	@property
	def status(self):
	    return self._status

	@property
	def title(self):
	    return self._title
		
	@property
	def author(self):
	    return self._author
	

	# get book's title, title sort, author, author sort, and asin if it exists
	def _get_basic_information(self):
		self._title = self._db.field_for('title', self._book_id)
        self._title_sort = self._db.field_for('sort', self._book_id)

        self._author = self._db.field_for('authors', self._book_id)
        if len(self._author) > 0:
            self._author = ' & '.join(self._author)
        self._author_sort = self._db.field_for('author_sort', self._book_id)

        identifiers = self._db.field_for('identifiers', self._book_id)
        self._asin = self._db.field_for('identifiers', self._book_id)['mobi-asin'].decode('ascii') if 'mobi-asin' in identifiers.keys() else None
        if not self._title or not self._title_sort or not self._author or not self._author_sort:
        	self._status = self.FAIL
        	self._status_message = self.FAILED_BASIC_INFORMATION_MISSING
        	return

    	# if all basic information is available, sanitize information
        if self._author_sort[-1] == '.': self._author_sort = self._author_sort[:-1] + '_'
        self._author_sort = self._author_sort.replace(':', '_').replace('\"', '_')

        trailing_period = False
        while self._title_sort[-1] == '.':
            self._title_sort = self._title_sort[:-1]
            trailing_period = True
        if trailing_period:
            self._title_sort += '_'
        self._title_sort = self._title_sort.replace(':', '_').replace('\"', '_')

        trailing_period = False
        self._author_in_filename = self._author
        while self._author_in_filename[-1] == '.':
            self._author_in_filename = self._author_in_filename[:-1]
            trailing_period = True
        if trailing_period:
            self._author_in_filename += '_'
        self._author_in_filename = self._author_in_filename.replace(':', '_').replace('\"', '_')

    def get_asin(self, connection):
        query = urlencode({'keywords': '%s - %s' % ( self._title, self._author)})
        connection.request('GET', '/s/ref=sr_qz_back?sf=qz&rh=i%3Adigital-text%2Cn%3A154606011%2Ck%3A' + query[9:] + '&' + query, None, self.HEADERS)
        try:
            response = connection.getresponse().read()
        except BadStatusLine:
            connection.close()
            connection = HTTPConnection('www.amazon.com')
            connection.request('GET', '/s/ref=sr_qz_back?sf=qz&rh=i%3Adigital-text%2Cn%3A154606011%2Ck%3A' + query[9:] + '&' + query, None, self.HEADERS)
            response = connection.getresponse().read()

        # check to make sure there are results
        if 'did not match any products' in response and not 'Did you mean:' in response and not 'so we searched in All Departments' in response:
            self._status = 'Fail'
            self._status_message = 'Could not find amazon page.'
            return
        soup = BeautifulSoup(response)
        results = soup.findAll('div', {'id': 'resultsCol'})
        for r in results:
            if 'Buy now with 1-Click' in str(r):
                asinSearch = self.AMAZON_ASIN_PAT.search(str(r))
                if asinSearch:
                    self._asin = asinSearch.group(1)
                    return connection

    def get_shelfari_url(self, connection):
        query = urlencode ({'Keywords': self._asin})
        connection.request('GET', '/search/books?' + query)
        try:
            response = connection.getresponse().read()
        except BadStatusLine:
            connection.close()
            connection = HTTPConnection('www.shelfari.com')
            connection.request('GET', '/search/books?' + query)
            response = connection.getresponse().read()

        # check to make sure there are results
        if 'did not return any results' in response:
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_FIND_SHELFARI_PAGE
            return connection
        urlsearch = self.SHELFARI_URL_PAT.search(response)
        if not urlsearch:
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_FIND_SHELFARI_PAGE
            return connection
        self._shelfari_url = urlsearch.group(1)
        return connection

    def parse_shelfari_data(self):
        try:
            self._parsed_shelfari_data = ShelfariParser(self._shelfari_url, spoilers=self._spoilers)
            self._parsed_shelfari_data.parse()
        except Exception:
            self._status = 'Fail'
            self._status_message = 'Could not parse shelfari data.'




    def create_xray(self, log=None):
    	pass























                continue

            # Book definitely has title, title_sort, author, and author_sort at this point

           
            type_specific_data = []

            for book_type in types:
                type_info = {'type': book_type, 'local_book': db.format_abspath(book_id, book_type)}
                if not type_info['local_book']:
                    type_info['status'] = 'Fail'
                    type_info['status_message'] = 'Book path in %s format not found.' % book_type
                    type_specific_data.append(type_info)
                    continue

                # book path exists at this point
                type_info['status'] = 'In Progress'
                type_info['status_message'] = ''
                type_info['local_xray'] = os.path.join('.'.join(type_info['local_book'].split('.')[:-1]) + '.sdr', book_type)
                type_info['device_book'] = os.path.join('documents', author_sort, title_sort + ' - ' + author_in_filename + '.' + book_type.lower())
                type_info['device_xray'] = '.'.join(type_info['device_book'].split('.')[:-1]) + '.sdr'
                type_specific_data.append(type_info)
            self._books.append(Book(self._db, book_id, title, author, type_specific_data, asin, spoilers, create_xray))
