#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
'''Allows user to control general plugin settings'''

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2016, Samreen Zarroug, Anthony Toole, & Alex Mayer'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QButtonGroup, QRadioButton, QCheckBox
from PyQt5.Qt import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QFrame

from calibre.gui2 import error_dialog
from calibre_plugins.xray_creator import __prefs__

class ConfigWidget(QWidget):
    '''Creates general preferences dialog'''
    def __init__(self):
        QWidget.__init__(self)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self._initialize_general(layout)
        self._intialize_file_settings(layout)
        self._initialize_file_type_settings(layout)

    def _initialize_general(self, layout):
        '''Initialize general settings'''
        self._settings = {}
        self._settings['send_to_device'] = QCheckBox('Send files to device if connected')
        self._settings['send_to_device'].setChecked(__prefs__['send_to_device'])
        layout.addWidget(self._settings['send_to_device'])

        self._settings['create_files_when_sending'] = QCheckBox('Create files for books that don\'t '
                                                                'already have them when sending to device')
        self._settings['create_files_when_sending'].setChecked(__prefs__['create_files_when_sending'])
        layout.addWidget(self._settings['create_files_when_sending'])

        self._settings['expand_aliases'] = QCheckBox('Auto associate split aliases [?]')
        self._settings['expand_aliases'].setChecked(__prefs__['expand_aliases'])
        expand_alias_explanation = ('When enabled, this will split aliases up further.\n\n'
                                    'Example: If a character on goodreads named "Vin" has a'
                                    'Goodreads alias of "Valette\nRenoux",  this option will '
                                    'add "Valette" and "Renoux" as aliases. You may not want\n'
                                    'this in cases such as "Timothy Cratchit" who has a '
                                    'Goodreads alias of "Tiny Tim".\nHaving this feature on '
                                    'would add "Tiny", and "Tim" as aliases which is not valid.')
        self._settings['expand_aliases'].setWhatsThis(expand_alias_explanation)
        self._settings['expand_aliases'].setToolTip(expand_alias_explanation)
        layout.addWidget(self._settings['expand_aliases'])

        self._settings['overwrite_when_creating'] = QCheckBox('Overwrite local files when creating files')
        self._settings['overwrite_when_creating'].setChecked(__prefs__['overwrite_when_creating'])
        layout.addWidget(self._settings['overwrite_when_creating'])

        self._settings['overwrite_when_sending'] = QCheckBox('Overwrite files on device when sending files')
        self._settings['overwrite_when_sending'].setChecked(__prefs__['overwrite_when_sending'])
        layout.addWidget(self._settings['overwrite_when_sending'])

    def _intialize_file_settings(self, layout):
        '''Initialize file creation/sending settings'''
        separator_a = QFrame()
        separator_a.setFrameStyle(QFrame.HLine)
        separator_a.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator_a)

        files_to_create = QGroupBox()
        files_to_create.setTitle('Files to create/send')
        files_to_create.setLayout(QGridLayout(files_to_create))

        self._settings['create_send_xray'] = QCheckBox('X-Ray')
        self._settings['create_send_xray'].setChecked(__prefs__['create_send_xray'])
        files_to_create.layout().addWidget(self._settings['create_send_xray'], 0, 0)

        self._settings['create_send_author_profile'] = QCheckBox('Author Profile')
        self._settings['create_send_author_profile'].setChecked(__prefs__['create_send_author_profile'])
        files_to_create.layout().addWidget(self._settings['create_send_author_profile'], 1, 0)

        self._settings['create_send_start_actions'] = QCheckBox('Start Actions')
        self._settings['create_send_start_actions'].setChecked(__prefs__['create_send_start_actions'])
        files_to_create.layout().addWidget(self._settings['create_send_start_actions'], 0, 1)

        self._settings['create_send_end_actions'] = QCheckBox('End Actions')
        self._settings['create_send_end_actions'].setChecked(__prefs__['create_send_end_actions'])
        files_to_create.layout().addWidget(self._settings['create_send_end_actions'], 1, 1)
        layout.addWidget(files_to_create)

    def _initialize_file_type_settings(self, layout):
        '''Initialize file creation/sending type settings'''
        separator_b = QFrame()
        separator_b.setFrameStyle(QFrame.HLine)
        separator_b.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator_b)

        book_types_to_create = QGroupBox()
        book_types_to_create.setTitle('Book types to create files for:')
        book_types_to_create.setLayout(QHBoxLayout(book_types_to_create))

        self._settings['mobi'] = QCheckBox('MOBI')
        self._settings['mobi'].setChecked('mobi' in __prefs__['formats'])
        book_types_to_create.layout().addWidget(self._settings['mobi'])

        self._settings['azw3'] = QCheckBox('AZW3')
        self._settings['azw3'].setChecked('azw3' in __prefs__['formats'])
        book_types_to_create.layout().addWidget(self._settings['azw3'])
        layout.addWidget(book_types_to_create)

        file_preference_layout = QGroupBox()
        file_preference_layout.setTitle('If device has both (mobi and azw3) formats, prefer:')
        file_preference_layout.setLayout(QHBoxLayout(file_preference_layout))

        file_preference_group = QButtonGroup()
        self._settings['file_preference_mobi'] = QRadioButton('MOBI')
        self._settings['file_preference_mobi'].setChecked(__prefs__['file_preference'] == 'mobi')
        file_preference_group.addButton(self._settings['file_preference_mobi'])
        file_preference_layout.layout().addWidget(self._settings['file_preference_mobi'])

        self._settings['file_preference_azw3'] = QRadioButton('AZW3')
        self._settings['file_preference_azw3'].setChecked(__prefs__['file_preference'] == 'azw3')
        file_preference_group.addButton(self._settings['file_preference_azw3'])
        file_preference_layout.layout().addWidget(self._settings['file_preference_azw3'])
        layout.addWidget(file_preference_layout)

    def validate(self):
        '''Validates current settings; Errors if there's a problem'''
        if (not self._settings['create_send_xray'].isChecked()
                and not self._settings['create_send_author_profile'].isChecked()
                and not self._settings['create_send_start_actions'].isChecked()
                and not self._settings['create_send_end_actions'].isChecked()):
            error_dialog(self, 'Invalid preferences.', 'You have chosen no files to create/send.', show=True)
            return False

        if not self._settings['mobi'].isChecked() and not self._settings['azw3'].isChecked():
            error_dialog(self, 'Invalid preferences.', 'You have chosen no book formats to create files for.', show=True)
            return False
        return True

    def save_settings(self):
        '''Saves current settings into preferences json file'''
        special = ['file_preference_azw3', 'file_preference_mobi', 'mobi', 'azw3']
        for setting, value in self._settings.items():
            if setting not in special:
                __prefs__[setting] = value.isChecked()

        if self._settings['file_preference_mobi'].isChecked():
            __prefs__['file_preference'] = 'mobi'
        elif self._settings['file_preference_azw3'].isChecked():
            __prefs__['file_preference'] = 'azw3'

        __prefs__['formats'] = [fmt for fmt in ['mobi', 'azw3'] if self._settings[fmt].isChecked()]
