#status_info.py
'''Holds status information'''

class StatusInfo(object):
    '''Class to hold book status information'''

    # TODO: remove these (they're created in book_refactored)
    # Status
    SUCCESS = 0
    IN_PROGRESS = 1
    FAIL = 2

    # Status Messages
    F_BASIC_INFORMATION_MISSING = 'Missing title and/or author.'
    F_COULD_NOT_FIND_ASIN = 'Could not find ASIN.'
    F_COULD_NOT_FIND_GOODREADS_PAGE = 'Could not find Goodreads page.'
    F_LOCAL_BOOK_NOT_FOUND = 'Local book not found.'
    F_NO_APPROPRIATE_LOCAL_BOOK_FOUND = 'No local book of the chosen formats was found.'
    F_COULD_NOT_PARSE_GOODREADS_DATA = 'Could not parse Goodreads data.'
    F_UNABLE_TO_PARSE_BOOK = 'Unable to parse book.'
    F_REMOVE_LOCAL_XRAY = 'Unable to remove local x-ray.'
    F_PREFS_NOT_OVERWRITE_LOCAL_XRAY = ('Local x-ray found. Your preferences are set to not'
                                        ' ovewrite if one already exists.')
    F_UNABLE_TO_CREATE_XRAY = 'Unable to create x-ray.'
    F_UNABLE_TO_WRITE_XRAY = 'Unable to write x-ray.'
    F_UNABLE_TO_SEND_XRAY = 'Unable to send x-ray.'
    F_PREFS_NOT_OVERWRITE_DEVICE_XRAY = ('Device already has x-ray for this book. Your preferences'
                                         ' are set to not ovewrite if one already exists.')
    F_REMOVE_LOCAL_AUTHOR_PROFILE = 'Unable to remove local author profile.'
    F_PREFS_NOT_OVERWRITE_LOCAL_AUTHOR_PROFILE = ('Local author profile found. Your preferences are'
                                                  ' set to not ovewrite if one already exists.')
    F_UNABLE_TO_CREATE_AUTHOR_PROFILE = 'Unable to create author profile.'
    F_UNABLE_TO_WRITE_AUTHOR_PROFILE = 'Unable to write author profile.'
    F_UNABLE_TO_SEND_AUTHOR_PROFILE = 'Unable to send author profile.'
    F_PREFS_NOT_OVERWRITE_DEVICE_AUTHOR_PROFILE = ('Device already has author profile for this'
                                                   ' book. Your preferences are set to not'
                                                   ' ovewrite if one already exists.')
    F_REMOVE_LOCAL_START_ACTIONS = 'Unable to remove local start actions.'
    F_PREFS_NOT_OVERWRITE_LOCAL_START_ACTIONS = ('Local start actions found. Your preferences are'
                                                 ' set to not ovewrite if one already exists.')
    F_UNABLE_TO_CREATE_START_ACTIONS = 'Unable to create start actions.'
    F_UNABLE_TO_WRITE_START_ACTIONS = 'Unable to write start actions.'
    F_UNABLE_TO_SEND_START_ACTIONS = 'Unable to send start actions.'
    F_PREFS_NOT_OVERWRITE_DEVICE_START_ACTIONS = ('Device already has start actions for this book.'
                                                  ' Your preferences are set to not ovewrite if'
                                                  ' one already exists.')
    F_REMOVE_LOCAL_END_ACTIONS = 'Unable to remove local end actions.'
    F_PREFS_NOT_OVERWRITE_LOCAL_END_ACTIONS = ('Local end actions found. Your preferences are set'
                                               '  to not ovewrite if one already exists.')
    F_UNABLE_TO_CREATE_END_ACTIONS = 'Unable to create end actions.'
    F_UNABLE_TO_WRITE_END_ACTIONS = 'Unable to write end actions.'
    F_UNABLE_TO_SEND_END_ACTIONS = 'Unable to send end actions.'
    F_PREFS_NOT_OVERWRITE_DEVICE_END_ACTIONS = ('Device already has end actions for this book.'
                                                ' Your preferences are set to not ovewrite if one'
                                                ' already exists.')
    F_BOOK_NOT_ON_DEVICE = 'None of the passing formats are on the device.'
    F_PREFS_SET_TO_NOT_CREATE_XRAY = ('No local x-ray found. Your preferences are set to not create'
                                      ' one if one is not already found when sending to device.')
    F_UNABLE_TO_UPDATE_ASIN = 'Unable to update ASIN in book on device.'

    def __init__(self, status=None, message=None):
        self._status = status
        self._message = message

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, val):
        self._status = val

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, val):
        self._message = val

    def set(self, status, message):
        '''Sets both status and status message'''
        self._status = status
        self._message = message
