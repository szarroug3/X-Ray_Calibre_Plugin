#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2016, szarroug3'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QWidget, QVBoxLayout, QLabel, QLineEdit, QCheckBox

from calibre.utils.config import JSONConfig

prefs = JSONConfig('plugins/xray_creator')

# Set defaults
prefs.defaults['spoilers'] = False
prefs.defaults['send_to_device'] = True
prefs.defaults['create_xray_when_sending'] = True

class ConfigWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.spoilers = QCheckBox('Use spoilers when creating x-ray')
        self.spoilers.setChecked(prefs['spoilers'])
        self.l.addWidget(self.spoilers)

        self.send_to_device = QCheckBox('Send x-ray to device if connected')
        self.send_to_device.setChecked(prefs['send_to_device'])
        self.l.addWidget(self.send_to_device)

        self.create_xray_when_sending = QCheckBox('Create x-ray for files that don\'t already have them when sending to device')
        self.create_xray_when_sending.setChecked(prefs['create_xray_when_sending'])
        self.l.addWidget(self.create_xray_when_sending)

    def save_settings(self):
        prefs['spoilers'] = self.spoilers.isChecked()
        prefs['send_to_device'] = self.send_to_device.isChecked()
        prefs['create_xray_when_sending'] = self.create_xray_when_sending.isChecked()