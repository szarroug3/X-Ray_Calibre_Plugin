#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com>'
__docformat__ = 'restructuredtext en'

import copy
from collections import OrderedDict
try:
    from PyQt5 import Qt as QtGui
    from PyQt5.Qt import (QWidget, QVBoxLayout, QLabel,
                          QGroupBox, QGridLayout, QListWidget, QListWidgetItem,
                          QAbstractItemView, Qt, QPushButton)
except:
    from PyQt4 import QtGui
    from PyQt4.Qt import (QWidget, QVBoxLayout, QLabel,
                          QGroupBox, QGridLayout, QListWidget, QListWidgetItem,
                          QAbstractItemView, Qt, QPushButton)

from calibre.gui2.actions import menu_action_unique_name
from calibre.gui2.complete2 import EditWithComplete
from calibre.utils.config import JSONConfig

from calibre_plugins.quality_check.common_utils import (get_icon, KeyboardConfigDialog, convert_qvariant,
                                        get_library_uuid, PrefsViewerDialog, KeyValueComboBox)

KEY_SCHEMA_VERSION = STORE_SCHEMA_VERSION = 'SchemaVersion'
DEFAULT_SCHEMA_VERSION = 1.9

STORE_OPTIONS = 'options'
KEY_MAX_TAGS = 'maxTags'
KEY_MAX_TAG_EXCLUSIONS = 'maxTagExclusions'
KEY_HIDDEN_MENUS = 'hiddenMenus'
KEY_SEARCH_SCOPE = 'searchScope'

SCOPE_LIBRARY = 'Library'
SCOPE_SELECTION = 'Selection'

DEFAULT_STORE_VALUES = {
                           KEY_MAX_TAGS: 5,
                           KEY_MAX_TAG_EXCLUSIONS: [],
                           KEY_HIDDEN_MENUS: [],
                       }

# Per library we store an exclusions map
# 'settings': { 'exclusionsByCheck':  { 'check_epub_jacket':[1,2,3], ... } } }
# Exclusions map is a dictionary keyed by quality check menu of lists of book ids excluded from check
# e.g. { 'check_epub_jacket': [1,2,3] }
PREFS_NAMESPACE = 'QualityCheckPlugin'
PREFS_KEY_SETTINGS = 'settings'
KEY_EXCLUSIONS_BY_CHECK = 'exclusionsByCheck'
KEY_AUTHOR_INITIALS_MODE = 'authorInitialsMode'
AUTHOR_INITIALS_MODES = ['A.B.', 'A. B.', 'A B', 'AB']

DEFAULT_LIBRARY_VALUES = {
                          KEY_EXCLUSIONS_BY_CHECK: {  },
                         }

PLUGIN_MENUS = OrderedDict([
       ('check_covers',             {'name': 'Check covers...',                'cat':'covers',   'sub_menu': '',                         'group': 0, 'excludable': True,  'image': 'images/check_cover.png',                'tooltip':'Find books with book covers matching your criteria'}),

       ('check_epub_jacket',        {'name': 'Check having any jacket',        'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 0, 'excludable': True,  'image': 'images/check_epub_jacket.png',          'tooltip':'Check for ePub formats which have any calibre jacket'}),
       ('check_epub_legacy_jacket', {'name': 'Check having legacy jacket',     'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 0, 'excludable': True,  'image': 'images/check_epub_jacket_legacy.png',   'tooltip':'Check for ePub formats which have a calibre jacket from versions prior to 0.6.51'}),
       ('check_epub_multi_jacket',  {'name': 'Check having multiple jackets',  'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 0, 'excludable': True,  'image': 'images/check_epub_jacket_multi.png',    'tooltip':'Check for ePub formats which have multiple jackets'}),
       ('check_epub_no_jacket',     {'name': 'Check missing jacket',           'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 0, 'excludable': True,  'image': 'images/check_epub_jacket_missing.png',  'tooltip':'Check for ePub formats which do not have a jacket'}),
       ('check_epub_no_container',  {'name': 'Check missing container.xml',    'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 1, 'excludable': True,  'image': 'images/check_epub_no_container.png',    'tooltip':'Check for ePub formats with a missing container.xml indicating an invalid ePub'}),
       ('check_epub_namespaces',    {'name': 'Check invalid namespaces',       'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 1, 'excludable': True,  'image': 'images/check_epub_namespaces.png',      'tooltip':'Check for ePub formats with invalid namespaces in the container xml or opf manifest'}),
       ('check_epub_non_dc_meta',   {'name': 'Check non-dc: metadata',         'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 1, 'excludable': True,  'image': 'images/check_epub_non_dc.png',          'tooltip':'Check for ePub formats with metadata elements in the opf manifest that are not in the dc: namespace'}),
       ('check_epub_files_missing', {'name': 'Check manifest files missing',   'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 1, 'excludable': True,  'image': 'images/check_epub_files_missing.png',   'tooltip':'Check for ePub formats with files missing that are listed in their opf manifest'}),
       ('check_epub_unman_files',   {'name': 'Check unmanifested files',       'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 1, 'excludable': True,  'image': 'images/check_epub_unmanifested.png',    'tooltip':'Check for ePub formats with files that are not listed in their opf manifest excluding iTunes/bookmarks'}),
       ('check_epub_unused_css',    {'name': 'Check unused CSS files',         'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 1, 'excludable': True,  'image': 'images/check_epub_unused_css.png',      'tooltip':'Check for ePub formats with CSS files that are not referenced from any html pages'}),
       ('check_epub_unused_images', {'name': 'Check unused image files',       'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 2, 'excludable': True,  'image': 'images/check_epub_unused_image.png',    'tooltip':'Check for ePub formats with image files that are not referenced from the xhtml pages'}),
       ('check_epub_broken_images', {'name': 'Check broken image links',       'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 2, 'excludable': True,  'image': 'images/check_epub_unused_image.png',    'tooltip':'Check for ePub formats with html pages that contain broken links to images'}),
       ('check_epub_itunes',        {'name': 'Check iTunes files',             'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 3, 'excludable': True,  'image': 'images/check_epub_itunes.png',          'tooltip':'Check for ePub formats with an iTunesMetadata.plist or iTunesArtwork file'}),
       ('check_epub_bookmark',      {'name': 'Check calibre bookmark files',   'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 3, 'excludable': True,  'image': 'images/check_epub_bookmarks.png',       'tooltip':'Check for ePub formats with a calibre bookmarks file'}),
       ('check_epub_os_artifacts',  {'name': 'Check OS artifacts',             'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 3, 'excludable': True,  'image': 'images/check_epub_os_files.png',        'tooltip':'Check for ePub formats with OS artifacts of .DS_Store or Thumbs.db'}),
       ('check_epub_toc_hierarchy', {'name': 'Check NCX TOC hierarchical',     'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 4, 'excludable': True,  'image': 'images/check_epub_toc_hierarchical.png','tooltip':'Check for ePub formats with a NCX file TOC which is not flat (i.e. hierarchical)'}),
       ('check_epub_toc_size',      {'name': 'Check NCX TOC with < 3 entries', 'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 4, 'excludable': True,  'image': 'images/check_epub_toc_size.png',        'tooltip':'Check for ePub formats with a NCX file TOC with less than 3 entries'}),
       ('check_epub_toc_broken',    {'name': 'Check NCX TOC with broken links','cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 4, 'excludable': True,  'image': 'images/check_epub_toc_broken.png',      'tooltip':'Check for ePub formats with a NCX file TOC that contains broken html links'}),
       ('check_epub_guide_broken',  {'name': 'Check <guide> broken links',     'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 5, 'excludable': True,  'image': 'images/check_epub_guide_broken.png',    'tooltip':'Check for ePub formats with broken links in the <guide> section of the manifest'}),
       ('check_epub_html_size',     {'name': 'Check oversize html files',      'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 6, 'excludable': True,  'image': 'images/check_epub_html_size.png',       'tooltip':'Check for ePub formats with an individual html file size that requires splitting on some devices'}),
       ('check_epub_drm',           {'name': 'Check DRM',                      'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 7, 'excludable': True,  'image': 'images/check_epub_drm.png',             'tooltip':'Check for ePub formats with DRM encryption xml files'}),
       ('check_epub_drm_meta',      {'name': 'Check Adobe DRM meta tag',       'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 7, 'excludable': True,  'image': 'images/check_epub_drm.png',             'tooltip':'Check for ePub formats that contain html pages with an Adobe DRM meta identifier tag'}),
       ('check_epub_repl_cover',    {'name': 'Check replaceable cover',        'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 8, 'excludable': True,  'image': 'images/check_epub_cover.png',           'tooltip':'Check for ePub formats with a cover that can be replaced when exporting or updating metadata with Modify ePub'}),
       ('check_epub_no_repl_cover', {'name': 'Check non-replaceable cover',    'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 8, 'excludable': True,  'image': 'images/check_epub_no_cover.png',        'tooltip':'Check for ePub formats with no cover or a cover that cannot be replaced without a calibre conversion'}),
       ('check_epub_svg_cover',     {'name': 'Check calibre SVG cover',        'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 8, 'excludable': True,  'image': 'images/check_epub_cover.png',           'tooltip':'Check for ePub formats with a cover that has been inserted by a calibre conversion or Modify ePub and that is SVG'}),
       ('check_epub_no_svg_cover',  {'name': 'Check no calibre SVG cover',     'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group': 8, 'excludable': True,  'image': 'images/check_epub_no_cover.png',        'tooltip':'Check for ePub formats that have no calibre cover inserted by a calibre conversion or Modify ePub that is SVG'}),
       ('check_epub_converted',     {'name': 'Check calibre conversion',       'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group':12, 'excludable': True,  'image': 'images/check_epub_converted.png',       'tooltip':'Check for ePub formats that have been converted by calibre'}),
       ('check_epub_not_converted', {'name': 'Check not calibre conversion',   'cat':'epub',     'sub_menu': 'Check ePub Structure',     'group':12, 'excludable': True,  'image': 'images/check_epub_not_converted.png',   'tooltip':'Check for ePub formats that have not been converted by calibre'}),

       ('check_epub_address',       {'name': 'Check <address> smart-tags',     'cat':'epub',     'sub_menu': 'Check ePub Style',     'group': 0, 'excludable': True,  'image': 'images/check_epub_address.png',        'tooltip':'Check for ePub formats that have <address> elements from a poor conversion with Word smart tags'}),
       ('check_epub_fonts',         {'name': 'Check embedded fonts',           'cat':'epub',     'sub_menu': 'Check ePub Style',     'group': 1, 'excludable': True,  'image': 'images/check_epub_fonts.png',          'tooltip':'Check for ePub formats with embedded fonts'}),
       ('check_epub_font_faces',    {'name': 'Check @font-face',               'cat':'epub',     'sub_menu': 'Check ePub Style',     'group': 1, 'excludable': True,  'image': 'images/check_epub_fonts.png',          'tooltip':'Check for ePub formats with CSS or html files that contain @font-face declarations'}),
       ('check_epub_xpgt',          {'name': 'Check Adobe .xpgt margins',      'cat':'epub',     'sub_menu': 'Check ePub Style',     'group': 2, 'excludable': True,  'image': 'images/check_epub_adobe.png',          'tooltip':'Check for ePub formats with an xpgt file with non-zero margins'}),
       ('check_epub_inline_xpgt',   {'name': 'Check Adobe inline .xpgt links', 'cat':'epub',     'sub_menu': 'Check ePub Style',     'group': 2, 'excludable': True,  'image': 'images/check_epub_adobe.png',          'tooltip':'Check for ePub formats that contain html pages with links to an xpgt file'}),
       ('check_epub_css_justify',   {'name': 'Check CSS non-justified',        'cat':'epub',     'sub_menu': 'Check ePub Style',     'group': 3, 'excludable': True,  'image': 'images/check_epub_css_justify.png',    'tooltip':'Check for ePub formats with CSS files that do not contain a text-align: justify style'}),
       ('check_epub_css_margins',   {'name': 'Check CSS book margins',         'cat':'epub',     'sub_menu': 'Check ePub Style',     'group': 3, 'excludable': True,  'image': 'images/check_epub_css_bmargins.png',   'tooltip':'Check for ePub formats with book level CSS margins conflicting with calibre Preferences'}),
       ('check_epub_css_no_margins',{'name': 'Check CSS no book margins',      'cat':'epub',     'sub_menu': 'Check ePub Style',     'group': 3, 'excludable': True,  'image': 'images/check_epub_css_nbmargins.png',  'tooltip':'Check for ePub formats that do not contain CSS book level margins'}),
       ('check_epub_inline_margins',{'name': 'Check inline @page margins',     'cat':'epub',     'sub_menu': 'Check ePub Style',     'group': 3, 'excludable': True,  'image': 'images/check_epub_css_pmargins.png',   'tooltip':'Check for ePub formats that contain @page CSS margins in each flow'}),
       ('check_epub_javascript',    {'name': 'Check javascript <script>',      'cat':'epub',     'sub_menu': 'Check ePub Style',     'group': 4, 'excludable': True,  'image': 'images/check_epub_javascript.png',     'tooltip':'Check for ePub formats that contain inline javascript <script> blocks'}),
       ('check_epub_smarten_punc',  {'name': 'Check smarten punctuation',      'cat':'epub',     'sub_menu': 'Check ePub Style',     'group': 4, 'excludable': True,  'image': 'images/check_epub_smarten_punc.png',   'tooltip':'Check for ePub formats that contain unsmartened punctuation'}),

       ('check_mobi_missing_ebok',  {'name': 'Check missing EBOK cdetype',     'cat':'mobi',     'sub_menu': 'Check Mobi',     'group': 0, 'excludable': True,  'image': 'images/check_mobi_asin.png',           'tooltip':'Check for MOBI/AZW/AZW3 formats missing the cdetype of EBOK required for a Kindle Fire'}),
       ('check_mobi_missing_asin',  {'name': 'Check missing ASIN identifier',  'cat':'mobi',     'sub_menu': 'Check Mobi',     'group': 0, 'excludable': True,  'image': 'images/check_mobi_asin.png',           'tooltip':'Check for MOBI/AZW/AZW3 formats missing an ASIN in EXTH 113 required for reading on a Kindle Fire'}),
       ('check_mobi_share_disabled',{'name': 'Check Twitter/Facebook disabled','cat':'mobi',     'sub_menu': 'Check Mobi',     'group': 0, 'excludable': True,  'image': 'images/check_mobi_asin.png',           'tooltip':'Check for MOBI/AZW/AZW3 formats missing an ASIN in both EXTH 113 and EXTH 504 to enable "share" features on Facebook or Twitter'}),
       ('check_mobi_clipping_limit',{'name': 'Check clipping limit',           'cat':'mobi',     'sub_menu': 'Check Mobi',     'group': 1, 'excludable': True,  'image': 'images/check_mobi_clipping.png',       'tooltip':'Check for MOBI/AZW/AZW3 formats that have a clipping limit specified by the publisher in EXTH header 401'}),

       ('check_title_sort',         {'name': 'Check title sort',               'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 1, 'excludable': True,  'image': 'images/check_book.png',                'tooltip':'Find books with an invalid title sort value'}),
       ('check_author_sort',        {'name': 'Check author sort',              'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 1, 'excludable': True,  'image': 'images/check_book.png',                'tooltip':'Find books with an invalid author sort value'}),
       ('check_isbn',               {'name': 'Check ISBN',                     'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 1, 'excludable': True,  'image': 'images/check_book.png',                'tooltip':'Find books with an invalid ISBN'}),
       ('check_pubdate',            {'name': 'Check pubdate',                  'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 1, 'excludable': True,  'image': 'images/check_book.png',                'tooltip':'Find books with an invalid pubdate where it is set to the timestamp date'}),
       ('check_dup_isbn',           {'name': 'Check duplicate ISBN',           'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 2, 'excludable': True,  'image': 'images/check_dup_isbn.png',            'tooltip':'Find books that have duplicate ISBN values'}),
       ('check_dup_series',         {'name': 'Check duplicate series',         'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 2, 'excludable': True,  'image': 'series.png',                           'tooltip':'Find books that have duplicate series values'}),
       ('check_series_gaps',        {'name': 'Check series gaps',              'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 2, 'excludable': True,  'image': 'series.png',                           'tooltip':'Find books that have gaps in their series index values'}),
       ('check_series_pubdate',     {'name': 'Check series pubdate order',     'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 2, 'excludable': True,  'image': 'series.png',                           'tooltip':'Find books that have gaps in their series index values'}),
       ('check_excess_tags',        {'name': 'Check excess tags',              'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 3, 'excludable': True,  'image': 'tags.png',                             'tooltip':'Find books with an excess number of tags'}),
       ('check_html_comments',      {'name': 'Check html comments',            'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 3, 'excludable': True,  'image': 'images/check_html.png',                'tooltip':'Find books which have comments html with style formatting embedded'}),
       ('check_no_html_comments',   {'name': 'Check no html comments',         'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 3, 'excludable': True,  'image': 'images/check_nohtml.png',              'tooltip':'Find books which have comments with no html tags at all'}),
       ('check_authors_commas',     {'name': 'Check authors with commas',      'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 4, 'excludable': True,  'image': 'images/check_comma.png',               'tooltip':'Find authors with commas in their name'}),
       ('check_authors_no_commas',  {'name': 'Check authors missing commas',   'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 4, 'excludable': True,  'image': 'images/check_nocomma.png',             'tooltip':'Find authors with no commas in their name'}),
       ('check_authors_case',       {'name': 'Check authors for case',         'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 4, 'excludable': True,  'image': 'images/check_titlecase.png',           'tooltip':'Find authors which are all uppercase or all lowercase'}),
       ('check_authors_non_alpha',  {'name': 'Check authors non alphabetic',   'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 4, 'excludable': True,  'image': 'user_profile.png',                     'tooltip':'Find authors with non-alphabetic characters such as semi-colons indicating cruft or incorrect separators'}),
       ('check_authors_non_ascii',  {'name': 'Check authors non ascii',        'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 4, 'excludable': True,  'image': 'user_profile.png',                     'tooltip':'Find authors with non-ascii names (e.g. with diatrics)'}),
       ('check_authors_initials',   {'name': 'Check authors initials',         'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 4, 'excludable': True,  'image': 'user_profile.png',                     'tooltip':'Find authors with initials that do not meet your preferred configuration'}),
       ('check_titles_series',      {'name': 'Check titles with series',       'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 5, 'excludable': True,  'image': 'images/check_titleseries.png',         'tooltip':'Find titles with possible series info in their name'}),
       ('check_title_case',         {'name': 'Check titles for title case',    'cat':'metadata', 'sub_menu': 'Check metadata', 'group': 5, 'excludable': True,  'image': 'images/check_titlecase.png',           'tooltip':'Find titles which are candidates to apply the titlecase function to'}),

       ('check_missing_title',      {'name': 'Check missing title',            'cat':'missing',  'sub_menu': 'Check missing',  'group': 1, 'excludable': False,  'image': 'images/check_book.png',               'tooltip':'Find books missing a title'}),
       ('check_missing_author',     {'name': 'Check missing author',           'cat':'missing',  'sub_menu': 'Check missing',  'group': 1, 'excludable': False,  'image': 'images/check_book.png',               'tooltip':'Find books missing authors'}),
       ('check_missing_isbn',       {'name': 'Check missing ISBN',             'cat':'missing',  'sub_menu': 'Check missing',  'group': 1, 'excludable': False,  'image': 'images/check_book.png',               'tooltip':'Find books missing an ISBN identifier'}),
       ('check_missing_pubdate',    {'name': 'Check missing pubdate',          'cat':'missing',  'sub_menu': 'Check missing',  'group': 1, 'excludable': False,  'image': 'images/check_book.png',               'tooltip':'Find books missing published date'}),
       ('check_missing_publisher',  {'name': 'Check missing publisher',        'cat':'missing',  'sub_menu': 'Check missing',  'group': 1, 'excludable': False,  'image': 'images/check_book.png',               'tooltip':'Find books missing publisher'}),
       ('check_missing_tags',       {'name': 'Check missing tags',             'cat':'missing',  'sub_menu': 'Check missing',  'group': 1, 'excludable': False,  'image': 'images/check_book.png',               'tooltip':'Find books missing tags'}),
       ('check_missing_rating',     {'name': 'Check missing rating',           'cat':'missing',  'sub_menu': 'Check missing',  'group': 1, 'excludable': False,  'image': 'images/check_book.png',               'tooltip':'Find books missing rating'}),
       ('check_missing_comments',   {'name': 'Check missing comments',         'cat':'missing',  'sub_menu': 'Check missing',  'group': 1, 'excludable': False,  'image': 'images/check_book.png',               'tooltip':'Find books missing comments'}),
       ('check_missing_languages',  {'name': 'Check missing languages',        'cat':'missing',  'sub_menu': 'Check missing',  'group': 1, 'excludable': False,  'image': 'images/check_book.png',               'tooltip':'Find books missing languages'}),
       ('check_missing_cover',      {'name': 'Check missing cover',            'cat':'missing',  'sub_menu': 'Check missing',  'group': 1, 'excludable': False,  'image': 'images/check_book.png',               'tooltip':'Find books missing a cover'}),
       ('check_missing_formats',    {'name': 'Check missing formats',          'cat':'missing',  'sub_menu': 'Check missing',  'group': 1, 'excludable': False,  'image': 'images/check_book.png',               'tooltip':'Find books missing formats'}),

       ('search_epub',              {'name': 'Search ePubs...',                'cat':'epub',     'sub_menu': '',               'group': 0, 'excludable': False, 'image': 'search.png',                           'tooltip':'Find ePub books with text matching your own regular expression'}),
       ])


PLUGIN_FIX_MENUS = OrderedDict([
       ('fix_swap_author_names',    {'name': 'Swap author FN LN <-> LN,FN',   'cat':'fix',  'group': 0, 'image': 'images/check_comma.png',         'tooltip':'For the selected book(s) swap author names between FN LN and LN, FN formats'}),
       ('fix_author_initials',      {'name': 'Reformat author initials',      'cat':'fix',  'group': 0, 'image': 'user_profile.png',               'tooltip':'For the selected book(s) reformat the author initials to your configured preference'}),
       ('fix_author_ascii',         {'name': 'Rename author to ascii',        'cat':'fix',  'group': 0, 'image': 'user_profile.png',               'tooltip':'For the selected book(s) rename the title to remove any accents and diatrics characters'}),
       ('check_fix_book_size',      {'name': 'Check and repair book sizes',   'cat':'fix',  'group': 1, 'image': 'images/check_file_size.png',     'tooltip':'Check and update file sizes for your books'}),
       ('check_fix_book_paths',     {'name': 'Check and rename book paths',   'cat':'fix',  'group': 1, 'image': 'images/fix_rename.png',          'tooltip':'Ensure book paths include commas if appropriate'}),
       ('cleanup_opf_files',        {'name': 'Cleanup .opf files/folders',    'cat':'fix',  'group': 2, 'image': 'images/fix_cleanup_folders.png', 'tooltip':'Delete orphaned opf/jpg files and remove empty folders'}),
       ('fix_mobi_asin',            {'name': 'Fix ASIN for Kindle Fire',      'cat':'fix',  'group': 3, 'image': 'images/fix_mobi_asin.png',       'tooltip':'For MOBI/AZW/AZW3 formats, assign the current amazon identifier (uuid if not present) as an ASIN to EXTH 113 and 504 fields'}),
       ])

# This is where all preferences for this plugin will be stored
plugin_prefs = JSONConfig('plugins/Quality Check')

# Set defaults
plugin_prefs.defaults[STORE_OPTIONS] = DEFAULT_STORE_VALUES


def migrate_library_config_if_required(db, library_config):
    schema_version = library_config.get(KEY_SCHEMA_VERSION, 0)
    if schema_version == DEFAULT_SCHEMA_VERSION:
        return
    # We have changes to be made - mark schema as updated
    library_config[KEY_SCHEMA_VERSION] = DEFAULT_SCHEMA_VERSION

    # Any migration code in future will exist in here.
    if schema_version < 1.9:
        # Make sure that any exclusions for checks which aren't allowed them are removed.
        exclusions_map = library_config.get(KEY_EXCLUSIONS_BY_CHECK, {})
        for excl_key in list(exclusions_map.keys()):
            if excl_key.startswith('check_missing_'):
                del exclusions_map[excl_key]

    set_library_config(db, library_config)


def get_library_config(db):
    library_id = get_library_uuid(db)
    library_config = None
    # Check whether this is a reading list needing to be migrated from json into database
    if 'Libraries' in plugin_prefs:
        libraries = plugin_prefs['Libraries']
        if library_id in libraries:
            # We will migrate this below
            library_config = libraries[library_id]
            # Cleanup from json file so we don't ever do this again
            del libraries[library_id]
            if len(libraries) == 0:
                # We have migrated the last library for this user
                del plugin_prefs['Libraries']
            else:
                plugin_prefs['Libraries'] = libraries

    if library_config is None:
        library_config = db.prefs.get_namespaced(PREFS_NAMESPACE, PREFS_KEY_SETTINGS,
                                                 copy.deepcopy(DEFAULT_LIBRARY_VALUES))
    migrate_library_config_if_required(db, library_config)
    return library_config

def set_library_config(db, library_config):
    db.prefs.set_namespaced(PREFS_NAMESPACE, PREFS_KEY_SETTINGS, library_config)

def get_excluded_books(db, menu_key):
    library_config = get_library_config(db)
    exclusions_map = library_config[KEY_EXCLUSIONS_BY_CHECK]
    exclusions = exclusions_map.get(menu_key, [])
    return exclusions

def get_valid_excluded_books(db, menu_key):
    book_ids = get_excluded_books(db, menu_key)
    valid_book_ids = [i for i in book_ids if db.data.has_id(i)]
    if len(book_ids) != len(valid_book_ids):
        set_excluded_books(db, menu_key, book_ids)
    return valid_book_ids

def set_excluded_books(db, menu_key, book_ids):
    library_config = get_library_config(db)
    exclusions_map = library_config[KEY_EXCLUSIONS_BY_CHECK]
    exclusions_map[menu_key] = book_ids
    set_library_config(db, library_config)


class VisibleMenuListWidget(QListWidget):
    def __init__(self, parent=None):
        QListWidget.__init__(self, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.populate()

    def populate(self):
        self.clear()
        hidden_prefs = plugin_prefs[STORE_OPTIONS].get(KEY_HIDDEN_MENUS, [])
        for key, value in PLUGIN_MENUS.iteritems():
            name = value['name']
            sub_menu = value['sub_menu']
            if sub_menu:
                name = sub_menu + ' -> ' + name
            item = QListWidgetItem(name, self)
            item.setIcon(get_icon(value['image']))
            item.setData(Qt.UserRole, key)
            if key in hidden_prefs:
                item.setCheckState(Qt.Unchecked)
            else:
                item.setCheckState(Qt.Checked)
            self.addItem(item)

    def get_hidden_menus(self):
        hidden_menus = []
        for x in xrange(self.count()):
            item = self.item(x)
            if item.checkState() == Qt.Unchecked:
                key = unicode(convert_qvariant(item.data(Qt.UserRole))).strip()
                hidden_menus.append(key)
        return hidden_menus


class ConfigWidget(QWidget):

    def __init__(self, plugin_action, all_tags):
        QWidget.__init__(self)
        self.plugin_action = plugin_action
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        c = plugin_prefs[STORE_OPTIONS]
        tags_groupbox = QGroupBox('Check excess tags Options')
        layout.addWidget(tags_groupbox)
        tags_layout = QGridLayout()
        tags_groupbox.setLayout(tags_layout)

        max_label = QLabel('Maximum tags:', self)
        max_label.setToolTip('Books with more than this value will be displayed')
        tags_layout.addWidget(max_label, 0, 0, 1, 1)
        self.max_tags_spin = QtGui.QSpinBox(self)
        self.max_tags_spin.setMinimum(0)
        self.max_tags_spin.setMaximum(100)
        self.max_tags_spin.setProperty('value', c.get(KEY_MAX_TAGS, 5))
        tags_layout.addWidget(self.max_tags_spin, 0, 1, 1, 1)

        exclude_label = QLabel('Exclude tags:', self)
        exclude_label.setToolTip('Exclude these tags from when counting the tags for each book')
        tags_layout.addWidget(exclude_label, 1, 0, 1, 1)
        self.exclude_tags = EditWithComplete(self)
        self.exclude_tags.set_add_separator(True)
        self.exclude_tags.update_items_cache(all_tags)
        self.exclude_tags.setText(', '.join(c.get(KEY_MAX_TAG_EXCLUSIONS, [])))
        tags_layout.addWidget(self.exclude_tags, 1, 1, 1, 2)
        tags_layout.setColumnStretch(2, 1)

        other_groupbox = QGroupBox('Other Options')
        layout.addWidget(other_groupbox)
        other_layout = QGridLayout()
        other_groupbox.setLayout(other_layout)

        initials_label = QLabel('Author initials format:', self)
        initials_label.setToolTip('For use with the "Check Author initials" option, set your preferred format')
        other_layout.addWidget(initials_label, 0, 0, 1, 1)
        initials_map = OrderedDict((k,k) for k in AUTHOR_INITIALS_MODES)
        initials_mode = c.get(KEY_AUTHOR_INITIALS_MODE, AUTHOR_INITIALS_MODES[0])
        self.initials_combo = KeyValueComboBox(self, initials_map, initials_mode)
        other_layout.addWidget(self.initials_combo, 0, 1, 1, 1)
        other_layout.setColumnStretch(2, 1)

        menus_groupbox = QGroupBox('Visible Menus')
        layout.addWidget(menus_groupbox)
        menus_layout = QVBoxLayout()
        menus_groupbox.setLayout(menus_layout)
        self.visible_menus_list = VisibleMenuListWidget(self)
        menus_layout.addWidget(self.visible_menus_list)
        self.orig_hidden_menus = self.visible_menus_list.get_hidden_menus()

        keyboard_shortcuts_button = QPushButton('Keyboard shortcuts...', self)
        keyboard_shortcuts_button.setToolTip(_(
                    'Edit the keyboard shortcuts associated with this plugin'))
        keyboard_shortcuts_button.clicked.connect(self.edit_shortcuts)
        layout.addWidget(keyboard_shortcuts_button)

        view_prefs_button = QPushButton('&View library preferences...', self)
        view_prefs_button.setToolTip(_(
                    'View data stored in the library database for this plugin'))
        view_prefs_button.clicked.connect(self.view_prefs)
        layout.addWidget(view_prefs_button)

    def save_settings(self):
        new_prefs = {}
        new_prefs[KEY_MAX_TAGS] = int(unicode(self.max_tags_spin.value()))
        exclude_tag_text = unicode(self.exclude_tags.text()).strip()
        if exclude_tag_text.endswith(','):
            exclude_tag_text = exclude_tag_text[:-1]
        new_prefs[KEY_MAX_TAG_EXCLUSIONS] = [t.strip() for t in exclude_tag_text.split(',')]
        new_prefs[KEY_AUTHOR_INITIALS_MODE] = self.initials_combo.selected_key()
        new_prefs[KEY_SEARCH_SCOPE] = plugin_prefs[STORE_OPTIONS].get(KEY_SEARCH_SCOPE, SCOPE_LIBRARY)

        new_prefs[KEY_HIDDEN_MENUS] = self.visible_menus_list.get_hidden_menus()
        # For each menu that was visible but now is not, we need to unregister any
        # keyboard shortcut associated with that action.
        menus_changed = False
        kb = self.plugin_action.gui.keyboard
        for menu_key in new_prefs[KEY_HIDDEN_MENUS]:
            if menu_key not in self.orig_hidden_menus:
                unique_name = menu_action_unique_name(self.plugin_action, menu_key)
                if unique_name in kb.shortcuts:
                    kb.unregister_shortcut(unique_name)
                    menus_changed = True
        if menus_changed:
            self.plugin_action.gui.keyboard.finalize()

        plugin_prefs[STORE_OPTIONS] = new_prefs

    def edit_shortcuts(self):
        d = KeyboardConfigDialog(self.plugin_action.gui, self.plugin_action.action_spec[0])
        if d.exec_() == d.Accepted:
            self.plugin_action.gui.keyboard.finalize()

    def view_prefs(self):
        d = PrefsViewerDialog(self.plugin_action.gui, PREFS_NAMESPACE)
        d.exec_()
