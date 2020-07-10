import logging

from message import Message

logger = logging.getLogger('default')


def constructObject(data):
    """Constructing an object using `.Message` class"""

    try:
        obj = Message()
        obj.decode(data)
    except KeyError as e:
        logger.error("Missing mandatory key %s", e)
    except:
        logger.error("classBase fail", exc_info=True)
    else:
        return obj
