#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2016, Samreen Zarroug, Anthony Toole, & Alex Mayer'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QMenu, QToolButton

from calibre.gui2 import error_dialog
from calibre.gui2 import Dispatcher
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.threaded_jobs import ThreadedJob

from calibre_plugins.xray_creator.config import prefs
from calibre_plugins.xray_creator.lib.xray_creator import *
from calibre_plugins.xray_creator.book_config import BookConfigWidget

class XRayCreatorInterfacePlugin(InterfaceAction):

    name = 'X-Ray Creator'

    # Set main action and keyboard shortcut
    action_spec = ('X-Ray Creator', None,
            'Run X-Ray Creator', 'Ctrl+Shift+Alt+X')
    popup_type = QToolButton.InstantPopup
    action_type = 'current'

    def genesis(self):
        # initial setup here
        self.apply_settings()

        icon = get_icons('images/icon.png')

        self.menu = QMenu(self.gui)
        self.create_menu_action(self.menu, 'Book Specific Preferences',
                'Book Specific Preferences', None, 'CTRL+SHIFT+ALT+Z',
                'Set preferences specific to the book', self.book_config)
        self.create_menu_action(self.menu, 'X-Ray Creator Create/Update Button',
                'Create/Update Files', None, 'CTRL+SHIFT+ALT+X',
                'Create/Update files for chosen books', self.create_files)
        self.create_menu_action(self.menu, 'Send Local Files to Device',
                'Sends Files to Device', None, 'CTRL+SHIFT+ALT+C',
                'Sends files to device', self.send_files)

        self.menu.addSeparator()

        self.create_menu_action(self.menu, 'X-Ray Creator Preferences Button',
                'Preferences', None, None,
                'Create X-Rays for Chosen Books', self.config)
        self.qaction.setIcon(icon)
        self.qaction.setMenu(self.menu)

    def apply_settings(self):
        self._send_to_device = prefs['send_to_device']
        self._create_xray_when_sending = prefs['create_xray_when_sending']
        self._expand_aliases = prefs['expand_aliases']
        self._create_send_xray = prefs['create_send_xray']
        self._create_send_author_profile = prefs['create_send_author_profile']
        self._create_send_start_actions = prefs['create_send_start_actions']
        self._create_send_end_actions = prefs['create_send_end_actions']
        self._file_preference = prefs['file_preference']
        self._mobi = prefs['mobi']
        self._azw3 = prefs['azw3']

    def create_files(self):
        xray_creator = self._get_books('Cannot create Files')
        if xray_creator:
            job = ThreadedJob('create_files', 'Creating Files', xray_creator.create_files_event, (), {}, Dispatcher(self.created_files))
            self.gui.job_manager.run_threaded_job(job)

    def send_files(self):
        xray_creator = self._get_books('Cannot send Files')
        if xray_creator:
            job = ThreadedJob('send_files', 'Sending Files to Device', xray_creator.send_files_event, (), {}, Dispatcher(self.sent_files))
            self.gui.job_manager.run_threaded_job(job)

    def book_config(self):
        db = self.gui.current_db
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            error_dialog(self.gui, 'Cannot set book preferences',
                         'No books selected', show=True)
            return

        ids = list(map(self.gui.library_view.model().id, rows))
        db = db.new_api

        book_configs = BookConfigWidget(db, ids, self._expand_aliases, self.gui)

    def created_files(self, job):
        pass

    def send_files(self, job):
        pass

    def _get_books(self, error_msg):
        from calibre.ebooks.metadata.meta import get_metadata, set_metadata

        db = self.gui.current_db
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            error_dialog(self.gui, error_msg,
                         'No books selected', show=True)
            return None

        ids = list(map(self.gui.library_view.model().id, rows))
        db = db.new_api

        formats = []
        if self._mobi:
            formats.append('mobi')
        if self._azw3:
            formats.append('azw3')

        xray_creator = XRayCreator(db, ids, formats, self._send_to_device, self._create_xray_when_sending, self._expand_aliases, self._create_send_xray,
            self._create_send_author_profile, self._create_send_start_actions, self._create_send_end_actions, self._file_preference)
        return xray_creator

    def config(self):
        self.interface_action_base_plugin.do_user_config(parent=self.gui)