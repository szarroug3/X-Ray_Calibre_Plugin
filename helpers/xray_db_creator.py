# xray_db_creator.py

from calibre_plugins.xray_creator.helpers.shelfari_parser import ShelfariParser
from calibre_plugins.xray_creator.helpers.book_parser import BookParser

class XRayDBCreator(object):
	def __init__(self, shelfari_url, book_path):
		self._shelfari_url = shelfari_url
		self._book_path = book_path
		# self._output_file_name = output_file_name

	def parse_shelfari_data(self):
		self._parsed_shelfari_data = ShelfariParser(self._shelfari_url).parse()

	def parse_book_data(self):
		self._parsed_book_data = BookParser(self._book_path, self._parsed_shelfari_data).parse()