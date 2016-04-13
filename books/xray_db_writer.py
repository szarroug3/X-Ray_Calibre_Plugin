# xray_db_writer.py

from sqlite3 import *
import os

class XRayDBWriter(object):
	def __init__(self, filename):
		fileExists = True if (os.path.exists(filename)) else False
		self._connection = connect(filename)
		self._cursor = self._connection.cursor()
		if not fileExists:
			self._importBaseDB()

	def __del__(self):
		self._connection.close()

	def _importBaseDB(self):
		with open(os.path.join(os.path.dirname(__file__), 'BaseDB.sql'), 'r') as baseDBFile:
			commands = baseDBFile.read().split(';\n')

		for cmd in commands:
			self._cursor.execute(cmd)

	def _insertIntoTable(self, tableName, data):
		data = [str(d) for d in data]
		self._cursor.execute('INSERT INTO %s VALUES (%s)' % (tableName, ','.join(data)))
		self._connection.commit()	

	def insertIntoBookMetadata(self, data):
		'''Insert data into the book_metadata table'''
		self._insertIntoTable('book_metadata', data)

	def insertIntoEntity(self, data):
		'''Insert data into the entity table'''
		self._insertIntoTable('entity', data)

	def insertIntoEntityDescription(self, data):
		'''Insert data into the entity_description table'''
		self._insertIntoTable('entity_description', data)

	def insertIntoEntityExcerpt(self, data):
		'''Insert data into the entity_excerpt table'''
		self._insertIntoTable('entity_excerpt', data)

	def insertIntoExcerpt(self, data):
		'''Insert data into the excerpt table'''
		self._insertIntoTable('excerpt', data)

	def insertIntoOccurrence(self, data):
		'''Insert data into the occurrence table'''
		self._insertIntoTable('occurrence', data)

	def updateType(self, typeID, data):
		'''Update top_mentioned_entities in type table'''

		if entityID != 1 and entityID != 2:
			raise ValueError('typeID %i is invalid; must be 1 or 2.' % typeID)
		data = str(data)
		self._cursor.execute('UPDATE type SET top_mentioned_entities=? WHERE id=?', (data, typeID))
		self._connection.commit()