"""Base class for message types"""


class MsgBase(object):  # pylint: disable=too-few-public-methods
    """Base class for message types"""
    def __init__(self):
        self.data = {"": type(self).__name__.lower()}
