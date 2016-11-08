#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
'''Creates and interacts with plugin's functions'''

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2016, Samreen Zarroug, Anthony Toole, & Alex Mayer'
__docformat__ = 'restructuredtext en'

from httplib import HTTPSConnection
from PyQt5.Qt import QMenu, QToolButton

from calibre import get_proxies

from calibre.gui2 import Dispatcher
from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.threaded_jobs import ThreadedJob

from calibre_plugins.xray_creator.config import __prefs__
from calibre_plugins.xray_creator.lib.xray_creator import XRayCreator
from calibre_plugins.xray_creator.book_config import BookConfigWidget

class XRayCreatorInterfacePlugin(InterfaceAction):
    '''Initializes plugin's interface'''
    name = 'X-Ray Creator'

    # Set main action and keyboard shortcut
    action_spec = ('X-Ray Creator', None,
                   'Run X-Ray Creator', 'Ctrl+Shift+Alt+X')
    popup_type = QToolButton.InstantPopup
    action_type = 'current'

    def __init__(self, parent, site_customization):
        InterfaceAction.__init__(self, parent, site_customization)
        self.apply_settings()
        self.menu = QMenu(self.gui)

    def genesis(self):
        '''Initial setup'''
        icon = get_icons('images/icon.png')

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
        '''Gets settings from config file'''
        self._send_to_device = __prefs__['send_to_device']
        self._create_files_when_sending = __prefs__['create_files_when_sending']
        self._expand_aliases = __prefs__['expand_aliases']
        self._overwrite_local = __prefs__['overwrite_when_creating']
        self._overwrite_device = __prefs__['overwrite_when_sending']
        self._create_send_xray = __prefs__['create_send_xray']
        self._create_send_author_profile = __prefs__['create_send_author_profile']
        self._create_send_start_actions = __prefs__['create_send_start_actions']
        self._create_send_end_actions = __prefs__['create_send_end_actions']
        self._file_preference = __prefs__['file_preference']
        self._mobi = __prefs__['mobi']
        self._azw3 = __prefs__['azw3']


        https_proxy = get_proxies(debug=False).get('https', None)
        if https_proxy:
            https_address = ':'.join(https_proxy.split(':')[:-1])
            https_port = int(https_proxy.split(':')[-1])
            self._goodreads_conn = HTTPSConnection(https_address, https_port)
            self._goodreads_conn.set_tunnel('www.goodreads.com', 443)
            self._amazon_conn = HTTPSConnection(https_address, https_port)
            self._amazon_conn.set_tunnel('www.amazon.com', 443)
        else:
            self._goodreads_conn = HTTPSConnection('www.goodreads.com')
            self._amazon_conn = HTTPSConnection('www.amazon.com')

    def create_files(self):
        '''Creates files depending on user's settings'''
        xray_creator = self._get_books('Cannot create Files')
        if xray_creator:
            job = ThreadedJob('create_files', 'Creating Files', xray_creator.create_files_event,
                              (), {}, Dispatcher(self.created_files))
            self.gui.job_manager.run_threaded_job(job)

    def send_files(self):
        '''Sends files depending on user's settings'''
        xray_creator = self._get_books('Cannot send Files')
        if xray_creator:
            job = ThreadedJob('send_files', 'Sending Files to Device', xray_creator.send_files_event,
                              (), {}, Dispatcher(self.sent_files))
            self.gui.job_manager.run_threaded_job(job)

    def book_config(self):
        '''Opens up a dialog that allows user to set book specific preferences'''
        database = self.gui.current_db
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            error_dialog(self.gui, 'Cannot set book preferences',
                         'No books selected', show=True)
            return

        ids = list(map(self.gui.library_view.model().id, rows))

        BookConfigWidget(database.new_api, ids, self._expand_aliases, self.gui, self._goodreads_conn, self._amazon_conn)

    def created_files(self, job):
        '''Dispatcher for create_files'''
        pass

    def sent_files(self, job):
        '''Dispatcher for send_files'''
        pass

    def _get_books(self, error_msg):
        '''Gets selected books'''
        database = self.gui.current_db
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            error_dialog(self.gui, error_msg,
                         'No books selected', show=True)
            return None

        ids = list(map(self.gui.library_view.model().id, rows))

        formats = []
        if self._mobi:
            formats.append('mobi')
        if self._azw3:
            formats.append('azw3')

        xray_creator = XRayCreator(database.new_api, ids, formats, self._goodreads_conn, self._amazon_conn,
                                   self._send_to_device, self._create_files_when_sending, self._expand_aliases,
                                   self._overwrite_local, self._overwrite_device, self._create_send_xray,
                                   self._create_send_author_profile, self._create_send_start_actions,
                                   self._create_send_end_actions, self._file_preference)
        return xray_creator

    def config(self):
        '''Opens up a dialog that allows user to set general preferences'''
        self.interface_action_base_plugin.do_user_config(parent=self.gui)
