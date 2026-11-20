"""
Exceptions raised by the client
Every one of them is a BOINCError, so catching that catches them all.
"""


class BOINCError(Exception):
    """
    Base of every error the client raises
    """


# The name the base had before there were others under it, kept so that code catching it goes on
# working.
BOINCClientError = BOINCError


class BOINCAuthError(BOINCError):
    """
    The password is wrong or missing, or the request needs authorize() first
    """


class BOINCCommandError(BOINCError):
    """
    The BOINC client answered the request with an error, such as "no such result"
    The connection is kept.
    """


class BOINCConnectionError(BOINCError, ConnectionError):
    """
    The BOINC client could not be reached, or the connection was lost
    The connection is dropped: connect() and authorize() again to go on.
    """


class BOINCTimeoutError(BOINCConnectionError, TimeoutError):
    """
    The BOINC client did not answer within the timeout
    """


class BOINCProtocolError(BOINCConnectionError):
    """
    What answered does not speak the GUI RPC protocol as a BOINC client does: the reply is not XML,
    is empty, or is not the one expected
    """
