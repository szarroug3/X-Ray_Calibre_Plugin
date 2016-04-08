# shelfari_parser.py

from HTMLParser import HTMLParser
from urllib2 import *
from lxml import html

# Parses shelfari page for characters, terms, and quotes
class ShelfariParser(Object):
	# global variables

	def __init__(self, url):
		response = urllib2.urlopen(url)
		page_source = response.read()
		self._html_source = html.fromstring(page_source)
		self._characters = {}
		self._terms = {}
		self._quotes = []

	@property
	def characters(self):
	    return self._characters

    @property
    def terms(self):
        return self._terms

    @property
    def quotes(self):
        return self._quotes
	
	def _get_characters(self):
		'''get characters from sheflari page'''
		charDesc = self._html_source.xpath('//div[@id="WikiModule_Characters"]//li//text()')
		charName = self._html_source.xpath('//div[@id="WikiModule_Characters"]//li//span/text()')
		self._characters = {char:desc for char, desc in zip(charName, charDesc)}

	def _get_terms(self):
		'''get terms from shelfari page'''

	def _get_quotes(self):
		'''get quotes from shelfari page'''
		quoteList = self._html_source.xpath('//div[@id="WikiModule_Quotations"]//li//blockquote/text()')
		self._quotes = [quote[1:-1] for quote in quoteList]

