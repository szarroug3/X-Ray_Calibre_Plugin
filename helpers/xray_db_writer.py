# xray_db_writer.py

import os

from calibre_plugins.xray_creator.helpers.db_writer import DBWriter

class XRayDBWriter(object):
	def __init__(self, xray_directory, asin, parsed_data):
		self._filename = os.path.join(xray_directory, 'XRAY.entities.%s.asc' % asin)
		self._db_writer = DBWriter(self._filename)
		self._erl = parsed_data.erl
		self._excerpt_data = parsed_data.excerpt_data
        self._entity_data = parsed_data.entity_data

    def create_xray(self):
    	fill_book_metadata()
    	fill_entity()
    	fill_entity_description()
    	fill_entity_excerpt()
    	fill_occurrence()
    	fill_type()
    	self._db_writer.close()

    def fill_book_metadata(self):
    	pass

	def fill_entity(self):
		pass

	def fill_entity_description(self):
		pass

	def fill_entity_excerpt(self):
		pass

	def fill_excerpt(self):
		pass

	def fill_occurrence(self):
		pass

	def fill_type(self):
		pass