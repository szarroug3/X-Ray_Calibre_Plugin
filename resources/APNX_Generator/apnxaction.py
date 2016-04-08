# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os, time
import cStringIO
from threading import Thread
from Queue import Queue

from PyQt4.Qt import Qt, QMenu, QFileDialog, QIcon, QPixmap

from calibre import sanitize_file_name
from calibre.devices.kindle.apnx import APNXBuilder
from calibre.gui2 import Dispatcher, warning_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.library.save_to_disk import get_components
from calibre.library.save_to_disk import config
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.filenames import shorten_components_to
from calibre.utils.ipc.job import BaseJob

class APNXAction(InterfaceAction):

    name = 'APNX'
    action_spec = (_('APNX'), None, None, None)
    
    def genesis(self):
        self.apnx_mixin = APNXMixin(self.gui)
        # Read the icons and assign to our global for potential sharing with the configuration dialog
        # Assign our menu to this action and an icon
        self.qaction.setIcon(get_icons('images/plugin_apnx_apnx.png'))
        self.qaction.triggered.connect(self.generate_selected)
        self.apnx_menu = QMenu()
        self.load_menu()
        
    def load_menu(self):
        self.apnx_menu.clear()
        self.apnx_menu.addAction(_('Generate from selected books...'), self.generate_selected)
        self.apnx_menu.addAction(_('Generate from file...'), self.generate_file)
        self.qaction.setMenu(self.apnx_menu)

    def generate_selected(self):
        self.apnx_mixin.genesis()
        
        apnxdir = unicode(QFileDialog.getExistingDirectory(self.gui, _('Directory to save APNX file'), self.gui.library_path, QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        if not apnxdir:
            return
        
        self._generate_selected(apnxdir)
        
    def _generate_selected(self, apnxdir, ids=None, do_auto_convert=False):
        if not ids:
            ids = [self.gui.library_view.model().id(r) for r in self.gui.library_view.selectionModel().selectedRows()]
        
        _files, _auto_ids = self.gui.library_view.model().get_preferred_formats_from_ids(ids, ['mobi', 'azw', 'prc'], exclude_auto=do_auto_convert)
        if do_auto_convert:
            ok_ids = list(set(ids).difference(_auto_ids))
            ids = [i for i in ids if i in ok_ids]
        else:
            _auto_ids = []
            
        metadata = self.gui.library_view.model().metadata_for(ids)
        ids = iter(ids)
        imetadata = iter(metadata)

        bad, good = [], []
        for f in _files:
            mi = imetadata.next()
            id = ids.next()
            if f is None:
                bad.append(mi.title)
            else:
                good.append((f, mi))

        template = config().parse().template
        if not isinstance(template, unicode):
            template = template.decode('utf-8')

        for f, mi in good:
            components = get_components(template, mi, f)
            if not components:
                components = [sanitize_file_name(mi.title)]

            def remove_trailing_periods(x):
                ans = x
                while ans.endswith('.'):
                    ans = ans[:-1].strip()
                if not ans:
                    ans = 'x'
                return ans
            
            components = list(map(remove_trailing_periods, components))
            components = shorten_components_to(250, components)
            components = list(map(sanitize_file_name, components))
            filepath = os.path.join(apnxdir, *components)

            apnxname = os.path.splitext(filepath)[0] + '.apnx'
            self.apnx_mixin.generate_apnx(f, apnxname)

        if bad:
            bad = '\n'.join('%s'%(i,) for i in bad)
            d = warning_dialog(self.gui, _('No suitable formats'),
                    _('Could not generate an APNX for the following books, '
                'as no suitable formats were found. Convert the book(s) to '
                'MOBI first.'
                ), bad)
            d.exec_()
    
    def generate_file(self):
        self.apnx_mixin.genesis()
        
        filename = unicode(QFileDialog.getOpenFileName(self.gui, _('MOBI file for generating APNX'), self.gui.library_path, 'MOBI files (*.mobi *.azw *.prc)'))
        if not filename:
            return
        apnxdir = unicode(QFileDialog.getExistingDirectory(self.gui, _('Directory to save APNX file'), self.gui.library_path, QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))
        if not apnxdir:
            return
        apnxname = os.path.join(apnxdir, os.path.splitext(os.path.basename(filename))[0] + '.apnx')
        
        self.apnx_mixin.generate_apnx(filename, apnxname)


class APNXJob(BaseJob):
    
    def __init__(self, callback, description, job_manager, filename, apnxname):
        BaseJob.__init__(self, description)
        self.exception = None
        self.job_manager = job_manager
        self.args = (filename, apnxname)
        self.callback = callback
        self.log_path = None
        self._log_file = cStringIO.StringIO()
        self._log_file.write(self.description.encode('utf-8') + '\n')

    @property
    def log_file(self):
        if self.log_path is not None:
            return open(self.log_path, 'rb')
        return cStringIO.StringIO(self._log_file.getvalue())

    def start_work(self):
        self.start_time = time.time()
        self.job_manager.changed_queue.put(self)

    def job_done(self):
        self.duration = time.time() - self.start_time
        self.percent = 1
        # Dump log onto disk
        lf = PersistentTemporaryFile('apnx_generate_log')
        lf.write(self._log_file.getvalue())
        lf.close()
        self.log_path = lf.name
        self._log_file.close()
        self._log_file = None

        self.job_manager.changed_queue.put(self)

    def log_write(self, what):
        self._log_file.write(what)
        
        
class APNXGenerator(Thread):
    
    def __init__(self, job_manager):
        Thread.__init__(self)
        self.daemon = True
        self.jobs = Queue()
        self.job_manager = job_manager
        self._run = True
        self.apnx_builder = APNXBuilder()
        
    def stop(self):
        self._run = False
        self.jobs.put(None)
        
    def run(self):
        while self._run:
            try:
                job = self.jobs.get()
            except:
                break
            if job is None or not self._run:
                break
            
            failed, exc = False, None
            job.start_work()
            if job.kill_on_start:
                self._abort_job(job)
                continue
            
            try:
                self._generate_apnx(job)
            except Exception as e:
                if not self._run:
                    return
                import traceback
                failed = True
                exc = e
                job.log_write('\nAPNX generation failed...\n')
                job.log_write(traceback.format_exc())

            if not self._run:
                break

            job.failed = failed
            job.exception = exc
            job.job_done()
            try:
                job.callback(job)
            except:
                import traceback
                traceback.print_exc()

    def _abort_job(self, job):
        job.log_write('Aborted\n')
        job.failed = False
        job.killed = True
        job.job_done()

    def _generate_apnx(self, job):
        filename, apnxname = job.args
        if not filename or not apnxname:
            raise Exception(_('Nothing to do.'))
        dirs = os.path.dirname(apnxname)
        if not os.path.exists(dirs):
            os.makedirs(dirs)
        self.apnx_builder.write_apnx(filename, apnxname)
        
    def generate_apnx(self, callback, filename, apnxname):
        description = _('Generating APNX for %s') % os.path.splitext(os.path.basename(apnxname))[0]
        job = APNXJob(callback, description, self.job_manager, filename, apnxname)
        self.job_manager.add_job(job)
        self.jobs.put(job)


class APNXMixin(object):

    def __init__(self, gui):
        self.gui = gui
    
    def genesis(self):
        '''
        Genesis must always be called before using an APNXMixin object.
        Plugins are initalized before the GUI initalizes the job_manager.
        We cannot create the APNXGenerator during __init__. Instead call
        genesis before using generate_apnx to ensure the APNXGenerator
        has been properly created with the job_manager.
        '''
        if not hasattr(self.gui, 'apnx_generator'):
            self.gui.apnx_generator = APNXGenerator(self.gui.job_manager)

    def generate_apnx(self, filename, apnxname):
        if not self.gui.apnx_generator.is_alive():
            self.gui.apnx_generator.start()
        self.gui.apnx_generator.generate_apnx(Dispatcher(self.apnx_generated), filename, apnxname)
        self.gui.status_bar.show_message(_('Generating APNX for %s') % os.path.splitext(os.path.basename(apnxname))[0], 3000)
    
    def apnx_generated(self, job):
        if job.failed:
            self.gui.job_exception(job, dialog_title=_('Failed to generate APNX'))
            return
        self.gui.status_bar.show_message(job.description + ' ' + _('finished'), 5000)
