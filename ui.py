#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2016, szarroug3'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QMenu, QToolButton

from calibre.gui2 import Dispatcher
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.threaded_jobs import ThreadedJob

from calibre_plugins.xray_creator.config import prefs
from calibre_plugins.xray_creator.helpers.xray_creator import *

class XRayCreatorInterfacePlugin(InterfaceAction):

    name = 'X-Ray Creator'

    # Set main action and keyboard shortcut
    action_spec = ('X-Ray Creator', None,
            'Run X-Ray Creator', 'Ctrl+Shift+Alt+X')
    popup_type = QToolButton.InstantPopup
    action_type = 'current'

    def genesis(self):
        # initial setup here
        self._spoilers = prefs['spoilers']
        self._send_to_device = prefs['send_to_device']
        self._create_xray_when_sending = prefs['create_xray_when_sending']
        
        icon = get_icons('images/icon.png')

        self.menu = QMenu(self.gui)
        self.create_menu_action(self.menu, 'X-Ray Creator Create Button',
                'Create X-Rays', None, None,
                'Create X-Rays for Chosen Books', self.create_xrays)
        self.create_menu_action(self.menu, 'Send Local X-Rays to Device',
                'Send X-Ray files to Device', None, None,
                'Sends X-Ray files to Device', self.send_xrays)
        self.menu.addSeparator()
        self.create_menu_action(self.menu, 'X-Ray Creator Preferences Button',
                'Preferences', None, None,
                'Create X-Rays for Chosen Books', self.config)
        self.qaction.setIcon(icon)
        self.qaction.setMenu(self.menu)

    def apply_settings(self):
        from calibre_plugins.xray_creator.config import prefs

        self._spoilers = prefs['spoilers']
        self._send_to_device = prefs['send_to_device']
        self._create_xray_when_sending = prefs['create_xray_when_sending']

    def create_xrays(self):
        from calibre.ebooks.metadata.meta import get_metadata, set_metadata
        from calibre.gui2 import error_dialog, info_dialog

        self.db = self.gui.current_db

        # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, 'Cannot create X-Ray',
                             'No books selected', show=True)
        # Map the rows to book ids
        ids = list(map(self.gui.library_view.model().id, rows))
        db = self.db.new_api
        books = Books(db, ids, spoilers=self._spoilers)
        print (books)
        job = ThreadedJob('create_xray', 'Creating X-Ray Files', books.create_xrays, (), {}, Dispatcher(self.created_xrays))
        self.gui.job_manager.run_threaded_job(job)

    def created_xrays(self, job):
        print (dir(job))
        print ('\n\n\n')
        print (dir(job.status_text))
        if job.failed:
            #job.status_text = 'Failed to create x-ray files'
            return
        #job.status_text = job.descritpion + ' ' + 'finished'

    def send_xrays(self):
        pass

    def config(self):
        self.interface_action_base_plugin.do_user_config(self.gui)