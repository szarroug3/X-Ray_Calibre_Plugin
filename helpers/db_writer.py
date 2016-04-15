# db_writer.py

from sqlite3 import *
import os

class DBWriter(object):
	def __init__(self, filename):
		fileExists = True if (os.path.exists(filename)) else False
		self._connection = connect(filename)
		self._cursor = self._connection.cursor()
		if not fileExists:
			self._import_base_db()

	def close(self):
		self._connection.close()

	def _import_base_db(self):
		with open(os.path.join(os.path.dirname(__file__), 'BaseDB.sql'), 'r') as baseDBFile:
			commands = baseDBFile.read().split(';\n')

		for cmd in commands:
			self._cursor.execute(cmd)

	def _insert_into_table(self, tableName, data):
		data = [str(d) for d in data]
		self._cursor.execute('INSERT INTO %s VALUES (%s)' % (tableName, ','.join(data)))
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

	def update_type(self, typeID, data):
		'''Update top_mentioned_entities in type table'''

		if entityID != 1 and entityID != 2:
			raise ValueError('typeID %i is invalid; must be 1 or 2.' % typeID)
		data = str(data)
		self._cursor.execute('UPDATE type SET top_mentioned_entities=? WHERE id=?', (data, typeID))
		self._connection.commit()