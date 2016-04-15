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
    	srl = num_images = show_spoilers_default = 0;
    	has_excerpts = 1 if self._excerpt_data > 0 else 0
    	num_people = sum(1 for char in self._entity_data.keys() if char['type'] == '1')
    	num_terms = sum(1 for term in self._entity_data.keys() if term['type'] == '2')
    	self._db_writer.insert_into_book_metadata([srl, self._erl, 0, has_excerpts, show_spoilers_default, num_people, num_terms, num_images, None])

	def fill_entity(self):
		for entity in self._entity_data.keys():
			label = entity['label']
			entity_type = entity['type']
			count = entity['mentions']
			has_info_card = 1 if entity['description'] else 0
			self._db_writer.insert_into_entity([entity, label, None, entity_type, count, has_info_card])

	def fill_entity_description(self):
		for entity in self._entity_data.keys():
			text = entity['description']
			source_wildcard = entity['label']
			source = 2
			self._db_writer.insert_into_entity_description([text, source_wildcard, source, entity])

	def fill_entity_excerpt(self):
		for entity in self._entity_data.keys():
			for excerpt_id in entity['excerpt_ids']:
				self._db_writer.insert_into_entity_excerpt([entity, excerpt_id])

	def fill_excerpt(self):
		for excerpt in self._excerpt_data.keys():
			start = excerpt['loc']
			length = excerpt['len']
			image = ''
			related_entities = ','.join(excerpt['related_entities'])
			self._db_writer.insert_into_excerpt([excerpt, start, length, image, related_entities, None])

	def fill_occurrence(self):
		for entity in self._entity_data.keys():
			for excerpt in entity['occurrence']:
				self._db_writer.insert_into_occurrence([entity, excerpt['loc'], excerpt['len']])

	def fill_type(self):
		top_mentioned_people = [(entity_id, self._entity_data[entity_id]['mentions']) for entity_id in self._entity_data.keys() if self._entity_data[entity_id]['source'] == 1]
		top_mentioned_people.sort(key=lambda x:x[2], reverse=True)
		if len(top_mentioned_people) > 10:
			top_mentioned_people = top_mentioned_people[:10]
		top_mentioned_people = [entity_id for entity_id, mentions in top_mentioned_people]
		self._db_writer.update_type(1, ','.join(top_mentioned_people))

		top_mentioned_terms = [(entity_id, self._entity_data[entity_id]['mentions']) for entity_id in self._entity_data.keys() if self._entity_data[entity_id]['source'] == 2]
		top_mentioned_terms.sort(key=lambda x:x[2], reverse=True)
		if len(top_mentioned_terms) > 10:
			top_mentioned_terms = top_mentioned_terms[:10]
		top_mentioned_terms = [entity_id for entity_id, mentions in top_mentioned_terms]
		self._db_writer.update_type(1, ','.join(top_mentioned_terms))