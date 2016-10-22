#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2016, Samreen Zarroug, Anthony Toole, & Alex Mayer'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QCheckBox, QGroupBox, QFrame

from calibre.utils.config import JSONConfig

prefs = JSONConfig('plugins/xray_creator')

# Set defaults
prefs.defaults['send_to_device'] = True
prefs.defaults['create_xray_when_sending'] = True
prefs.defaults['expand_aliases'] = True
prefs.defaults['create_send_xray'] = True
prefs.defaults['create_send_author_profile'] = False
prefs.defaults['create_send_start_actions'] = False
prefs.defaults['create_send_end_actions'] = False
prefs.defaults['mobi'] = True
prefs.defaults['azw3'] = True

class ConfigWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.send_to_device = QCheckBox('Send x-ray to device if connected')
        self.send_to_device.setChecked(prefs['send_to_device'])
        self.l.addWidget(self.send_to_device)

        self.create_xray_when_sending = QCheckBox('Create x-ray for files that don\'t already have them when sending to device')
        self.create_xray_when_sending.setChecked(prefs['create_xray_when_sending'])
        self.l.addWidget(self.create_xray_when_sending)

        self.expand_aliases = QCheckBox('Auto associate split aliases [?]')
        self.expand_aliases.setChecked(prefs['expand_aliases'])
        expand_alias_explanation = 'When enabled, this will split aliases up further.\n\nExample: If a character on goodreads named "Vin" has a Goodreads alias of "Valette Renoux",\nthis option will add "Valette" and "Renoux" as aliases. You may not want this in cases such\nas "Timothy Cratchit" who has a Goodreads alias of "Tiny Tim". Having this feature on would\nadd "Tiny", and "Tim" as aliases which is not valid.'
        self.expand_aliases.setWhatsThis(expand_alias_explanation)
        self.expand_aliases.setToolTip(expand_alias_explanation)
        self.l.addWidget(self.expand_aliases)

        self.separator_a = QFrame()
        self.separator_a.setFrameStyle(QFrame.HLine)
        self.separator_a.setFrameShadow(QFrame.Sunken)
        self.l.addWidget(self.separator_a)

        self.files_to_create = QGroupBox()
        self.files_to_create.setTitle('Files to create/send')
        self.files_to_create.setLayout(QGridLayout (self.files_to_create))

        self.create_send_xray = QCheckBox('X-Ray')
        self.create_send_xray.setChecked(prefs['create_send_xray'])
        self.files_to_create.layout().addWidget(self.create_send_xray, 0, 0)

        self.create_send_author_profile = QCheckBox('Author Profile')
        self.create_send_author_profile.setChecked(prefs['create_send_author_profile'])
        self.files_to_create.layout().addWidget(self.create_send_author_profile, 1, 0)

        self.create_send_start_actions = QCheckBox('Start Actions')
        self.create_send_start_actions.setChecked(prefs['create_send_start_actions'])
        self.files_to_create.layout().addWidget(self.create_send_start_actions, 0, 1)

        self.create_send_end_actions = QCheckBox('End Actions')
        self.create_send_end_actions.setChecked(prefs['create_send_end_actions'])
        self.files_to_create.layout().addWidget(self.create_send_end_actions, 1, 1)

        self.l.addWidget(self.files_to_create)

        self.separator_b = QFrame()
        self.separator_b.setFrameStyle(QFrame.HLine)
        self.separator_b.setFrameShadow(QFrame.Sunken)
        self.l.addWidget(self.separator_b)

        self.book_types_to_create = QGroupBox()
        self.book_types_to_create.setTitle('Book types to create x-ray files for')
        self.book_types_to_create.setLayout(QHBoxLayout (self.book_types_to_create))

        self.mobi = QCheckBox('MOBI')
        self.mobi.setChecked(prefs['mobi'])
        self.book_types_to_create.layout().addWidget(self.mobi)

        self.azw3 = QCheckBox('AZW3')
        self.azw3.setChecked(prefs['azw3'])
        self.book_types_to_create.layout().addWidget(self.azw3)

        self.l.addWidget(self.book_types_to_create)

    def save_settings(self):
        prefs['send_to_device'] = self.send_to_device.isChecked()
        prefs['create_xray_when_sending'] = self.create_xray_when_sending.isChecked()
        prefs['expand_aliases'] = self.expand_aliases.isChecked()
        prefs['create_send_xray'] = self.create_send_xray.isChecked()
        prefs['create_send_author_profile'] = self.create_send_author_profile.isChecked()
        prefs['create_send_start_actions'] = self.create_send_start_actions.isChecked()
        prefs['create_send_end_actions'] = self.create_send_end_actions.isChecked()
        prefs['mobi'] = self.mobi.isChecked()
        prefs['azw3'] = self.azw3.isChecked()