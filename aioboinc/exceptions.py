"""
Exceptions raised by the client
Every one of them is a BOINCClientError, so catching that catches them all.
"""


class BOINCClientError(Exception):
    """
    Base of every error the client raises
    Raised as is when the BOINC client answers a request with an error
    """


class BOINCConnectionError(BOINCClientError, ConnectionError):
    """
    The BOINC client could not be reached, the connection was lost, or what answered is not a
    BOINC client
    The connection is dropped: connect() and authorize() again to go on.
    """


class BOINCTimeoutError(BOINCConnectionError, TimeoutError):
    """
    The BOINC client did not answer within the timeout
    """


class BOINCAuthError(BOINCClientError):
    """
    The password is wrong or missing, or the request needs authorize() first
    """
