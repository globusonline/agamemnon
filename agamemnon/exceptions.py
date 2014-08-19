class AgamemnonException(Exception):
    """Base class for errors raised by Agamemnon."""

class NoTransactionError(AgamemnonException):
    pass

class NodeNotFoundException(AgamemnonException):
    pass

class CassandraClusterNotFoundException(AgamemnonException):
    pass
