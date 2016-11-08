# db_writer.py
'''Writes x-ray data into file using given information'''

import os
import json
from sqlite3 import connect, Binary

class DBWriter(object):
    '''Writes x-ray data into file using given information'''
    def __init__(self, filename):
        if os.path.exists(filename):
            os.remove(filename)
        self._connection = connect(filename)
        self._connection.text_factory = Binary
        self._cursor = self._connection.cursor()
        self._import_base_db()

    def save(self):
        '''Saves changes into file'''
        self._connection.commit()

    def close(self):
        '''Closes file'''
        self._connection.close()

    def _import_base_db(self):
        '''Imports base data into file'''
        self._cursor.execute('PRAGMA user_version = 1')
        self._cursor.execute('PRAGMA encoding = utf8')

        # create tables
        self._cursor.execute('CREATE TABLE type(id INTEGER, label INTEGER, singular_label INTEGER, '
                             'icon INTEGER, top_mentioned_entities TEXT, PRIMARY KEY(id))')
        self._cursor.execute('CREATE TABLE string(id INTEGER, language TEXT, text TEXT)')
        self._cursor.execute('CREATE TABLE source(id INTEGER, label INTEGER, url INTEGER, '
                             'license_label INTEGER, license_url INTEGER, PRIMARY KEY(id))')
        self._cursor.execute('CREATE TABLE occurrence(entity INTEGER, start INTEGER, length INTEGER)')
        self._cursor.execute('CREATE TABLE excerpt(id INTEGER, start INTEGER, length INTEGER, '
                             'image TEXT, related_entities TEXT, goto INTEGER, PRIMARY KEY(id))')
        self._cursor.execute('CREATE TABLE entity_excerpt(entity INTEGER, excerpt INTEGER)')
        self._cursor.execute('CREATE TABLE entity_description(text TEXT, source_wildcard TEXT, '
                             'source INTEGER, entity INTEGER, PRIMARY KEY(entity))')
        self._cursor.execute('CREATE TABLE entity(id INTEGER, label TEXT, loc_label INTEGER, '
                             'type INTEGER, count INTEGER, has_info_card TINYINT, PRIMARY KEY(id))')
        self._cursor.execute('CREATE TABLE book_metadata(srl INTEGER, erl INTEGER, has_images TINYINT, '
                             'has_excerpts TINYINT, show_spoilers_default TINYINT, num_people INTEGER, '
                             'num_terms INTEGER, num_images INTEGER, preview_images TEXT)')

        # insert base data
        dir_path = os.path.join(os.getcwd(), 'lib')
        with open(os.path.join(dir_path, 'xray_data_template.json'), 'r') as template:
            xray_templates = json.load(template)

        self._insert_into_table('type', xray_templates['BASE_DB_TYPE'])
        self._insert_into_table('source', xray_templates['BASE_DB_SOURCE'])
        self._insert_into_table('entity', xray_templates['BASE_DB_ENTITY'])
        self._insert_into_table('string', xray_templates['BASE_DB_STRING'])

    def _insert_into_table(self, table_name, data):
        '''Import given data into table named table_name'''
        if len(data) == 0:
            return
        if isinstance(data, list):
            params = ['?'] * len(data[0])
            self._cursor.executemany('INSERT INTO %s VALUES (%s)' % (table_name, ','.join(params)), data)
        elif isinstance(data, tuple):
            params = ['?'] * len(data)
            self._cursor.execute('INSERT INTO %s VALUES (%s)' % (table_name, ','.join(params)), data)
        else:
            raise ValueError('data is invalid. Expected list or tuple, found %s' % type(data))

    def insert_into_book_metadata(self, data):
        '''Insert data into the book_metadata table'''
        self._insert_into_table('book_metadata', data)

    def insert_into_entity(self, data):
        '''Insert data into the entity table'''
        self._insert_into_table('entity', data)

    def insert_into_entity_description(self, data):
        '''Insert data into the entity_description table'''
        self._insert_into_table('entity_description', data)

    def insert_into_entity_excerpt(self, data):
        '''Insert data into the entity_excerpt table'''
        self._insert_into_table('entity_excerpt', data)

    def insert_into_excerpt(self, data):
        '''Insert data into the excerpt table'''
        self._insert_into_table('excerpt', data)

    def insert_into_occurrence(self, data):
        '''Insert data into the occurrence table'''
        self._insert_into_table('occurrence', data)

    def update_string(self, url):
        '''Update Goodreads url in string table'''
        self._cursor.execute('UPDATE string SET text=? WHERE id=15', (url, ))
        self._connection.commit()

    def update_type(self, type_id, data):
        '''Update top_mentioned_entities in type table'''
        if type_id != 1 and type_id != 2:
            raise ValueError('type_id %i is invalid; must be 1 or 2.' % type_id)
        self._cursor.execute('UPDATE type SET top_mentioned_entities=? WHERE id=?', (data, type_id))

    def create_indices(self):
        '''Creates default indices used by kindle'''
        self._cursor.execute('CREATE INDEX idx_entity_excerpt ON entity_excerpt(entity ASC)')
        self._cursor.execute('CREATE INDEX idx_entity_type ON entity(type ASC)')
        self._cursor.execute('CREATE INDEX idx_occurrence_start ON occurrence(start ASC)')
