#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Grant Drake <grant.drake@gmail.com>'
__docformat__ = 'restructuredtext en'

import copy
from functools import partial
try:
    from PyQt5 import Qt as QtGui
    from PyQt5.Qt import (QTableWidgetItem, QVBoxLayout, Qt, QGroupBox, QTableWidget,
                          QCheckBox, QAbstractItemView, QHBoxLayout, QIcon,
                          QInputDialog)
except ImportError:
    from PyQt4 import QtGui
    from PyQt4.Qt import (QTableWidgetItem, QVBoxLayout, Qt, QGroupBox, QTableWidget,
                          QCheckBox, QAbstractItemView, QHBoxLayout, QIcon,
                          QInputDialog)
from calibre.gui2 import get_current_db, question_dialog, error_dialog
from calibre.gui2.complete2 import EditWithComplete
from calibre.gui2.metadata.config import ConfigWidget as DefaultConfigWidget
from calibre.utils.config import JSONConfig

from calibre_plugins.goodreads.common_utils import ReadOnlyTableWidgetItem

STORE_NAME = 'Options'
KEY_GET_ALL_AUTHORS = 'getAllAuthors'
KEY_GET_EDITIONS = 'getEditions'
KEY_GENRE_MAPPINGS = 'genreMappings'

DEFAULT_GENRE_MAPPINGS = {
                'Anthologies': ['Anthologies'],
                'Adventure': ['Adventure'],
                'Adult Fiction': ['Adult'],
                'Adult': ['Adult'],
                'Art': ['Art'],
                'Biography': ['Biography'],
                'Biography Memoir': ['Biography'],
                'Business': ['Business'],
                'Chick-lit': ['Chick-lit'],
                'Childrens': ['Childrens'],
                'Classics': ['Classics'],
                'Comics': ['Comics'],
                'Graphic Novels Comics': ['Comics'],
                'Contemporary': ['Contemporary'],
                'Cookbooks': ['Cookbooks'],
                'Crime': ['Crime'],
                'Fantasy': ['Fantasy'],
                'Feminism': ['Feminism'],
                'Gardening': ['Gardening'],
                'Gay': ['Gay'],
                'Glbt': ['Gay'],
                'Health': ['Health'],
                'History': ['History'],
                'Historical Fiction': ['Historical'],
                'Horror': ['Horror'],
                'Comedy': ['Humour'],
                'Humor': ['Humour'],
                'Health': ['Health'],
                'Inspirational': ['Inspirational'],
                'Sequential Art > Manga': ['Manga'],
                'Modern': ['Modern'],
                'Music': ['Music'],
                'Mystery': ['Mystery'],
                'Non Fiction': ['Non-Fiction'],
                'Paranormal': ['Paranormal'],
                'Religion': ['Religion'],
                'Philosophy': ['Philosophy'],
                'Politics': ['Politics'],
                'Poetry': ['Poetry'],
                'Psychology': ['Psychology'],
                'Reference': ['Reference'],
                'Romance': ['Romance'],
                'Science': ['Science'],
                'Science Fiction': ['Science Fiction'],
                'Science Fiction Fantasy': ['Science Fiction', 'Fantasy'],
                'Self Help': ['Self Help'],
                'Sociology': ['Sociology'],
                'Spirituality': ['Spirituality'],
                'Suspense': ['Suspense'],
                'Thriller': ['Thriller'],
                'Travel': ['Travel'],
                'Paranormal > Vampires': ['Vampires'],
                'War': ['War'],
                'Western': ['Western'],
                'Language > Writing': ['Writing'],
                'Writing > Essays': ['Writing'],
                'Young Adult': ['Young Adult'],
                }

DEFAULT_STORE_VALUES = {
    KEY_GET_EDITIONS: False,
    KEY_GET_ALL_AUTHORS: False,
    KEY_GENRE_MAPPINGS: copy.deepcopy(DEFAULT_GENRE_MAPPINGS)
}

# This is where all preferences for this plugin will be stored
plugin_prefs = JSONConfig('plugins/Goodreads')

# Set defaults
plugin_prefs.defaults[STORE_NAME] = DEFAULT_STORE_VALUES


class GenreTagMappingsTableWidget(QTableWidget):
    def __init__(self, parent, all_tags):
        QTableWidget.__init__(self, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tags_values = all_tags

    def populate_table(self, tag_mappings):
        self.clear()
        self.setAlternatingRowColors(True)
        self.setRowCount(len(tag_mappings))
        header_labels = ['Goodreads Genre', 'Maps to Calibre Tag(s)']
        self.setColumnCount(len(header_labels))
        self.setHorizontalHeaderLabels(header_labels)
        self.verticalHeader().setDefaultSectionSize(24)
        self.horizontalHeader().setStretchLastSection(True)

        for row, genre in enumerate(sorted(tag_mappings.keys(), key=lambda s: (s.lower(), s))):
            self.populate_table_row(row, genre, sorted(tag_mappings[genre]))

        self.resizeColumnToContents(0)
        self.set_minimum_column_width(0, 200)
        self.setSortingEnabled(False)
        if len(tag_mappings) > 0:
            self.selectRow(0)

    def set_minimum_column_width(self, col, minimum):
        if self.columnWidth(col) < minimum:
            self.setColumnWidth(col, minimum)

    def populate_table_row(self, row, genre, tags):
        self.setItem(row, 0, ReadOnlyTableWidgetItem(genre))
        tags_value = ', '.join(tags)
        # Add a widget under the cell just for sorting purposes
        self.setItem(row, 1, QTableWidgetItem(tags_value))
        self.setCellWidget(row, 1, self.create_tags_edit(tags_value, row))

    def create_tags_edit(self, value, row):
        tags_edit = EditWithComplete(self)
        tags_edit.set_add_separator(False)
        tags_edit.update_items_cache(self.tags_values)
        tags_edit.setText(value)
#        tags_edit.editingFinished.connect(partial(self.tags_editing_finished, row, tags_edit))
        return tags_edit

    def tags_editing_finished(self, row, tags_edit):
        # Update our underlying widget for sorting
        self.item(row, 1).setText(tags_edit.text())

    def get_data(self):
        tag_mappings = {}
        for row in range(self.rowCount()):
            genre = unicode(self.item(row, 0).text()).strip()
            tags_text = unicode(self.cellWidget(row, 1).text()).strip()
            tag_values = tags_text.split(',')
            tags_list = []
            for tag in tag_values:
                if len(tag.strip()) > 0:
                    tags_list.append(tag.strip())
            tag_mappings[genre] = tags_list
        return tag_mappings

    def select_genre(self, genre_name):
        for row in range(self.rowCount()):
            if unicode(self.item(row, 0).text()) == genre_name:
                self.setCurrentCell(row, 1)
                return

    def get_selected_genre(self):
        if self.currentRow() >= 0:
            return unicode(self.item(self.currentRow(), 0).text())


class ConfigWidget(DefaultConfigWidget):

    def __init__(self, plugin):
        DefaultConfigWidget.__init__(self, plugin)
        c = plugin_prefs[STORE_NAME]
        all_tags = get_current_db().all_tags()

        self.gb.setMaximumHeight(80)
        genre_group_box = QGroupBox('Goodreads genre to calibre tag mappings', self)
        self.l.addWidget(genre_group_box, self.l.rowCount(), 0, 1, 2)
        genre_group_box_layout = QVBoxLayout()
        genre_group_box.setLayout(genre_group_box_layout)

        tags_layout = QHBoxLayout()
        genre_group_box_layout.addLayout(tags_layout)

        self.edit_table = GenreTagMappingsTableWidget(self, all_tags)
        tags_layout.addWidget(self.edit_table)
        button_layout = QVBoxLayout()
        tags_layout.addLayout(button_layout)
        add_mapping_button = QtGui.QToolButton(self)
        add_mapping_button.setToolTip('Add genre mapping')
        add_mapping_button.setIcon(QIcon(I('plus.png')))
        add_mapping_button.clicked.connect(self.add_mapping)
        button_layout.addWidget(add_mapping_button)
        spacerItem1 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        button_layout.addItem(spacerItem1)
        remove_mapping_button = QtGui.QToolButton(self)
        remove_mapping_button.setToolTip('Delete genre mapping')
        remove_mapping_button.setIcon(QIcon(I('minus.png')))
        remove_mapping_button.clicked.connect(self.delete_mapping)
        button_layout.addWidget(remove_mapping_button)
        spacerItem3 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        button_layout.addItem(spacerItem3)
        rename_genre_button = QtGui.QToolButton(self)
        rename_genre_button.setToolTip('Rename Goodreads genre')
        rename_genre_button.setIcon(QIcon(I('edit-undo.png')))
        rename_genre_button.clicked.connect(self.rename_genre)
        button_layout.addWidget(rename_genre_button)
        spacerItem2 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        button_layout.addItem(spacerItem2)
        reset_defaults_button = QtGui.QToolButton(self)
        reset_defaults_button.setToolTip('Reset to plugin default mappings')
        reset_defaults_button.setIcon(QIcon(I('clear_left.png')))
        reset_defaults_button.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_defaults_button)
        self.l.setRowStretch(self.l.rowCount()-1, 2)

        other_group_box = QGroupBox('Other options', self)
        self.l.addWidget(other_group_box, self.l.rowCount(), 0, 1, 2)
        other_group_box_layout = QVBoxLayout()
        other_group_box.setLayout(other_group_box_layout)

        self.get_editions_checkbox = QCheckBox('Scan multiple editions for title/author searches (slower)', self)
        self.get_editions_checkbox.setToolTip('When checked will perform an additional search to scan the top ranked\n'
                                              'Goodreads editions (if available) to exclude audiobook editions.\n'
                                              'Without this enabled you will get a faster search, using the "best".\n'
                                              'edition ranked by Goodreads which can in some cases be an audiobook.')
        self.get_editions_checkbox.setChecked(c[KEY_GET_EDITIONS])
        other_group_box_layout.addWidget(self.get_editions_checkbox)
        self.all_authors_checkbox = QCheckBox('Get all contributing authors (e.g. illustrators, series editors etc)', self)
        self.all_authors_checkbox.setToolTip('Goodreads for some books will list all of the contributing authors and\n'
                                              'the type of contribution like (Editor), (Illustrator) etc.\n\n'
                                              'When this option is checked, all contributing authors are retrieved.\n\n'
                                              'When unchecked (default) only the primary author(s) are returned which\n'
                                              'are those that either have no contribution type specified, or have the\n'
                                              'value of (Goodreads Author).\n\n'
                                              'If there is no primary author then only those with the same contribution\n'
                                              'type as the first author are returned.\n'
                                              'e.g. "A, B (Illustrator)" will return author A\n'
                                              'e.g. "A (Goodreads Author)" will return author A\n'
                                              'e.g. "A (Editor), B (Editor), C (Illustrator)" will return authors A & B\n'
                                              'e.g. "A (Editor), B (Series Editor)" will return author A\n')
        self.all_authors_checkbox.setChecked(c[KEY_GET_ALL_AUTHORS])
        other_group_box_layout.addWidget(self.all_authors_checkbox)

        self.edit_table.populate_table(c[KEY_GENRE_MAPPINGS])

    def commit(self):
        DefaultConfigWidget.commit(self)
        new_prefs = {}
        new_prefs[KEY_GET_EDITIONS] = self.get_editions_checkbox.checkState() == Qt.Checked
        new_prefs[KEY_GET_ALL_AUTHORS] = self.all_authors_checkbox.checkState() == Qt.Checked
        new_prefs[KEY_GENRE_MAPPINGS] = self.edit_table.get_data()
        plugin_prefs[STORE_NAME] = new_prefs

    def add_mapping(self):
        new_genre_name, ok = QInputDialog.getText(self, 'Add new mapping',
                    'Enter a Goodreads genre name to create a mapping for:', text='')
        if not ok:
            # Operation cancelled
            return
        new_genre_name = unicode(new_genre_name).strip()
        if not new_genre_name:
            return
        # Verify it does not clash with any other mappings in the list
        data = self.edit_table.get_data()
        for genre_name in data.keys():
            if genre_name.lower() == new_genre_name.lower():
                return error_dialog(self, 'Add Failed', 'A genre with the same name already exists', show=True)
        data[new_genre_name] = []
        self.edit_table.populate_table(data)
        self.edit_table.select_genre(new_genre_name)

    def delete_mapping(self):
        if not self.edit_table.selectionModel().hasSelection():
            return
        if not question_dialog(self, _('Are you sure?'), '<p>'+
                'Are you sure you want to delete the selected genre mappings?',
                show_copy_button=False):
            return
        for row in reversed(sorted(self.edit_table.selectionModel().selectedRows())):
            self.edit_table.removeRow(row.row())

    def rename_genre(self):
        selected_genre = self.edit_table.get_selected_genre()
        if not selected_genre:
            return
        new_genre_name, ok = QInputDialog.getText(self, 'Add new mapping',
                    'Enter a Goodreads genre name to create a mapping for:', text=selected_genre)
        if not ok:
            # Operation cancelled
            return
        new_genre_name = unicode(new_genre_name).strip()
        if not new_genre_name or new_genre_name == selected_genre:
            return
        data = self.edit_table.get_data()
        if new_genre_name.lower() != selected_genre.lower():
            # Verify it does not clash with any other mappings in the list
            for genre_name in data.keys():
                if genre_name.lower() == new_genre_name.lower():
                    return error_dialog(self, 'Rename Failed', 'A genre with the same name already exists', show=True)
        data[new_genre_name] = data[selected_genre]
        del data[selected_genre]
        self.edit_table.populate_table(data)
        self.edit_table.select_genre(new_genre_name)

    def reset_to_defaults(self):
        if not question_dialog(self, _('Are you sure?'), '<p>'+
                'Are you sure you want to reset to the plugin default genre mappings?',
                show_copy_button=False):
            return
        self.edit_table.populate_table(DEFAULT_GENRE_MAPPINGS)

