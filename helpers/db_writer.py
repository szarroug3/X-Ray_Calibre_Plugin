# db_writer.py

from sqlite3 import *
import os

class DBWriter(object):
	def __init__(self, filename):
		if (os.path.exists(filename)):
			os.remove(filename)
		self._connection = connect(filename)
		self._cursor = self._connection.cursor()
		self._import_base_db()

	def close(self):
		self._connection.close()

	def _import_base_db(self):
		with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'helpers', 'BaseDB.sql'), 'r') as baseDBFile:
			commands = baseDBFile.read().split(';\n')

		for cmd in commands:
			self._cursor.execute(cmd)

		self._cursor.execute('PRAGMA user_version = 1')
		self._cursor.execute('PRAGMA encoding = utf8')

	def _insert_into_table(self, tableName, data):
		if isinstance(data, list):
			params = ['?' for d in data[0]]
			self._cursor.executemany('INSERT INTO %s VALUES (%s)' % (tableName, ','.join(params)), data)
		elif isinstance(data, tuple):
			params = ['?' for d in data]
			self._cursor.execute('INSERT INTO %s VALUES (%s)' % (tableName, ','.join(params)), data)
		else:
			raise ValueError('data is invalid. Expected list or tuple, found %s' % type(data))
		self._connection.commit()

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

	def update_type(self, type_id, data):
		'''Update top_mentioned_entities in type table'''
		if type_id != 1 and type_id != 2:
			raise ValueError('type_id %i is invalid; must be 1 or 2.' % type_id)
		data = str(data)
		self._cursor.execute('UPDATE type SET top_mentioned_entities=? WHERE id=?', (data, type_id))
		self._connection.commit()

	def create_indices(self):
		self._cursor.execute('CREATE INDEX idx_entity_excerpt ON entity_excerpt(entity ASC)')
		self._cursor.execute('CREATE INDEX idx_entity_type ON entity(type ASC)')
		self._cursor.execute('CREATE INDEX idx_occurrence_start ON occurrence(start ASC)')
		self._connection.commit()