#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2016, szarroug3'
__docformat__ = 'restructuredtext en'

from calibre.gui2.actions import InterfaceAction
from calibre_plugins.xray_creator.main import XRayCreatorDialog

class XRayCreatorInterfacePlugin(InterfaceAction):

    name = 'X-Ray Creator'

    # Set main action and keyboard shortcut
    action_spec = ('X-Ray Creator', None,
            'Run X-Ray Creator', 'Ctrl+Shift+Alt+X')

    def genesis(self):
        # initial setup here

        # Set the icon for this interface action
        icon = get_icons('images/icon.png')

        # The qaction is automatically created from the action_spec defined
        # above
        self.qaction.setIcon(icon)
        self.qaction.triggered.connect(self.show_dialog)

    def show_dialog(self):
        # The base plugin object defined in __init__.py
        base_plugin_object = self.interface_action_base_plugin

        # Show the config dialog
        do_user_config = base_plugin_object.do_user_config

        # self.gui is the main calibre GUI. It acts as the gateway to access
        # all the elements of the calibre user interface, it should also be the
        # parent of the dialog
        d = XRayCreatorDialog(self.gui, self.qaction.icon(), do_user_config)
        d.show()

    def apply_settings(self):
        from calibre_plugins.xray_creator.config import prefs
        # In an actual non trivial plugin, you would probably need to
        # do something based on the settings in prefs
        prefs

