import Queue
import collections
import multiprocessing
import struct
import sys
import threading
import time

import dumbsolver
import fastsolver
import forkingsolver
import gpusolver
import utils

timeout = .5

class Stop(Exception):
    pass

class Task(object):
    previous = None
    next = None

    def __init__(self, headlessPayload, TTL, expiryTime, target, difficulty):
        self.headlessPayload = headlessPayload
        self.TTL = TTL
        self.expiryTime = expiryTime
        self.target = target
        self.difficulty = difficulty

Status = collections.namedtuple("Status", ["solverName", "solverStatus", "speed", "tasksCount", "difficulty"])

# Only one instance allowed

class WorkProver(threading.Thread):
    # Seed must be 32 bytes

    def __init__(self, codePath, seed, statusUpdated, resultsQueue):
        super(self.__class__, self).__init__()

        self.availableSolvers = {
            "dumb": dumbsolver.DumbSolver(codePath)
        }

        # Comment from the previous version:

        # on my (Peter Surda) Windows 10, Windows Defender
        # does not like this and fights with PyBitmessage
        # over CPU, resulting in very slow PoW
        # added on 2015-11-29: multiprocesing.freeze_support() doesn't help

        if not hasattr(sys, "frozen") or sys.frozen == "macosx_app":
            self.availableSolvers["forking"] = forkingsolver.ForkingSolver(codePath)

        try:
            self.availableSolvers["fast"] = fastsolver.FastSolver(codePath)
        except fastsolver.FastSolverError:
            pass

        try:
            self.availableSolvers["gpu"] = gpusolver.GPUSolver(codePath)
        except gpusolver.GPUSolverError:
            pass

        try:
            self.defaultParallelism = multiprocessing.cpu_count()
        except NotImplementedError:
            self.defaultParallelism = 1

        self.seed = seed
        self.roundsCounter = 0
        self.statusUpdated = statusUpdated

        self.commandsQueue = Queue.Queue()

        if resultsQueue is None:
            self.resultsQueue = Queue.Queue()
        else:
            self.resultsQueue = resultsQueue

        self.solverName = None
        self.solver = None

        self.lastTime = utils.getTimePoint()
        self.timedIntervals = collections.deque()
        self.speed = 0
        self.totalDifficulty = 0

        self.tasks = {}
        self.currentTaskID = None

    def notifyStatus(self):
        if self.statusUpdated is None:
            return

        status = None

        if self.solver is not None:
            status = self.solver.status

        self.statusUpdated(Status(self.solverName, status, self.speed, len(self.tasks), self.totalDifficulty))

    def setSolver(self, name, configuration):
        try:
            if name is None and self.solverName is None:
                pass
            elif name == self.solverName:
                self.solver.setConfiguration(configuration)
            else:
                if self.solver is not None:
                    self.solver.setConfiguration(None)
                    self.solverName = None
                    self.solver = None

                if name is not None:
                    if name not in self.availableSolvers:
                        name, configuration = "dumb", None

                    self.solverName = name
                    self.solver = self.availableSolvers[name]
                    self.solver.setConfiguration(configuration)
        except gpusolver.GPUSolverError:
            self.solverName = None
            self.solver = None

            self.resultsQueue.put(("GPUError", ))

        self.notifyStatus()

    def updateSpeed(self, iterationsCount):
        currentTime = utils.getTimePoint()
        duration = currentTime - self.lastTime
        self.lastTime = currentTime

        self.timedIntervals.append((currentTime, iterationsCount, duration))

        for i in xrange(len(self.timedIntervals)):
            time, iterationsCount, duration = self.timedIntervals[0]

            if time + duration < currentTime - 3:
                self.timedIntervals.popleft()

        totalDuration = 0
        totalIterationsCount = 0

        for time, iterationsCount, duration in self.timedIntervals:
            totalIterationsCount += iterationsCount
            totalDuration += duration

        if totalDuration < .25:
            self.speed = 0
        else:
            self.speed = totalIterationsCount / totalDuration

        self.notifyStatus()

    def addTask(self, ID, headlessPayload, TTL, expiryTime, byteDifficulty, lengthExtension):
        target, difficulty = utils.calculateTarget(8 + 8 + len(headlessPayload), TTL, byteDifficulty, lengthExtension)

        task = Task(headlessPayload, TTL, expiryTime, target, difficulty)

        self.tasks[ID] = task
        self.totalDifficulty += difficulty

        if self.currentTaskID is None:
            task.previous = ID
            task.next = ID

            self.currentTaskID = ID
        else:
            task.previous = self.currentTaskID
            task.next = self.tasks[self.currentTaskID].next

            self.tasks[task.previous].next = ID
            self.tasks[task.next].previous = ID

        self.notifyStatus()

    def cancelTask(self, ID):
        if ID not in self.tasks:
            return

        task = self.tasks.pop(ID)
        self.totalDifficulty -= task.difficulty

        if len(self.tasks) == 0:
            self.currentTaskID = None
        else:
            self.tasks[task.previous].next = task.next
            self.tasks[task.next].previous = task.previous

            if self.currentTaskID == ID:
                self.currentTaskID = task.next

        self.notifyStatus()

    def nextTask(self):
        self.currentTaskID = self.tasks[self.currentTaskID].next

    def shutdown(self):
        self.setSolver(None, None)

        for i in self.tasks.keys():
            self.cancelTask(i)

        raise Stop()

    def processCommand(self, command, *arguments):
        getattr(self, command)(*arguments)

    def round(self):
        while True:
            try:
                self.processCommand(*self.commandsQueue.get_nowait())
            except Queue.Empty:
                break

        while self.solver is None or self.currentTaskID is None:
            try:
                self.processCommand(*self.commandsQueue.get(True, timeout))
            except Queue.Empty:
                self.updateSpeed(0)

        task = self.tasks[self.currentTaskID]

        if task.expiryTime is None:
            expiryTime = int(time.time() + task.TTL)
        else:
            expiryTime = task.expiryTime

        initialPayload = struct.pack(">Q", expiryTime) + task.headlessPayload
        initialHash = utils.calculateInitialHash(initialPayload)

        appendedSeed = self.seed + struct.pack(">Q", self.roundsCounter)
        self.roundsCounter += 1

        try:
            nonce, iterationsCount = self.solver.search(initialHash, task.target, appendedSeed, timeout)
        except gpusolver.GPUSolverError:
            self.setSolver(None, None)

            self.resultsQueue.put(("GPUError", ))

            nonce, iterationsCount = None, 0

        self.updateSpeed(iterationsCount)

        if nonce is None:
            self.nextTask()
        else:
            self.resultsQueue.put(("taskDone", self.currentTaskID, nonce, expiryTime))

            self.cancelTask(self.currentTaskID)

    def run(self):
        try:
            while True:
                self.round()
        except Stop:
            return
        except Exception as exception:
            self.resultsQueue.put(exception)
