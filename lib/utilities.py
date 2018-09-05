# utilities.py
'''General utility functions used throughout plugin'''

import re
import os
import time
import socket
from httplib import HTTPException
from calibre.library import current_library_path
from calibre_plugins.xray_creator.lib.exceptions import PageDoesNotExist

HONORIFICS = 'mr mrs ms esq prof dr fr rev pr atty adv hon pres gov sen ofc pvt cpl sgt maj capt cmdr lt col gen'
HONORIFICS = HONORIFICS.split()
HONORIFICS.extend([x + '.' for x in HONORIFICS])
HONORIFICS += 'miss master sir madam lord dame lady esquire professor doctor father mother brother sister'.split()
HONORIFICS += 'reverend pastor elder rabbi sheikh attorney advocate honorable president governor senator'.split()
HONORIFICS += 'officer private corporal sargent major captain commander lieutenant colonel general'.split()
RELIGIOUS_HONORIFICS = 'fr br sr rev pr'
RELIGIOUS_HONORIFICS = RELIGIOUS_HONORIFICS.split()
RELIGIOUS_HONORIFICS.extend([x + '.' for x in RELIGIOUS_HONORIFICS])
RELIGIOUS_HONORIFICS += 'father mother brother sister reverend pastor elder rabbi sheikh'.split()
DOUBLE_HONORIFICS = 'lord'
# We want all the honorifics to be in the general honorifics list so when we're
# checking if a word is an honorifics, we only need to search in one list
HONORIFICS += RELIGIOUS_HONORIFICS
HONORIFICS += DOUBLE_HONORIFICS

COMMON_WORDS = 'the of de'.split()

HEADERS = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/html",
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0"}

BOOK_ID_PAT = re.compile(r'\/show\/([\d]+)')
AMAZON_ASIN_PAT = re.compile(r'data\-asin=\"([a-zA-z0-9]+)\"')
GOODREADS_ASIN_PAT = re.compile(r'"asin":"(.+?)"')
GOODREADS_URL_PAT = re.compile(r'href="(\/book\/show\/.+?)"')

LIBRARY = current_library_path().replace('/', os.sep)


def open_url(connection, url, return_redirect_url=False):
    '''Tries to open url and return page's html'''
    if 'goodreads.com' in url:
        url = url[url.find('goodreads.com') + len('goodreads.com'):]
    try:
        connection.request('GET', url, headers=HEADERS)
        response = connection.getresponse()
        if response.status == 301 or response.status == 302:
            if return_redirect_url:
                return response.msg['location']
            response = open_url(connection, response.msg['location'])
        else:
            response = response.read()
    except (HTTPException, socket.error):
        time.sleep(1)
        connection.close()
        connection.connect()
        connection.request('GET', url, headers=HEADERS)
        response = connection.getresponse()
        if response.status == 301 or response.status == 302:
            if return_redirect_url:
                return response.msg['location']
            response = open_url(connection, response.msg['location'])
        else:
            response = response.read()

    if 'Page Not Found' in response:
        raise PageDoesNotExist('Page not found.')

    return response


def auto_expand_aliases(characters):
    '''Goes through each character and expands them using fullname_to_possible_aliases without adding duplicates'''
    actual_aliases = {}
    duplicates = [alias.lower() for aliases in characters.values() for alias in aliases]
    for entity_id, aliases in characters.items():
        # get all expansions for original name and aliases retrieved from goodreads
        expanded_aliases = []
        for alias in aliases:
            new_aliases = fullname_to_possible_aliases(alias.lower())
            expanded_aliases += [new_alias for new_alias in new_aliases if new_alias not in expanded_aliases]

        for alias in expanded_aliases:
            # if this alias has already been flagged as a duplicate or is a common word, skip it
            if alias in duplicates or alias in COMMON_WORDS:
                continue

            # check if this alias is a duplicate but isn't in the duplicates list
            if alias in actual_aliases:
                duplicates.append(alias)
                actual_aliases.pop(alias)
                continue

            # at this point, the alias is new -- add it to the dict with the alias as the key and fullname as the value
            actual_aliases[alias] = entity_id

    return actual_aliases


def fullname_to_possible_aliases(fullname):
    '''
    Given a full name ("{Title} ChristianName {Middle Names} {Surname}"), return a list of possible aliases

    ie. Title Surname, ChristianName Surname, Title ChristianName, {the full name}

    The returned aliases are in the order they should match
    '''
    aliases = []
    parts = fullname.split()
    title = None

    if parts[0].lower() in HONORIFICS:
        title_list = []
        while parts and parts[0].lower() in HONORIFICS:
            title_list.append(parts.pop(0))
        title = ' '.join(title_list)

    if len(parts) >= 2:
        # Assume: {Title} Firstname {Middlenames} Lastname
        # Already added the full form, also add Title Lastname, and for some Title Firstname
        surname = parts.pop()  # This will cover double barrel surnames, we split on whitespace only
        christian_name = parts.pop(0)
        if title:
            # Religious Honorifics usually only use {Title} {ChristianName}
            # ie. John Doe could be Father John but usually not Father Doe
            if title in RELIGIOUS_HONORIFICS:
                aliases.append("%s %s" % (title, christian_name))
            # Some titles work as both {Title} {ChristianName} and {Title} {Lastname}
            # ie. John Doe could be Lord John or Lord Doe
            elif title in DOUBLE_HONORIFICS:
                aliases.append("%s %s" % (title, christian_name))
                aliases.append("%s %s" % (title, surname))
            # Everything else usually goes {Title} {Lastname}
            # ie. John Doe could be Captain Doe but usually not Captain John
            else:
                aliases.append("%s %s" % (title, surname))
        # Don't want the formats {ChristianName}, {Surname} and {ChristianName} {Lastname} in special cases
        # i.e. The Lord Ruler should never have "The Ruler", "Lord" or "Ruler" as aliases
        # Same for John the Great
        if christian_name not in COMMON_WORDS and (len(parts) == 0 or parts[0] not in COMMON_WORDS):
            aliases.append(christian_name)
            aliases.append(surname)
            aliases.append("%s %s" % (christian_name, surname))

    elif title:
        # Odd, but got Title Name (eg. Lord Buttsworth), so see if we can alias
        if len(parts) > 0:
            aliases.append(parts[0])
    else:
        # We've got no title, so just a single word name.  No alias needed
        pass
    return aliases
