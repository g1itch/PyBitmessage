"""
Network subsystem package
"""

from connectionpool import BMConnectionPool
from receivequeuethread import ReceiveQueueThread
from threads import StoppableThread


__all__ = [
    "BMConnectionPool",
    "ReceiveQueueThread", "StoppableThread"
    # "AddrThread", "AnnounceThread", "BMNetworkThread", "Dandelion",
    # "DownloadThread", "InvThread", "UploadThread",
]


def start():
    """Start network threads"""
    from addrthread import AddrThread
    from announcethread import AnnounceThread
    from dandelion import Dandelion
    from downloadthread import DownloadThread
    from invthread import InvThread
    from networkthread import BMNetworkThread
    from knownnodes import readKnownNodes
    from uploadthread import UploadThread

    readKnownNodes()
    # init, needs to be early because other thread may access it early
    Dandelion()
    BMConnectionPool().connectToStream(1)
    asyncoreThread = BMNetworkThread()
    asyncoreThread.daemon = True
    asyncoreThread.start()
    announceThread = AnnounceThread()
    announceThread.daemon = True
    announceThread.start()
    invThread = InvThread()
    invThread.daemon = True
    invThread.start()
    addrThread = AddrThread()
    addrThread.daemon = True
    addrThread.start()
    downloadThread = DownloadThread()
    downloadThread.daemon = True
    downloadThread.start()
    uploadThread = UploadThread()
    uploadThread.daemon = True
    uploadThread.start()
