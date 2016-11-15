#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
'''Allows user to control general plugin settings'''

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2016, Samreen Zarroug, Anthony Toole, & Alex Mayer'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QFrame
from PyQt5.Qt import QButtonGroup, QRadioButton, QCheckBox

from calibre.utils.config import JSONConfig
from calibre.gui2 import error_dialog

__prefs__ = JSONConfig('plugins/xray_creator')

# Set defaults
__prefs__.defaults['send_to_device'] = True
__prefs__.defaults['create_files_when_sending'] = True
__prefs__.defaults['expand_aliases'] = True
__prefs__.defaults['overwrite_when_creating'] = False
__prefs__.defaults['overwrite_when_sending'] = False
__prefs__.defaults['create_send_xray'] = True
__prefs__.defaults['create_send_author_profile'] = False
__prefs__.defaults['create_send_start_actions'] = False
__prefs__.defaults['create_send_end_actions'] = False
__prefs__.defaults['file_preference'] = 'mobi'
__prefs__.defaults['mobi'] = True
__prefs__.defaults['azw3'] = True
__prefs__.defaults['tld'] = None

class ConfigWidget(QWidget):
    '''Creates general preferences dialog'''
    def __init__(self):
        QWidget.__init__(self)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.send_to_device = QCheckBox('Send x-ray to device if connected')
        self.send_to_device.setChecked(__prefs__['send_to_device'])
        self.layout.addWidget(self.send_to_device)

        self.create_files_when_sending = QCheckBox('Create x-ray for files that don\'t '
                                                   'already have them when sending to device')
        self.create_files_when_sending.setChecked(__prefs__['create_files_when_sending'])
        self.layout.addWidget(self.create_files_when_sending)

        self.expand_aliases = QCheckBox('Auto associate split aliases [?]')
        self.expand_aliases.setChecked(__prefs__['expand_aliases'])
        expand_alias_explanation = ('When enabled, this will split aliases up further.\n\n'
                                    'Example: If a character on goodreads named "Vin" has a'
                                    'Goodreads alias of "Valette\nRenoux",  this option will '
                                    'add "Valette" and "Renoux" as aliases. You may not want\n'
                                    'this in cases such as "Timothy Cratchit" who has a '
                                    'Goodreads alias of "Tiny Tim".\nHaving this feature on '
                                    'would add "Tiny", and "Tim" as aliases which is not valid.')
        self.expand_aliases.setWhatsThis(expand_alias_explanation)
        self.expand_aliases.setToolTip(expand_alias_explanation)
        self.layout.addWidget(self.expand_aliases)

        self.overwrite_when_creating = QCheckBox('Overwrite local files that already exist when creating files')
        self.overwrite_when_creating.setChecked(__prefs__['overwrite_when_creating'])
        self.layout.addWidget(self.overwrite_when_creating)

        self.overwrite_when_sending = QCheckBox('Overwrite files on device that already exist when sending files')
        self.overwrite_when_sending.setChecked(__prefs__['overwrite_when_sending'])
        self.layout.addWidget(self.overwrite_when_sending)

        self.separator_a = QFrame()
        self.separator_a.setFrameStyle(QFrame.HLine)
        self.separator_a.setFrameShadow(QFrame.Sunken)
        self.layout.addWidget(self.separator_a)

        self.files_to_create = QGroupBox()
        self.files_to_create.setTitle('Files to create/send')
        self.files_to_create.setLayout(QGridLayout(self.files_to_create))

        self.create_send_xray = QCheckBox('X-Ray')
        self.create_send_xray.setChecked(__prefs__['create_send_xray'])
        self.files_to_create.layout().addWidget(self.create_send_xray, 0, 0)

        self.create_send_author_profile = QCheckBox('Author Profile')
        self.create_send_author_profile.setChecked(__prefs__['create_send_author_profile'])
        self.files_to_create.layout().addWidget(self.create_send_author_profile, 1, 0)

        self.create_send_start_actions = QCheckBox('Start Actions')
        self.create_send_start_actions.setChecked(__prefs__['create_send_start_actions'])
        self.files_to_create.layout().addWidget(self.create_send_start_actions, 0, 1)

        self.create_send_end_actions = QCheckBox('End Actions')
        self.create_send_end_actions.setChecked(__prefs__['create_send_end_actions'])
        self.files_to_create.layout().addWidget(self.create_send_end_actions, 1, 1)
        self.layout.addWidget(self.files_to_create)

        self.separator_b = QFrame()
        self.separator_b.setFrameStyle(QFrame.HLine)
        self.separator_b.setFrameShadow(QFrame.Sunken)
        self.layout.addWidget(self.separator_b)

        self.book_types_to_create = QGroupBox()
        self.book_types_to_create.setTitle('Book types to create files for:')
        self.book_types_to_create.setLayout(QHBoxLayout(self.book_types_to_create))

        self.mobi = QCheckBox('MOBI')
        self.mobi.setChecked(__prefs__['mobi'])
        self.book_types_to_create.layout().addWidget(self.mobi)

        self.azw3 = QCheckBox('AZW3')
        self.azw3.setChecked(__prefs__['azw3'])
        self.book_types_to_create.layout().addWidget(self.azw3)
        self.layout.addWidget(self.book_types_to_create)

        self.file_preference_layout = QGroupBox()
        self.file_preference_layout.setTitle('If device has both (mobi and azw3) formats, prefer:')
        self.file_preference_layout.setLayout(QHBoxLayout(self.file_preference_layout))

        self.file_preference_group = QButtonGroup()
        self.file_preference_mobi = QRadioButton('MOBI')
        self.file_preference_mobi.setChecked(__prefs__['file_preference'] == 'mobi')
        self.file_preference_group.addButton(self.file_preference_mobi)
        self.file_preference_layout.layout().addWidget(self.file_preference_mobi)

        self.file_preference_azw3 = QRadioButton('AZW3')
        self.file_preference_azw3.setChecked(__prefs__['file_preference'] == 'azw3')
        self.file_preference_group.addButton(self.file_preference_azw3)
        self.file_preference_layout.layout().addWidget(self.file_preference_azw3)
        self.layout.addWidget(self.file_preference_layout)

    def validate(self):
        '''Validates current settings; Errors if there's a problem'''
        if (not self.create_send_xray.isChecked() and not self.create_send_author_profile.isChecked()
                and not self.create_send_start_actions.isChecked() and not self.create_send_end_actions.isChecked()):
            error_dialog(self, 'Invalid preferences.', 'You have chosen no files to create/send.', show=True)
            return False

        if not self.mobi.isChecked() and not self.azw3.isChecked():
            error_dialog(self, 'Invalid preferences.', 'You have chosen no book formats to create files for.', show=True)
            return False
        return True

    def save_settings(self):
        '''Saves current settings into preferences json file'''
        __prefs__['send_to_device'] = self.send_to_device.isChecked()
        __prefs__['create_files_when_sending'] = self.create_files_when_sending.isChecked()
        __prefs__['expand_aliases'] = self.expand_aliases.isChecked()
        __prefs__['overwrite_when_creating'] = self.overwrite_when_creating.isChecked()
        __prefs__['overwrite_when_sending'] = self.overwrite_when_sending.isChecked()
        __prefs__['create_send_xray'] = self.create_send_xray.isChecked()
        __prefs__['create_send_author_profile'] = self.create_send_author_profile.isChecked()
        __prefs__['create_send_start_actions'] = self.create_send_start_actions.isChecked()
        __prefs__['create_send_end_actions'] = self.create_send_end_actions.isChecked()
        if self.file_preference_mobi.isChecked():
            __prefs__['file_preference'] = 'mobi'
        elif self.file_preference_azw3.isChecked():
            __prefs__['file_preference'] = 'azw3'
        __prefs__['mobi'] = self.mobi.isChecked()
        __prefs__['azw3'] = self.azw3.isChecked()
