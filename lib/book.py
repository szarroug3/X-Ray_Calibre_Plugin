# Book.py

class Book(object):
	# Status'
	SUCCESS = 0
	IN_PROGRESS = 1
	FAIL = 2

	# Status Messages
	FAILED_BASIC_INFORMATION_MISSING = 'Missing title, title sort, author, and/or author sort.'
    FAILED_COULD_NOT_FIND_AMAZON_PAGE = 'Could not find amazon page.'
	FAILED_COULD_NOT_FIND_SHELFARI_PAGE = 'Could not find shelfari page.'
    FAILED_UNSUPPORTED_FORMAT = 'Chosen format is unsupported.'
    FAILED_LOCAL_BOOK_NOT_FOUND = 'Local book not found.'
    FAILED_UNABLE_TO_PARSE_BOOK = 'Unable to parse book.'
    FAILED_UNABLE_TO_UPDATE_ASIN = 'Unable to update book\'s ASIN.'
    FAILED_UNABLE_TO_WRITE_XRAY = 'Unable to write x-ray file.'

    # allowed formats
    FMTS = ['mobi', 'azw3']

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
            self._status = self.FAIL
            self._status_message = self.FAILED_COULD_NOT_FIND_AMAZON_PAGE
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
            self._status = self.FAIL
            self._status_message = 'Could not parse shelfari data.'

    def get_format_specific_information(self):
        self._format_specific_info = []

        for fmt in self._formats:
            info = {'format': fmt}
            
            # check to make sure format is supported
            if fmt.lower() is not in self.FMTS:
                info['status'] = self.FAIL
                info['status_message'] = self.FAILED_UNSUPPORTED_FORMAT
                return

            # find local book if it exists; fail if it doesn't
            local_book = self._db.format_abspath(self._book_id, fmt.upper())
            if not local_path or not os.path.exists(local_book):
                info['status'] = self.FAIL
                info['status_message'] = self.FAILED_LOCAL_BOOK_NOT_FOUND
                return

            info['local_book'] = local_book
            info['local_xray'] = os.path.join('.'.join(local_book.split('.')[:-1]) + '.sdr', fmt.lower())
            info['device_book'] = os.path.join('documents', self._author_sort, self._title_sort + ' - ' + self._author_in_filename + '.' + fmt.lower())
            info['device_xray'] = '.'.join(info['device_book'].split('.')[:-1]) + '.sdr'

            self._format_specific_info.append(info)

    def parse_book(self):
        for info in self._format_specific_info:
            if info['status'] is not self.FAIL:
                try:
                    info['parsed_book_data'] = BookParser(info['format'], info['local_book'], self._parsed_shelfari_data)
                    info['parsed_book_data'].parse()
                except:
                    info['status'] = self.FAIL
                    info['status_message'] = self.FAILED_UNABLE_TO_PARSE_BOOK

    def get_book_asin(self):
        for info in self._format_specific_info:
            if info['status'] is not self.FAIL:
                try:
                    with open(info['local_book'], 'r+b') as stream:
                        mu = ASINUpdater(stream)
                        info['book_asin'] = mu.update(asin=self._asin)
                except:
                    info['status'] = self.FAIL
                    info['status_message'] = self.FAILED_UNABLE_TO_UPDATE_ASIN

    def write_xray(self):
        for info in self._format_specific_info:
            if info['status'] is not self.FAIL:
                try:
                    xray_db_writer = XRayDBWriter(info['local_xray'], info['book_asin'], self._shelfari_url, info['parse_book_data'])
                    xray_db_writer.create_xray()
                except:
                    info['status'] = self.FAIL
                    info['status_message'] = self.FAILED_UNABLE_TO_WRITE_XRAY




    def create_xray(self, log=None):
    	pass










class ASINUpdater(MetadataUpdater):
    def update(self, asin):
        def update_exth_record(rec):
            recs.append(rec)
            if rec[0] in self.original_exth_records:
                self.original_exth_records.pop(rec[0])

        if self.type != "BOOKMOBI":
                raise MobiError("Setting ASIN only supported for MOBI files of type 'BOOK'.\n"
                                "\tThis is a '%s' file of type '%s'" % (self.type[0:4], self.type[4:8]))

        recs = []
        if 113 in self.original_exth_records:
            asin = self.original_exth_records[113]
        elif 504 in self.original_exth_records:
            asin = self.original_exth_records[504]

        update_exth_record((113, asin.encode(self.codec, 'replace')))
        update_exth_record((504, asin.encode(self.codec, 'replace')))

        # Include remaining original EXTH fields
        for id in sorted(self.original_exth_records):
            recs.append((id, self.original_exth_records[id]))
        recs = sorted(recs, key=lambda x:(x[0],x[0]))

        exth = StringIO()
        for code, data in recs:
            exth.write(struct.pack('>II', code, len(data) + 8))
            exth.write(data)
        exth = exth.getvalue()
        trail = len(exth) % 4
        pad = '\0' * (4 - trail) # Always pad w/ at least 1 byte
        exth = ['EXTH', struct.pack('>II', len(exth) + 12, len(recs)), exth, pad]
        exth = ''.join(exth)

        if getattr(self, 'exth', None) is None:
            raise MobiError('No existing EXTH record. Cannot update ASIN.')

        self.create_exth(exth=exth)

        return asin