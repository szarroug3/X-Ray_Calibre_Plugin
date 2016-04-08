# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.customize import InterfaceActionBase

class ActionAPNX(InterfaceActionBase):

    name = 'APNX Generator'
    description = 'Generate Amazon APNX page number file'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'John Schember'
    version = (1, 1, 0)
    minimum_calibre_version = (0, 7, 53)
    
    actual_plugin = 'calibre_plugins.apnx_generator.apnxaction:APNXAction'