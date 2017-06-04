"""Hold book information"""

from calibre_plugins.xray_creator.lib.status_info import StatusInfo
from calibre_plugins.xray_creator.lib.book_settings import BookSettings


class Book(object):
    """Class to hold and perform operations on book"""
    def __init__(self, database, book_id, connections, settings):
        # Get basic book info
        self._title = database.field_for('title', book_id)
        self._author = ' & '.join(database.field_for('authors', book_id))
        self._status = StatusInfo()

        # Verify required book info exists
        if self._title == 'Unknown' or self._author == 'Unknown':
            self._status.set(StatusInfo.FAIL, StatusInfo.F_BASIC_INFORMATION_MISSING)
            return

        book_settings = BookSettings(database, book_id, connections)
        if not book_settings.prefs['goodreads_url']:
            self._status.set(StatusInfo.FAIL, StatusInfo.F_COULD_NOT_FIND_GOODREADS_PAGE)
            return

        if not book_settings.prefs['asin']:
            self._status.set(StatusInfo.FAIL, StatusInfo.F_COULD_NOT_FIND_ASIN)
            return

        if settings['create_send_xray']:
            # TODO: Create x-ray object here
            self._xray = None
        if settings['create_send_author_profile']:
            # TODO: Create author profile object here
            self._author_profile = None
        if settings['create_send_start_actions']:
            # TODO: Create start actions object here
            self._start_actions = None
        if settings['create_send_end_actions']:
            # TODO: Create end actions object here
            self._end_actions = None

    @property
    def title(self):
        return self._title

    @property
    def author(self):
        return self._author
