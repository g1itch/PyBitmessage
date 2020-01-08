"""shutdown function"""
import os
import Queue
import threading
import time

import state
from debug import logger
from helper_sql import sqlQuery, sqlStoredProcedure
from inventory import Inventory
from network import knownnodes, StoppableThread
from queues import (
    addressGeneratorQueue, objectProcessorQueue, UISignalQueue, workerQueue)


def doCleanShutdown():
    """
    Used to tell all the treads to finish work and exit.
    """
    state.shutdown = 1

    objectProcessorQueue.put(('checkShutdownVariable', 'no data'))
    for thread in threading.enumerate():
        if thread.isAlive() and isinstance(thread, StoppableThread):
            thread.stopThread()

    UISignalQueue.put((
        'updateStatusBar',
        'Saving the knownNodes list of peers to disk...'))
    logger.info('Saving knownNodes list of peers to disk')
    knownnodes.saveKnownNodes()
    logger.info('Done saving knownNodes list of peers to disk')
    UISignalQueue.put((
        'updateStatusBar',
        'Done saving the knownNodes list of peers to disk.'))
    logger.info('Flushing inventory in memory out to disk...')
    UISignalQueue.put((
        'updateStatusBar',
        'Flushing inventory in memory out to disk.'
        ' This should normally only take a second...'))
    Inventory().flush()

    # Verify that the objectProcessor has finished exiting. It should have
    # incremented the shutdown variable from 1 to 2. This must finish before
    # we command the sqlThread to exit.
    while state.shutdown == 1:
        time.sleep(.1)

    # Wait long enough to guarantee that any running proof of work worker
    # threads will check the shutdown variable and exit. If the main thread
    # closes before they do then they won't stop.
    time.sleep(.25)

    for thread in threading.enumerate():
        if (
            thread is not threading.currentThread()
            and isinstance(thread, StoppableThread)
            and thread.name != 'SQL'
        ):
            logger.debug("Waiting for thread %s", thread.name)
            thread.join()

    # This one last useless query will guarantee that the previous flush
    # committed and that the
    # objectProcessorThread committed before we close the program.
    sqlQuery('SELECT address FROM subscriptions')
    logger.info('Finished flushing inventory.')
    sqlStoredProcedure('exit')

    # flush queues
    for queue in (
            workerQueue, UISignalQueue, addressGeneratorQueue,
            objectProcessorQueue):
        while True:
            try:
                queue.get(False)
                queue.task_done()
            except Queue.Empty:
                break

    # Log knownnodes/outages/multiport statistics
    dupes = {}
    nodes_counter = 0
    for stream in knownnodes.knownNodes.itervalues():
        for peer in stream:
            nodes_counter += 1
            dup = dupes.get(peer.host)
            port = str(peer.port)
            if dup:
                dupes[peer.host].append(port)
            else:
                dupes[peer.host] = [port]

    dup_counter = 0
    max_ports = (1, '')
    for dup, ports in dupes.iteritems():
        ports_len = len(ports)
        if ports_len > 1:
            dup_counter += 1
            if ports_len > max_ports[0]:
                max_ports = (ports_len, dup)
            logger.warning(
                'Multiport host: %s, ports: %s',
                dup, ', '.join(ports))
    logger.warning(
        'Knownnodes len: %s, outages: %s, multiport: %s',
        nodes_counter, len(knownnodes.outages), dup_counter)
    if max_ports[0] > 0:
        logger.warning(
            'Maximum number of ports %s - %s', *max_ports)

    if state.thisapp.daemon or not state.enableGUI:
        logger.info('Clean shutdown complete.')
        state.thisapp.cleanup()
        os._exit(0)  # pylint: disable=protected-access
    else:
        logger.info('Core shutdown complete.')
    for thread in threading.enumerate():
        logger.debug('Thread %s still running', thread.name)
