#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
'''Creates and interacts with plugin's functions'''

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2016, Samreen Zarroug, Anthony Toole, & Alex Mayer'
__docformat__ = 'restructuredtext en'

import os
from httplib import HTTPSConnection
from PyQt5.Qt import QMenu, QToolButton, QIcon, QPixmap

from calibre import get_proxies
from calibre.gui2 import Dispatcher
from calibre.gui2 import error_dialog
from calibre.utils.config import config_dir
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.threaded_jobs import ThreadedJob

from calibre.customize.zipplugin import get_icons
from calibre_plugins.xray_creator.lib.book import Book
from calibre_plugins.xray_creator.config import __prefs__ as settings
from calibre_plugins.xray_creator.book_config import BookConfigWidget
from calibre_plugins.xray_creator.lib.xray_creator import XRayCreator
from calibre_plugins.xray_creator.lib.book_settings import BookSettings


class XRayCreatorInterfacePlugin(InterfaceAction):
    '''Initializes plugin's interface'''
    name = 'X-Ray Creator'

    # Set main action and keyboard shortcut
    action_spec = ('X-Ray Creator', None, 'Run X-Ray Creator', 'Ctrl+Shift+Alt+X')
    popup_type = QToolButton.InstantPopup
    action_type = 'current'

    def __init__(self, parent, site_customization):
        InterfaceAction.__init__(self, parent, site_customization)

        https_proxy = get_proxies(debug=False).get('https', None)
        if https_proxy:
            https_address = ':'.join(https_proxy.split(':')[:-1])
            https_port = int(https_proxy.split(':')[-1])
            goodreads_conn = HTTPSConnection(https_address, https_port)
            goodreads_conn.set_tunnel('www.goodreads.com', 443)
            amazon_conn = HTTPSConnection(https_address, https_port)
            amazon_conn.set_tunnel('www.amazon.com', 443)
        else:
            goodreads_conn = HTTPSConnection('www.goodreads.com')
            amazon_conn = HTTPSConnection('www.amazon.com')

        self._connections = {'goodreads': goodreads_conn, 'amazon': amazon_conn}
        self.menu = QMenu(self.gui)

    def genesis(self):
        '''Initial setup'''
        icon = self.get_icon('icon.png')

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

    def create_files(self):
        '''Creates files depending on user's settings'''
        xray_creator = self._get_books('Cannot create Files')
        if xray_creator:
            job = ThreadedJob('create_files', 'Creating Files', xray_creator.create_files_event,
                              ((self.gui.current_db.new_api,)), {}, Dispatcher(self.created_files))
            self.gui.job_manager.run_threaded_job(job)

    def send_files(self):
        '''Sends files depending on user's settings'''
        xray_creator = self._get_books('Cannot send Files')
        if xray_creator:
            job = ThreadedJob('send_files', 'Sending Files to Device', xray_creator.send_files_event,
                              ((self.gui.current_db.new_api,)), {}, Dispatcher(self.sent_files))
            self.gui.job_manager.run_threaded_job(job)

    def book_config(self):
        '''Opens up a dialog that allows user to set book specific preferences'''
        database = self.gui.current_db.new_api
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            error_dialog(self.gui, 'Cannot set book preferences',
                         'No books selected', show=True)
            return

        book_ids = list(map(self.gui.library_view.model().id, rows))

        book_settings_list = []
        for book_id in book_ids:
            book_settings = BookSettings(database, book_id, self._connections)
            if len(book_settings.aliases) == 0 and book_settings.goodreads_url != '':
                book_settings.update_aliases(book_settings.goodreads_url)
                book_settings.save()
            book_settings_list.append(book_settings)

        BookConfigWidget(self.gui, book_settings_list)

    def created_files(self, job):
        '''Dispatcher for create_files'''
        pass

    def sent_files(self, job):
        '''Dispatcher for send_files'''
        pass

    def _get_books(self, error_msg):
        '''Gets selected books'''
        database = self.gui.current_db.new_api
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            error_dialog(self.gui, error_msg,
                         'No books selected', show=True)
            return None

        book_ids = list(map(self.gui.library_view.model().id, rows))

        # Initialize each book's information
        books = []
        for book_id in book_ids:
            books.append(Book(database, book_id, self._connections, settings))

        return XRayCreator(books, settings)

    def config(self):
        '''Opens up a dialog that allows user to set general preferences'''
        self.interface_action_base_plugin.do_user_config(parent=self.gui)

    def get_icon(self, icon_name):
        """
        Check to see whether the icon exists as a Calibre resource
        This will enable skinning if the user stores icons within a folder like:
        ...\AppData\Roaming\calibre\resources\images\Plugin Name\
        """
        icon_path = os.path.join(config_dir, 'resources', 'images', self.name, icon_name)
        if not os.path.exists(icon_path):
            return get_icons(self.plugin_path, 'images/{0}'.format(icon_name))
        pixmap = QPixmap()
        pixmap.load(icon_path)
        return QIcon(pixmap)
