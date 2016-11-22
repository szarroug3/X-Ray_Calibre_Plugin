# utilities.py
'''General utility functions used throughout plugin'''

from httplib import HTTPException
from calibre_plugins.xray_creator.lib.exceptions import PageDoesNotExist

HEADERS = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/html",
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0"}

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
    except PageDoesNotExist as e:
        raise e
    except HTTPException:
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
