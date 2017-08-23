# xray_db_writer.py
'''Injects x-ray data into DBWriter'''

import os

from calibre_plugins.xray_creator.lib.db_writer import DBWriter

class XRayDBWriter(object):
    '''Uses DBWriter to write x-ray data into file'''
    def __init__(self, xray_directory, goodreads_url, asin, parsed_data):
        filename = os.path.join(xray_directory, 'XRAY.entities.{0}.asc'.format(asin))
        if not os.path.exists(xray_directory):
            os.mkdir(xray_directory)
        self._db_writer = DBWriter(filename)
        self._goodreads_url = goodreads_url
        self._erl = parsed_data['erl']
        self._excerpt_data = parsed_data['excerpt_data']
        self._notable_clips = parsed_data['notable_clips']
        self._entity_data = parsed_data['entity_data']
        self._codec = parsed_data['codec']

    def write_xray(self):
        '''Write all data into file'''
        self.fill_book_metadata()
        self.fill_entity()
        self.fill_entity_description()
        self.fill_entity_excerpt()
        self.fill_excerpt()
        self.fill_occurrence()
        self.update_string()
        self.update_type()
        self._db_writer.create_indices()
        self._db_writer.save()
        self._db_writer.close()

    def fill_book_metadata(self):
        '''Write book_metadata table'''
        srl = num_images = show_spoilers_default = '0'
        has_excerpts = '1' if self._excerpt_data > 0 else '0'
        num_people = sum(1 for char in self._entity_data.keys() if self._entity_data[char]['type'] == 1)
        num_people_str = str(num_people)
        num_terms = sum(1 for term in self._entity_data.keys() if self._entity_data[term]['type'] == 2)
        num_terms_str = str(num_terms)
        self._db_writer.insert_into_book_metadata((srl, self._erl, 0, has_excerpts, show_spoilers_default, num_people_str,
                                                   num_terms_str, num_images, None))

    def fill_entity(self):
        '''Writes entity table'''
        entity_data = []
        for entity in self._entity_data.keys():
            original_label = self._entity_data[entity]['original_label']
            entity_id = str(self._entity_data[entity]['entity_id'])
            entity_type = str(self._entity_data[entity]['type'])
            count = str(self._entity_data[entity]['mentions'])
            has_info_card = '1' if self._entity_data[entity]['description'] else '0'
            entity_data.append((entity_id, original_label, None, entity_type, count, has_info_card))
        self._db_writer.insert_into_entity(entity_data)

    def fill_entity_description(self):
        '''Writes entity_description table'''
        entity_description_data = []
        for entity in self._entity_data.keys():
            original_label = self._entity_data[entity]['original_label']
            entity_id = str(self._entity_data[entity]['entity_id'])
            text = str(self._entity_data[entity]['description'])
            source = str(self._entity_data[entity]['type'])
            entity_description_data.append((text, original_label, source, entity_id))
        self._db_writer.insert_into_entity_description(entity_description_data)

    def fill_entity_excerpt(self):
        '''Writes entity_excerpt table'''
        entity_excerpt_data = []

        # add notable clips to entity_excerpt as entity 0
        for notable_clip in self._notable_clips:
            entity_excerpt_data.append(('0', str(notable_clip)))

        for entity in self._entity_data.keys():
            entity_id = str(self._entity_data[entity]['entity_id'])
            for excerpt_id in self._entity_data[entity]['excerpt_ids']:
                entity_excerpt_data.append((str(entity_id), str(excerpt_id)))
        self._db_writer.insert_into_entity_excerpt(entity_excerpt_data)

    def fill_excerpt(self):
        '''Writes excerpt table'''
        excerpt_data = []
        for excerpt_id in self._excerpt_data.keys():
            if len(self._excerpt_data[excerpt_id]['related_entities']) > 0 or excerpt_id in self._notable_clips:
                start = str(self._excerpt_data[excerpt_id]['loc'])
                length = str(self._excerpt_data[excerpt_id]['len'])
                image = ''
                related_entities_list = [str(entity_id) for entity_id in self._excerpt_data[excerpt_id]['related_entities']]
                related_entities = ','.join(related_entities_list)
                excerpt_data.append((str(excerpt_id), start, length, image, related_entities, None))
        self._db_writer.insert_into_excerpt(excerpt_data)

    def fill_occurrence(self):
        '''Writes occurrence table'''
        occurrence_data = []
        for entity in self._entity_data.keys():
            entity_id = str(self._entity_data[entity]['entity_id'])
            for excerpt in self._entity_data[entity]['occurrence']:
                occurrence_data.append((entity_id, str(excerpt['loc']),
                                        str(excerpt['len'])))
        self._db_writer.insert_into_occurrence(occurrence_data)

    def update_string(self):
        '''Updates goodreads url string'''
        self._db_writer.update_string(self._goodreads_url)

    def update_type(self):
        '''Updates type table using character/settings data'''
        top_mentioned_people = []
        top_mentioned_terms = []
        for data in self._entity_data.values():
            if data['type'] == 1:
                top_mentioned_people.append((str(data['entity_id']), data['mentions']))
            elif data['type'] == 2:
                top_mentioned_terms.append((str(data['entity_id']), data['mentions']))

        top_mentioned_people.sort(key=lambda x: x[1], reverse=True)
        top_mentioned_terms.sort(key=lambda x: x[1], reverse=True)

        if len(top_mentioned_people) > 10:
            top_mentioned_people = top_mentioned_people[:10]
        top_mentioned_people = [mentions[0] for mentions in top_mentioned_people]

        if len(top_mentioned_terms) > 10:
            top_mentioned_terms = top_mentioned_terms[:10]
        top_mentioned_terms = [mentions[0] for mentions in top_mentioned_terms]

        self._db_writer.update_type(1, ','.join(top_mentioned_people))
        self._db_writer.update_type(2, ','.join(top_mentioned_terms))
