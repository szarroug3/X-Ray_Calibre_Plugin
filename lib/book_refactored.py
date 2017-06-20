# !/usr/bin/env python

"""
Contains classes for things related to the book
"""

from calibre_plugins.xray_creator.lib.status_info import StatusInfo

FAIL = -1
SUCCESS = 0
NOT_STARTED = 1
IN_PROGRESS = 2


class Book(object):

    """Holds book information such as author and title and perform operations on the data"""

    def __init__(self, database, book_id):
        """
        Get the book's basic data and initialize the variables

        Args:
            :Cache database: Calibre database containing book information
            :int book_id: id of the book we're working with
        """
        self._title = database.field_for('title', book_id)
        self._author = ' & '.join(database.field_for('authors', book_id))
        self._status = Status()

    @property
    def title(self):
        return self._title

    @property
    def author(self):
        return self._author

    @property
    def status(self):
        return self._status


class Status(object):

    """Holds status information for book, x-ray, author profile, start actions, and end actions"""

    def __init__(self):
        """Initialize the statues"""
        self._general = StatusInfo(status=IN_PROGRESS)
        self._xray = StatusInfo(status=NOT_STARTED)
        self._author_profile = StatusInfo(status=NOT_STARTED)
        self._start_actions = StatusInfo(status=NOT_STARTED)
        self._end_actions = StatusInfo(status=NOT_STARTED)

    @property
    def general(self):
        return self._general

    @property
    def xray(self):
        return self._xray

    @property
    def author_profile(self):
        return self._author_profile

    @property
    def start_actions(self):
        return self._start_actions

    @property
    def end_actions(self):
        return self._end_actions
