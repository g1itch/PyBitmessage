import binascii
import collections
import hashlib
import os.path
import struct
import threading
import time

import addresses
import bmconfigparser
import debug
import defaults
import helper_msgcoding
import helper_sql
import helper_random
import helper_threading
import highlevelcrypto
import inventory
import l10n
import paths
import protocol
import shared
import state
import tr
import queues
import workprover

# Message status flow:
#
# +----------------------------------------------------------------------------------------+
# v                                                                                        |
# +-> msgqueued -+---------------------------------------->+-+-> doingmsgpow -+-> msgsent -+-> ackreceived
# ^              |                                         ^ |                |
# |              +-> awaitingpubkey -+-> doingpubkeypow -+ | |                +-> msgsentnoackexpected
# |              ^                   v                   | | |                |
# +--------------+-------------------+-------------------+ | |                +-> badkey
#                                                          | |
#                                                          | +-> toodifficult --> forcepow -+
#                                                          |                                |
#                                                          +--------------------------------+

# Broadcast status flow:
#
# broadcastqueued --> doingbroadcastpow --> broadcastsent

# TODO: queued pubkey messages are not saved to the database, they disappear when the client is closed

AddressProperties = collections.namedtuple("AddressProperties", [
    "version", "stream", "ripe",
    "own", "chan", "bitfield", "byteDifficulty", "lengthExtension",
    "secretSigningKey", "secretEncryptionKey", "publicSigningKey", "publicEncryptionKey"
])

def getMyAddressProperties(address, defaultDifficulty = False):
    status, version, stream, ripe = addresses.decodeAddress(address)

    if defaultDifficulty:
        byteDifficulty = defaults.networkDefaultProofOfWorkNonceTrialsPerByte
        lengthExtension = defaults.networkDefaultPayloadLengthExtraBytes
    else:
        byteDifficulty = bmconfigparser.BMConfigParser().safeGetInt(address, "noncetrialsperbyte", None)
        lengthExtension = bmconfigparser.BMConfigParser().safeGetInt(address, "payloadlengthextrabytes", None)

    chan = bmconfigparser.BMConfigParser().safeGetBoolean(address, "chan")
    bitfield = 0

    if not bmconfigparser.BMConfigParser().safeGetBoolean(address, "dontsendack"):
        bitfield |= protocol.BITFIELD_DOESACK

    secretSigningKeyBase58 = bmconfigparser.BMConfigParser().get(address, "privsigningkey")
    secretEncryptionKeyBase58 = bmconfigparser.BMConfigParser().get(address, "privencryptionkey")

    secretSigningKey = shared.decodeWalletImportFormat(secretSigningKeyBase58)
    secretEncryptionKey = shared.decodeWalletImportFormat(secretEncryptionKeyBase58)

    publicSigningKey = binascii.unhexlify(highlevelcrypto.privToPub(binascii.hexlify(secretSigningKey)))
    publicEncryptionKey = binascii.unhexlify(highlevelcrypto.privToPub(binascii.hexlify(secretEncryptionKey)))

    return AddressProperties(
        version, stream, ripe,
        True, chan, bitfield, byteDifficulty, lengthExtension,
        secretSigningKey, secretEncryptionKey, publicSigningKey, publicEncryptionKey
    )

def parsePubkeyMessage(encoded):
    readPosition = 0

    version, readLength = addresses.decodeVarint(encoded[readPosition: readPosition + 9])
    readPosition += readLength

    stream, readLength = addresses.decodeVarint(encoded[readPosition: readPosition + 9])
    readPosition += readLength

    bitfield, = struct.unpack(">I", encoded[readPosition: readPosition + 4])
    readPosition += 4

    publicSigningKey = "\x04" + encoded[readPosition: readPosition + 64]
    readPosition += 64

    publicEncryptionKey = "\x04" + encoded[readPosition: readPosition + 64]
    readPosition += 64

    ripe = protocol.calculateRipeHash(publicSigningKey + publicEncryptionKey)

    if version < 3:
        byteDifficulty = defaults.networkDefaultProofOfWorkNonceTrialsPerByte
        lengthExtension = defaults.networkDefaultPayloadLengthExtraBytes
    else:
        byteDifficulty, readLength = addresses.decodeVarint(encoded[readPosition: readPosition + 9])
        readPosition += readLength

        lengthExtension, readLength = addresses.decodeVarint(encoded[readPosition: readPosition + 9])
        readPosition += readLength

        byteDifficulty = max(defaults.networkDefaultProofOfWorkNonceTrialsPerByte, byteDifficulty)
        lengthExtension = max(defaults.networkDefaultPayloadLengthExtraBytes, lengthExtension)

    return AddressProperties(
        version, stream, ripe,
        False, False, bitfield, byteDifficulty, lengthExtension,
        None, None, publicSigningKey, publicEncryptionKey
    )

def getDestinationAddressProperties(address):
    # Search own and chan addresses

    try:
        return getMyAddressProperties(address, True)
    except:
        pass

    # Search the "pubkeys" table in the database

    status, version, stream, ripe = addresses.decodeAddress(address)

    if version == 4:
        secretEncryptionKey, tag = protocol.calculateAddressTag(version, stream, ripe)

        cryptor = highlevelcrypto.makeCryptor(binascii.hexlify(secretEncryptionKey))

        alreadyNeeded = tag in state.neededPubkeys
        state.neededPubkeys[tag] = address, cryptor
    else:
        alreadyNeeded = address in state.neededPubkeys
        state.neededPubkeys[address] = None

    helper_sql.sqlExecute("""UPDATE "pubkeys" SET "usedpersonally" = 'yes' WHERE "address" == ?;""", address)
    encodedPubkeys = helper_sql.sqlQuery("""SELECT "transmitdata" FROM "pubkeys" WHERE "address" == ?;""", address)

    result = None

    if len(encodedPubkeys) != 0:
        result = parsePubkeyMessage(encodedPubkeys[-1][0])

    # Search the inventory for encrypted keys

    if result is None and version == 4:
        for i in inventory.Inventory().by_type_and_tag(1, tag):
            encodedPubkey = protocol.decryptAndCheckV4Pubkey(i.payload, address, cryptor)

            if encodedPubkey is None:
                continue

            helper_sql.sqlExecute("""
                INSERT INTO "pubkeys" ("address", "addressversion", "transmitdata", "time", "usedpersonally")
                VALUES (?, 4, ?, ?, 'yes');
            """, address, encodedPubkey, int(time.time()))

            result = parsePubkeyMessage(encodedPubkey)

            break

    if result is not None:
        if version == 4:
            state.neededPubkeys.pop(tag, None)
        else:
            state.neededPubkeys.pop(address, None)

        helper_sql.sqlExecute("""
            UPDATE "sent" SET "status" = 'msgqueued'
            WHERE "status" IN ('doingpubkeypow', 'awaitingpubkey') AND "toaddress" == ? AND "folder" == 'sent';
        """, address)

        if alreadyNeeded:
            queues.workerQueue.put(("sendmessage", ))

        queued = helper_sql.sqlQuery("""
            SELECT "ackdata" FROM "sent"
            WHERE "status" == 'msgqueued' AND "toaddress" == ? AND "folder" == 'sent';
        """, address)

        for i, in queued:
            queues.UISignalQueue.put(("updateSentItemStatusByAckdata", (
                i,
                tr._translate(
                    "MainWindow",
                    "Queued."
                )
            )))

        return result

    return None

def randomizeTTL(TTL):
   return TTL + helper_random.randomrandrange(-300, 300)

def disseminateObject(nonce, expiryTime, headlessPayload, objectType, stream, tag):
    payload = nonce + struct.pack(">Q", expiryTime) + headlessPayload
    inventoryHash = protocol.calculateDoubleHash(payload)[: 32]

    inventory.Inventory()[inventoryHash] = objectType, stream, payload, expiryTime, buffer(tag)
    queues.invQueue.put((stream, inventoryHash))

    debug.logger.info("Broadcasting inventory object with hash: %s", binascii.hexlify(inventoryHash))

    return inventoryHash, payload

class singleWorker(threading.Thread, helper_threading.StoppableThread):
    name = "singleWorker"

    def __init__(self):
        super(self.__class__, self).__init__()

        self.initStop()

    def stopThread(self):
        queues.workerQueue.put(("stopThread", "data"))

        super(self.__class__, self).stopThread()

    def run(self):
        GPUVendor = bmconfigparser.BMConfigParser().safeGet("bitmessagesettings", "opencl")

        self.workProver = workprover.WorkProver(
            os.path.join(paths.codePath(), "workprover"),
            GPUVendor,
            helper_random.randomBytes(32),
            lambda status: queues.UISignalQueue.put(("updateWorkProverStatus", status)),
            queues.workerQueue
        )

        self.workProver.start()

        parallelism = bmconfigparser.BMConfigParser().safeGetInt("bitmessagesettings", "maxcores")

        if parallelism is None:
            parallelism = self.workProver.defaultParallelism

        if "gpu" in self.workProver.availableSolvers and GPUVendor is not None:
            self.workProver.commandsQueue.put(("setSolver", "gpu", None))
        elif "fast" in self.workProver.availableSolvers:
            self.workProver.commandsQueue.put(("setSolver", "fast", parallelism))
        elif "forking" in self.workProver.availableSolvers:
            self.workProver.commandsQueue.put(("setSolver", "forking", parallelism))
        else:
            self.workProver.commandsQueue.put(("setSolver", "dumb", None))

        if "fast" not in self.workProver.availableSolvers:
            queues.UISignalQueue.put(("updateStatusBar", (
                tr._translate(
                    "proofofwork",
                    "C PoW module unavailable. Please build it."
                ), 1
            )))

        self.startedWorks = {}

        # Give some time for the GUI to start
        # TODO: use a condition variable

        self.stop.wait(10)

        queues.workerQueue.put(("sendmessage", ))
        queues.workerQueue.put(("sendbroadcast", ))

        while state.shutdown == 0:
            queueItem = queues.workerQueue.get()
            command, arguments = queueItem[0], queueItem[1: ]

            if command == "sendmessage":
                self.sendMessages()
            elif command == "sendbroadcast":
                self.sendBroadcasts()
            elif command == "sendMyPubkey":
                self.sendMyPubkey(*arguments)
            elif command == "requestPubkey":
                self.requestPubkey(*arguments)
            elif command == "resetPoW":
                pass
            elif command == "taskDone":
                self.workDone(*arguments)
            elif command == "stopThread":
                self.workProver.commandsQueue.put(("shutdown", ))
                self.workProver.join()

                break

        debug.logger.info("Quitting...")

    def startWork(self, ID, headlessPayload, TTL, expiryTime, byteDifficulty, lengthExtension, logPrefix, callback):
        debug.logger.info(
            "%s Starting work %s, payload length = %s, TTL = %s",
            logPrefix, ID, 8 + 8 + len(headlessPayload), TTL
        )

        self.startedWorks[ID] = callback

        self.workProver.commandsQueue.put((
            "addTask", ID, headlessPayload, TTL, expiryTime,
            byteDifficulty, lengthExtension
        ))

    def workDone(self, ID, nonce, expiryTime):
        debug.logger.info("Found proof of work %s", ID)

        self.startedWorks[ID](nonce, expiryTime)

        del self.startedWorks[ID]

    def sendMyPubkey(self, address):
        ID = "pubkey", address

        if ID in self.startedWorks:
            return

        try:
            addressProperties = getMyAddressProperties(address)
        except Exception as exception:
            debug.logger.error("Could not get the properties of a requested address %s\n", exception)

            return

        if addressProperties.chan:
            debug.logger.info("This is a chan address. Not sending pubkey")

            return

        if addressProperties.version == 4:
            secretEncryptionKey, tag = protocol.calculateAddressTag(
                addressProperties.version,
                addressProperties.stream,
                addressProperties.ripe
            )

            publicEncryptionKey = highlevelcrypto.pointMult(secretEncryptionKey)
        else:
            tag = ""

        debug.logger.info("Sending pubkey of %s", address)

        TTL = randomizeTTL(28 * 24 * 60 * 60)

        if addressProperties.version > 2:
            expiryTime = int(time.time() + TTL)
        else:
            expiryTime = None

        headlessPayload = struct.pack(">I", 1)
        headlessPayload += addresses.encodeVarint(addressProperties.version)
        headlessPayload += addresses.encodeVarint(addressProperties.stream)

        inventoryTagPosition = len(headlessPayload)

        headlessPayload += tag

        if addressProperties.version == 4:
            plaintext = struct.pack(">I", addressProperties.bitfield)
            plaintext += addressProperties.publicSigningKey[1: ]
            plaintext += addressProperties.publicEncryptionKey[1: ]
            plaintext += addresses.encodeVarint(addressProperties.byteDifficulty)
            plaintext += addresses.encodeVarint(addressProperties.lengthExtension)

            signature = highlevelcrypto.sign(
                struct.pack(">Q", expiryTime) + headlessPayload + plaintext,
                binascii.hexlify(addressProperties.secretSigningKey)
            )

            plaintext += addresses.encodeVarint(len(signature))
            plaintext += signature

            headlessPayload += highlevelcrypto.encrypt(plaintext, binascii.hexlify(publicEncryptionKey))
        else:
            headlessPayload += struct.pack(">I", addressProperties.bitfield)
            headlessPayload += addressProperties.publicSigningKey[1: ]
            headlessPayload += addressProperties.publicEncryptionKey[1: ]

            if addressProperties.version == 3:
                headlessPayload += addresses.encodeVarint(addressProperties.byteDifficulty)
                headlessPayload += addresses.encodeVarint(addressProperties.lengthExtension)

                signature = highlevelcrypto.sign(
                    struct.pack(">Q", expiryTime) + headlessPayload,
                    binascii.hexlify(addressProperties.secretSigningKey)
                )

                headlessPayload += addresses.encodeVarint(len(signature))
                headlessPayload += signature

        def workDone(nonce, expiryTime):
            inventoryTag = headlessPayload[inventoryTagPosition: inventoryTagPosition + 32]

            disseminateObject(nonce, expiryTime, headlessPayload, 1, addressProperties.stream, inventoryTag)

            # TODO: not atomic with the addition to the inventory, the "lastpubkeysendtime" property should be removed
            # Instead check if the pubkey is present in the inventory

            try:
                bmconfigparser.BMConfigParser().set(address, "lastpubkeysendtime", str(int(time.time())))
                bmconfigparser.BMConfigParser().save()
            except:
                pass

            queues.UISignalQueue.put(("updateStatusBar", ""))

        self.startWork(
            ID, headlessPayload, TTL, expiryTime,
            defaults.networkDefaultProofOfWorkNonceTrialsPerByte,
            defaults.networkDefaultPayloadLengthExtraBytes,
            "(For pubkey version {} message)".format(addressProperties.version),
            workDone
        )

    def processBroadcast(self, address, subject, body, ackData, TTL, encoding):
        ID = "broadcast", ackData

        try:
            addressProperties = getMyAddressProperties(address)
        except:
            queues.UISignalQueue.put(("updateSentItemStatusByAckdata", (
                ackData,
                tr._translate(
                    "MainWindow",
                    "Error! Could not find sender address (your address) in the keys.dat file."
                )
            )))

            return

        if addressProperties.version < 2:
            debug.logger.error("Address version unsupported for broadcasts")

            return

        debug.logger.info("Sending broadcast from %s", address)

        if addressProperties.version == 4:
            secretEncryptionKey, tag = protocol.calculateAddressTag(
                addressProperties.version,
                addressProperties.stream,
                addressProperties.ripe
            )
        else:
            secretEncryptionKey = hashlib.sha512(
                addresses.encodeVarint(addressProperties.version) +
                addresses.encodeVarint(addressProperties.stream) +
                addressProperties.ripe
            ).digest()[: 32]

            tag = ""

        publicEncryptionKey = highlevelcrypto.pointMult(secretEncryptionKey)

        TTL = min(28 * 24 * 60 * 60, TTL)
        TTL = max(60 * 60, TTL)
        TTL = randomizeTTL(TTL)
        expiryTime = int(time.time() + TTL)

        headlessPayload = struct.pack(">I", 3)

        if addressProperties.version == 4:
            headlessPayload += addresses.encodeVarint(5)
        else:
            headlessPayload += addresses.encodeVarint(4)

        headlessPayload += addresses.encodeVarint(addressProperties.stream)

        inventoryTagPosition = len(headlessPayload)

        headlessPayload += tag

        plaintext = addresses.encodeVarint(addressProperties.version)
        plaintext += addresses.encodeVarint(addressProperties.stream)
        plaintext += struct.pack(">I", addressProperties.bitfield)
        plaintext += addressProperties.publicSigningKey[1: ]
        plaintext += addressProperties.publicEncryptionKey[1: ]

        if addressProperties.version >= 3:
            plaintext += addresses.encodeVarint(addressProperties.byteDifficulty)
            plaintext += addresses.encodeVarint(addressProperties.lengthExtension)

        encodedMessage = helper_msgcoding.MsgEncode({"subject": subject, "body": body}, encoding)

        plaintext += addresses.encodeVarint(encoding)
        plaintext += addresses.encodeVarint(encodedMessage.length)
        plaintext += encodedMessage.data

        signature = highlevelcrypto.sign(
            struct.pack(">Q", expiryTime) + headlessPayload + plaintext,
            binascii.hexlify(addressProperties.secretSigningKey)
        )

        plaintext += addresses.encodeVarint(len(signature))
        plaintext += signature

        headlessPayload += highlevelcrypto.encrypt(plaintext, binascii.hexlify(publicEncryptionKey))

        if len(headlessPayload) > 2 ** 18 - (8 + 8): # 256 kiB
            debug.logger.critical(
                "This broadcast object is too large to send. This should never happen. Object size: %s",
                len(headlessPayload)
            )

            return

        def workDone(nonce, expiryTime):
            inventoryTag = headlessPayload[inventoryTagPosition: inventoryTagPosition + 32]

            # TODO: adding to the inventory, adding to inbox and setting the sent status should be within a single SQL transaction

            inventoryHash, payload = disseminateObject(
                nonce, expiryTime, headlessPayload,
                3, addressProperties.stream, inventoryTag
            )

            helper_sql.sqlExecute("""
                UPDATE "sent" SET "msgid" = ?, "status" = 'broadcastsent', "lastactiontime" = ?
                WHERE "ackdata" == ?;
            """, inventoryHash, int(time.time()), ackData)

            queues.UISignalQueue.put(("updateSentItemStatusByAckdata", (
                ackData,
                tr._translate("MainWindow", "Broadcast sent on %1").arg(l10n.formatTimestamp())
            )))

            # Add to own inbox

            if addressProperties.version == 4:
                if tag in shared.MyECSubscriptionCryptorObjects:
                    queues.objectProcessorQueue.put((3, payload))
            else:
                if addressProperties.ripe in shared.MyECSubscriptionCryptorObjects:
                    queues.objectProcessorQueue.put((3, payload))

        helper_sql.sqlExecute("""UPDATE "sent" SET "status" = 'doingbroadcastpow' WHERE "ackdata" == ?;""", ackData)

        queues.UISignalQueue.put(("updateSentItemStatusByAckdata", (
            ackData,
            tr._translate(
                "MainWindow",
                "Doing work necessary to send broadcast."
            )
        )))

        self.startWork(
            ID, headlessPayload, TTL, expiryTime,
            defaults.networkDefaultProofOfWorkNonceTrialsPerByte,
            defaults.networkDefaultPayloadLengthExtraBytes,
            "(For broadcast message)",
            workDone
        )

    def sendBroadcasts(self):
        queued = helper_sql.sqlQuery("""
            SELECT "fromaddress", "subject", "message", "ackdata", "ttl", "encodingtype" FROM "sent"
            WHERE "status" == 'broadcastqueued' AND "folder" == 'sent';
        """)

        for i in queued:
            # Must be in a separate function because of the nested callback

            self.processBroadcast(*i)

    def generateAckMessage(self, ackData, stream, TTL, callback):
        ID = "ack", ackData

        # It might be perfectly fine to just use the same TTL for
        # the ackdata that we use for the message. But I would rather
        # it be more difficult for attackers to associate ackData with
        # the associated msg object. However, users would want the TTL
        # of the acknowledgement to be about the same as they set
        # for the message itself. So let's set the TTL of the
        # acknowledgement to be in one of three 'buckets': 1 hour, 7
        # days, or 28 days, whichever is relatively close to what the
        # user specified.

        if TTL < 24 * 60 * 60:
            TTL = 24 * 60 * 60
        elif TTL < 7 * 24 * 60 * 60:
            TTL = 7 * 24 * 60 * 60
        else:
            TTL = 28 * 24 * 60 * 60

        TTL = randomizeTTL(TTL)
        expiryTime = int(time.time() + TTL)

        def workDone(nonce, expiryTime):
            payload = nonce + struct.pack(">Q", expiryTime) + ackData

            callback(protocol.CreatePacket("object", payload))

        self.startWork(
            ID, ackData, TTL, expiryTime,
            defaults.networkDefaultProofOfWorkNonceTrialsPerByte,
            defaults.networkDefaultPayloadLengthExtraBytes,
            "(For ack message)",
            workDone
        )

    def processMessage(self, status, destination, source, subject, body, ackData, TTL, retryNumber, encoding):
        ID = "message", ackData

        helper_sql.sqlExecute("""UPDATE "sent" SET "status" = 'awaitingpubkey' WHERE "ackdata" == ?;""", ackData)

        destinationProperties = getDestinationAddressProperties(destination)

        if destinationProperties is None:
            queues.workerQueue.put(("requestPubkey", destination))

            queues.UISignalQueue.put(("updateSentItemStatusByAckdata", (
                ackData,
                tr._translate(
                    "MainWindow",
                    "Waiting for their encryption key. Will request it again soon."
                )
            )))

            return

        try:
            defaultDifficulty = shared.isAddressInMyAddressBookSubscriptionsListOrWhitelist(destination)

            if destinationProperties.own:
                defaultDifficulty = True

            sourceProperties = getMyAddressProperties(source, defaultDifficulty)
        except:
            queues.UISignalQueue.put(("updateSentItemStatusByAckdata", (
                ackData,
                tr._translate(
                    "MainWindow",
                    "Error! Could not find sender address (your address) in the keys.dat file."
                )
            )))

            return

        relativeByteDifficulty = (
            float(destinationProperties.byteDifficulty) /
            defaults.networkDefaultProofOfWorkNonceTrialsPerByte
        )

        relativeLengthExtension = (
            float(destinationProperties.lengthExtension) /
            defaults.networkDefaultPayloadLengthExtraBytes
        )

        if status != "forcepow":
            maximumByteDifficulty = bmconfigparser.BMConfigParser().getint(
                "bitmessagesettings", "maxacceptablenoncetrialsperbyte"
            )

            maximumLengthExtension = bmconfigparser.BMConfigParser().getint(
                "bitmessagesettings", "maxacceptablepayloadlengthextrabytes"
            )

            if (
                maximumByteDifficulty != 0 and destinationProperties.byteDifficulty > maximumLengthExtension or
                maximumLengthExtension != 0 and destinationProperties.lengthExtension > maximumLengthExtension
            ):
                helper_sql.sqlExecute("""UPDATE "sent" SET "status" = 'toodifficult' WHERE "ackdata" == ?;""", ackData)

                queues.UISignalQueue.put(("updateSentItemStatusByAckdata", (
                    ackData,
                    tr._translate(
                        "MainWindow",
                        "Problem: The work demanded by the recipient (%1 and %2) is "
                        "more difficult than you are willing to do. %3"
                    ).arg(str(relativeByteDifficulty)).arg(str(relativeLengthExtension)).arg(l10n.formatTimestamp())
                )))

                return

        debug.logger.info("Sending message from %s to %s", source, destination)

        TTL *= 2 ** retryNumber
        TTL = min(28 * 24 * 60 * 60, TTL)
        TTL = max(60 * 60, TTL)
        TTL = randomizeTTL(TTL)
        expiryTime = int(time.time() + TTL)

        def ackMessageGenerated(ackMessage):
            headlessPayload = struct.pack(">I", 2)
            headlessPayload += addresses.encodeVarint(1)
            headlessPayload += addresses.encodeVarint(destinationProperties.stream)

            plaintext = addresses.encodeVarint(sourceProperties.version)
            plaintext += addresses.encodeVarint(sourceProperties.stream)
            plaintext += struct.pack(">I", sourceProperties.bitfield)
            plaintext += sourceProperties.publicSigningKey[1: ]
            plaintext += sourceProperties.publicEncryptionKey[1: ]

            if sourceProperties.version >= 3:
                plaintext += addresses.encodeVarint(sourceProperties.byteDifficulty)
                plaintext += addresses.encodeVarint(sourceProperties.lengthExtension)

            plaintext += destinationProperties.ripe # To prevent resending a signed message to a different reciever

            encodedMessage = helper_msgcoding.MsgEncode({"subject": subject, "body": body}, encoding)

            plaintext += addresses.encodeVarint(encoding)
            plaintext += addresses.encodeVarint(encodedMessage.length)
            plaintext += encodedMessage.data

            if ackMessage is None:
                plaintext += addresses.encodeVarint(0)
            else:
                plaintext += addresses.encodeVarint(len(ackMessage))
                plaintext += ackMessage

            signature = highlevelcrypto.sign(
                struct.pack(">Q", expiryTime) + headlessPayload + plaintext,
                binascii.hexlify(sourceProperties.secretSigningKey)
            )

            plaintext += addresses.encodeVarint(len(signature))
            plaintext += signature

            try:
                ciphertext = highlevelcrypto.encrypt(
                    plaintext,
                    binascii.hexlify(destinationProperties.publicEncryptionKey)
                )
            except:
                helper_sql.sqlExecute("""UPDATE "sent" SET "status" = 'badkey' WHERE "ackdata" == ?;""", ackData)

                queues.UISignalQueue.put(("updateSentItemStatusByAckdata", (
                    ackData,
                    tr._translate(
                        "MainWindow",
                        "Problem: The recipient's encryption key is no good. Could not encrypt message. %1"
                    ).arg(l10n.formatTimestamp())
                )))

                return

            headlessPayload += ciphertext
            inventoryTag = ciphertext[: 32]

            if len(headlessPayload) > 2 ** 18 - (8 + 8): # 256 kiB
                debug.logger.critical(
                    "This message object is too large to send. This should never happen. Object size: %s",
                    len(headlessPayload)
                )

                return

            def workDone(nonce, expiryTime):
                if ackMessage is not None:
                    state.watchedAckData.add(ackData)

                #TODO: adding to the inventory, adding to inbox and setting the sent status should be within a single SQL transaction

                inventoryHash, payload = disseminateObject(
                    nonce, expiryTime, headlessPayload,
                    2, destinationProperties.stream, inventoryTag
                )

                if ackMessage is None:
                    newStatus = "msgsentnoackexpected"
                else:
                    newStatus = "msgsent"

                sleepTill = int(time.time() + TTL * 1.1)

                helper_sql.sqlExecute("""
                    UPDATE "sent" SET "msgid" = ?, "status" = ?, "retrynumber" = ?,
                        "sleeptill" = ?, "lastactiontime" = ?
                    WHERE "status" == 'doingmsgpow' AND "ackdata" == ?;
                """, inventoryHash, newStatus, retryNumber + 1, sleepTill, int(time.time()), ackData)

                # Add to own inbox

                if destinationProperties.own:
                    queues.objectProcessorQueue.put((2, payload))

                if ackMessage is None:
                    queues.UISignalQueue.put(("updateSentItemStatusByAckdata", (
                        ackData,
                        tr._translate(
                            "MainWindow",
                            "Message sent. Sent at %1"
                        ).arg(l10n.formatTimestamp())
                    )))
                else:
                    queues.UISignalQueue.put(("updateSentItemStatusByAckdata", (
                        ackData,
                        tr._translate(
                            "MainWindow",
                            "Message sent. Waiting for acknowledgement. Sent on %1"
                        ).arg(l10n.formatTimestamp())
                    )))

            self.startWork(
                ID, headlessPayload, TTL, expiryTime,
                destinationProperties.byteDifficulty,
                destinationProperties.lengthExtension,
                "(For message)",
                workDone
            )

        helper_sql.sqlExecute("""UPDATE "sent" SET "status" = 'doingmsgpow' WHERE "ackdata" == ?;""", ackData)

        if relativeByteDifficulty != 1 or relativeLengthExtension != 1:
            queues.UISignalQueue.put(("updateSentItemStatusByAckdata", (
                ackData,
                tr._translate(
                    "MainWindow",
                    "Doing work necessary to send message.\nReceiver's required difficulty: %1 and %2"
                ).arg(str(relativeByteDifficulty)).arg(str(relativeLengthExtension))
            )))
        else:
            queues.UISignalQueue.put(("updateSentItemStatusByAckdata", (
                ackData,
                tr._translate(
                    "MainWindow",
                    "Doing work necessary to send message."
                )
            )))

        if destinationProperties.own:
            debug.logger.info("Not bothering to include ack data because we are sending to ourselves or a chan")

            ackMessageGenerated(None)
        elif destinationProperties.bitfield & protocol.BITFIELD_DOESACK == 0:
            debug.logger.info("Not bothering to include ack data because the receiver said that they won't relay it anyway")

            ackMessageGenerated(None)
        else:
            self.generateAckMessage(ackData, destinationProperties.stream, TTL, ackMessageGenerated)

    def sendMessages(self):
        queued = helper_sql.sqlQuery("""
            SELECT "status", "toaddress", "fromaddress", "subject", "message",
                "ackdata", "ttl", "retrynumber", "encodingtype" FROM "sent"
            WHERE "status" IN ('msgqueued', 'forcepow') AND "folder" == 'sent';
        """)

        for i in queued:
            # Must be in a separate function because of the nested callback

            self.processMessage(*i)

    def requestPubkey(self, address):
        ID = "getpubkey", address

        if ID in self.startedWorks:
            return

        status, version, stream, ripe = addresses.decodeAddress(address)

        # Check if a request is already in the inventory

        if version == 4:
            secretEncryptionKey, tag = protocol.calculateAddressTag(version, stream, ripe)
        else:
            tag = ripe

        currentExpiryTime = None

        for i in inventory.Inventory().by_type_and_tag(0, tag):
            if currentExpiryTime is None:
                currentExpiryTime = i.expires
            else:
                currentExpiryTime = max(currentExpiryTime, i.expires)

        if currentExpiryTime is not None:
            helper_sql.sqlExecute("""
                UPDATE "sent" SET "status" = 'awaitingpubkey', "sleeptill" = ?
                WHERE "status" IN ('doingpubkeypow', 'awaitingpubkey') AND "toaddress" == ? AND "folder" == 'sent';
            """, currentExpiryTime, address)

            queues.UISignalQueue.put(("updateSentItemStatusByToAddress", (
                address,
                tr._translate(
                    "MainWindow",
                    "Waiting for their encryption key. Will request it again soon."
                )
            )))

            return

        debug.logger.info("Making request for version %s pubkey with tag: %s", version, binascii.hexlify(tag))

        TTL = randomizeTTL(28 * 24 * 60 * 60)

        headlessPayload = struct.pack(">I", 0)
        headlessPayload += addresses.encodeVarint(version)
        headlessPayload += addresses.encodeVarint(stream)

        headlessPayload += tag

        def workDone(nonce, expiryTime):
            # TODO: adding to the inventory and setting the sent status should be within a single SQL transaction

            disseminateObject(nonce, expiryTime, headlessPayload, 0, stream, tag)

            sleepTill = int(time.time() + TTL * 1.1)

            helper_sql.sqlExecute("""
                UPDATE "sent" SET "status" = 'awaitingpubkey', "sleeptill" = ?, "lastactiontime" = ?
                WHERE "status" IN ('doingpubkeypow', 'awaitingpubkey') AND "toaddress" == ? AND "folder" == 'sent';
            """, sleepTill, int(time.time()), address)

            queues.UISignalQueue.put(("updateSentItemStatusByToAddress", (
                address,
                tr._translate(
                    "MainWindow",
                    "Sending public key request. Waiting for reply. Requested at %1"
                ).arg(l10n.formatTimestamp())
            )))

        helper_sql.sqlExecute("""
            UPDATE "sent" SET "status" = 'doingpubkeypow'
            WHERE "status" == 'awaitingpubkey' AND "toaddress" == ? AND "folder" == 'sent';
        """, address)

        queues.UISignalQueue.put(("updateSentItemStatusByToAddress", (
            address,
            tr._translate(
                "MainWindow",
                "Doing work necessary to request encryption key."
            )
        )))

        self.startWork(
            ID, headlessPayload, TTL, None,
            defaults.networkDefaultProofOfWorkNonceTrialsPerByte,
            defaults.networkDefaultPayloadLengthExtraBytes,
            "(For getpubkey message)".format(version),
            workDone
        )