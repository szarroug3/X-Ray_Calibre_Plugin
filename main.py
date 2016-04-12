#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2016, szarroug3 & dresendez'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QDialog, QVBoxLayout, QPushButton, QMessageBox, QLabel

from calibre_plugins.xray_creator.config import prefs
from calibre.ebooks.metadata.mobi import MetadataUpdater
from calibre.ebooks.mobi.reader.headers import EXTHHeader

import struct
import os

class XRayCreatorDialog(QDialog):

    def __init__(self, gui, icon, do_user_config):
        QDialog.__init__(self, gui)
        self.gui = gui
        self.do_user_config = do_user_config

        # The current database shown in the GUI
        # db is an instance of the class LibraryDatabase from db/legacy.py
        # This class has many, many methods that allow you to do a lot of
        # things. For most purposes you should use db.new_api, which has
        # a much nicer interface from db/cache.py
        self.db = gui.current_db

        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.setWindowTitle('X-Ray Creator')
        self.setWindowIcon(icon)

        self.create_xray_button = QPushButton(
            'Create X-Ray for chosen books', self)
        self.create_xray_button.clicked.connect(self.create_xray)
        self.l.addWidget(self.create_xray_button)

        self.conf_button = QPushButton(
                'Configure this plugin', self)
        self.conf_button.clicked.connect(self.config)
        self.l.addWidget(self.conf_button)

        self.resize(self.sizeHint())

    def create_xray(self):
        '''
        Set the metadata in the files in the selected book's record to
        match the current metadata in the database.
        '''
        from calibre.ebooks.metadata.meta import get_metadata, set_metadata
        from calibre.gui2 import error_dialog, info_dialog

        # Get currently selected books
        rows = self.gui.library_view.selectionModel().selectedRows()
        if not rows or len(rows) == 0:
            return error_dialog(self.gui, 'Cannot create X-Ray',
                             'No books selected', show=True)
        # Map the rows to book ids
        ids = list(map(self.gui.library_view.model().id, rows))
        db = self.db.new_api
        for book_id in ids:
            # Get the current ASIN for this book from the db
            mi = db.get_metadata(book_id, get_cover=True, cover_as_data=True)
            fmts = db.formats(book_id)
            if not fmts:
                continue
            for fmt in fmts:
                fmt = fmt.lower()

                # Get a python file object for the format. This will be either
                # an in memory file or a temporary on disk file
                ffile = db.format(book_id, fmt, as_file=True)
                ffile.seek(0)
                # Set metadata in the format
                set_metadata(ffile, mi, fmt)
                ffile.seek(0)
                # Now replace the file in the calibre library with the updated
                # file. We dont use add_format_with_hooks as the hooks were
                # already run when the file was first added to calibre.
                db.add_format(book_id, fmt, ffile, run_hooks=False)
            book_path = db.format_abspath(book_id, 'MOBI')
            with open(book_path, 'rb') as stream:
                raw = stream.read()
                doctype = raw[:4]
                length, num_items = struct.unpack('>LL', raw[4:12])
                print ('------------------------------------')
                print (doctype, length, num_items)
                print ('------------------------------------')
                exthHeader = EXTHHeader(raw, 'utf8', None)
                mu = MetadataUpdater(stream)
                print ('------------------------------------')
                print (self.start_offset)
                erl = struct.unpack('>i', mu.record0[0x04:0x08])[0]
                print ('------------------------------------')
                print ('erl:', erl)
                print ('------------------------------------')
                print (mu.have_exth)
                print ('------------------------------------')
                i = 100
                length = len(mu.record(mu.nrecs-i))
                stringlen = '%is' % length
                print (i, length)
                print (mu.record(mu.nrecs-i)[0:length])
                print (struct.unpack(stringlen, mu.record(mu.nrecs-i)[0:length]))
                print ('------------------------------------')


        info_dialog(self, 'Updated files',
                'Updated the metadata in the files of %d book(s)'%len(ids),
                show=True)

    def config(self):
        self.do_user_config(parent=self)
        # Apply the changes