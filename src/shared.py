from __future__ import division

# Libraries.
import os
import sys
import stat
import threading
import hashlib
import subprocess
from binascii import hexlify, unhexlify
from pyelliptic import arithmetic, Cipher

# Project imports.
import state
import highlevelcrypto
from bmconfigparser import BMConfigParser
from debug import logger
from addresses import decodeAddress, encodeVarint
from helper_sql import sqlQuery

try:
    from plugins.plugin import get_plugin
except ImportError:
    get_plugin = False

verbose = 1
# This is obsolete with the change to protocol v3
# but the singleCleaner thread still hasn't been updated
# so we need this a little longer.
maximumAgeOfAnObjectThatIAmWillingToAccept = 216000
# Equals 4 weeks. You could make this longer if you want
# but making it shorter would not be advisable because
# there is a very small possibility that it could keep you
# from obtaining a needed pubkey for a period of time.
lengthOfTimeToHoldOnToAllPubkeys = 2419200
maximumAgeOfNodesThatIAdvertiseToOthers = 10800  # Equals three hours


myECCryptorObjects = {}
MyECSubscriptionCryptorObjects = {}
# The key in this dictionary is the RIPE hash which is encoded
# in an address and value is the address itself.
myAddressesByHash = {}
# The key in this dictionary is the tag generated from the address.
myAddressesByTag = {}
broadcastSendersForWhichImWatching = {}
printLock = threading.Lock()
statusIconColor = 'red'

thisapp = None  # singleton lock instance

ackdataForWhichImWatching = {}
# used by API command clientStatus
clientHasReceivedIncomingConnections = False
numberOfMessagesProcessed = 0
numberOfBroadcastsProcessed = 0
numberOfPubkeysProcessed = 0

maximumLengthOfTimeToBotherResendingMessages = 0


def isAddressInMyAddressBook(address):
    queryreturn = sqlQuery(
        '''select address from addressbook where address=?''',
        address)
    return queryreturn != []


# At this point we should really just have a isAddressInMy(book, address)...
def isAddressInMySubscriptionsList(address):
    queryreturn = sqlQuery(
        '''select * from subscriptions where address=?''',
        str(address))
    return queryreturn != []


def isAddressInMyAddressBookSubscriptionsListOrWhitelist(address):
    if isAddressInMyAddressBook(address):
        return True

    queryreturn = sqlQuery(
        '''SELECT address FROM whitelist where address=?'''
        ''' and enabled = '1' ''',
        address)
    if queryreturn != []:
        return True

    queryreturn = sqlQuery(
        '''select address from subscriptions where address=?'''
        ''' and enabled = '1' ''',
        address)
    if queryreturn != []:
        return True
    return False


def decodeWalletImportFormat(WIFstring):
    fullString = arithmetic.changebase(WIFstring, 58, 256)
    privkey = fullString[:-4]
    if fullString[-4:] != \
       hashlib.sha256(hashlib.sha256(privkey).digest()).digest()[:4]:
        logger.critical(
            'Major problem! When trying to decode one of your'
            ' private keys, the checksum failed. Here are the first'
            ' 6 characters of the PRIVATE key: %s',
            str(WIFstring)[:6]
        )
        os._exit(0)
        # return ""
    elif privkey[0] == '\x80':  # checksum passed
        return privkey[1:]

    logger.critical(
        'Major problem! When trying to decode one of your  private keys,'
        ' the checksum passed but the key doesn\'t begin with hex 80.'
        ' Here is the PRIVATE key: %s', WIFstring
    )
    os._exit(0)


class Keystore(object):
    """Class implementing common key storage workflow"""
    def __init__(self):
        self.config = BMConfigParser()
        keysencrypted = self.config.safeGetBoolean(
            'bitmessagesettings', 'keysencrypted')

        def noop(key):
            return key

        self.fetch = self._get_key
        self.push = self._set_keys
        self.encrypt = self.decrypt = noop

        try:
            content, plugin = self.config.safeGet(
                'bitmessagesettings', 'keystore').split(':')
            plugin = get_plugin('keystore', name=plugin)(self)
        except (ValueError, TypeError):
            plugin = None

        if not plugin:
            if keysencrypted:
                logger.warning(
                    'Key encryption plugin not found or unimplemented!')
            return

        try:
            if content == 'password' and keysencrypted:
                self.decrypt = plugin.decrypt
                self.encrypt = plugin.encrypt
            elif content == 'keys':
                self.fetch = plugin.fetch
                self.push = plugin.push
        except AttributeError:
            pass

    def fetch_key(self, address, key_type='privencryptionkey'):
        """Fetch address key of type key_type from keystore"""
        try:
            return hexlify(decodeWalletImportFormat(
                self.decrypt(self.fetch(address, key_type))
            ))
        except TypeError:
            pass  # handle in reloadMyAddressHashes etc

    def push_keys(self, address, keys):
        """Push the address keys in WIF into keystore"""
        self.push(address, [self.encrypt(key) for key in keys])

    def _get_key(self, address, key_type='privencryptionkey'):
        return self.config.get(address, key_type)

    def _set_keys(self, address, keys):
        for key, key_type in zip(
                keys, ('privencryptionkey', 'privsigningkey')):
            self.config.set(address, key_type, key)
        self.config.save()

    # simmetric encryption from pyelliptic example:
    # https://github.com/yann2192/pyelliptic
    def _encrypt_AES_CFB(self, data, password):
        nonce = Cipher.gen_IV('aes-256-cfb')
        ctx = Cipher(password, nonce, 1, ciphername='aes-256-cfb')
        encrypted = ctx.update(data)
        encrypted += ctx.final()
        return ':'.join(hexlify(i) for i in (encrypted, nonce))

    def _decrypt_AES_CFB(self, data, password):
        encrypted, nonce = [unhexlify(part) for part in data.split(':')]
        ctx = Cipher(password, nonce, 0, ciphername='aes-256-cfb')
        return ctx.ciphering(encrypted)


keystore = Keystore()


def reloadMyAddressHashes():
    logger.debug('reloading keys from keys.dat file')
    myECCryptorObjects.clear()
    myAddressesByHash.clear()
    myAddressesByTag.clear()
    # myPrivateKeys.clear()

    keyfileSecure = checkSensitiveFilePermissions(state.appdata + 'keys.dat')
    hasEnabledKeys = False
    for addressInKeysFile in BMConfigParser().addresses():
        isEnabled = BMConfigParser().getboolean(addressInKeysFile, 'enabled')
        if isEnabled:
            hasEnabledKeys = True
            # status
            _, addressVersionNumber, streamNumber, hash = \
                decodeAddress(addressInKeysFile)
            if addressVersionNumber in (2, 3, 4):
                # Returns a simple 32 bytes of information encoded
                # in 64 Hex characters, or null if there was an error.
                privEncryptionKey = keystore.fetch_key(addressInKeysFile)

                # It is 32 bytes encoded as 64 hex characters
                if len(privEncryptionKey) == 64:
                    myECCryptorObjects[hash] = \
                        highlevelcrypto.makeCryptor(privEncryptionKey)
                    myAddressesByHash[hash] = addressInKeysFile
                    tag = hashlib.sha512(hashlib.sha512(
                        encodeVarint(addressVersionNumber) +
                        encodeVarint(streamNumber) + hash).digest()
                    ).digest()[32:]
                    myAddressesByTag[tag] = addressInKeysFile

            else:
                logger.error(
                    'Error in reloadMyAddressHashes: Can\'t handle'
                    ' address versions other than 2, 3, or 4.\n'
                )

    if not keyfileSecure:
        fixSensitiveFilePermissions(state.appdata + 'keys.dat', hasEnabledKeys)


def reloadBroadcastSendersForWhichImWatching():
    broadcastSendersForWhichImWatching.clear()
    MyECSubscriptionCryptorObjects.clear()
    queryreturn = sqlQuery('SELECT address FROM subscriptions where enabled=1')
    logger.debug('reloading subscriptions...')
    for row in queryreturn:
        address, = row
        # status
        _, addressVersionNumber, streamNumber, hash = decodeAddress(address)
        if addressVersionNumber == 2:
            broadcastSendersForWhichImWatching[hash] = 0
        # Now, for all addresses, even version 2 addresses,
        # we should create Cryptor objects in a dictionary which we will
        # use to attempt to decrypt encrypted broadcast messages.

        if addressVersionNumber <= 3:
            privEncryptionKey = hashlib.sha512(
                encodeVarint(addressVersionNumber) +
                encodeVarint(streamNumber) + hash
            ).digest()[:32]
            MyECSubscriptionCryptorObjects[hash] = \
                highlevelcrypto.makeCryptor(hexlify(privEncryptionKey))
        else:
            doubleHashOfAddressData = hashlib.sha512(hashlib.sha512(
                encodeVarint(addressVersionNumber) +
                encodeVarint(streamNumber) + hash
            ).digest()).digest()
            tag = doubleHashOfAddressData[32:]
            privEncryptionKey = doubleHashOfAddressData[:32]
            MyECSubscriptionCryptorObjects[tag] = \
                highlevelcrypto.makeCryptor(hexlify(privEncryptionKey))


def fixPotentiallyInvalidUTF8Data(text):
    try:
        unicode(text, 'utf-8')
        return text
    except:
        return 'Part of the message is corrupt. The message cannot be' \
           ' displayed the normal way.\n\n' + repr(text)


# Checks sensitive file permissions for inappropriate umask
# during keys.dat creation. (Or unwise subsequent chmod.)
#
# Returns true iff file appears to have appropriate permissions.
def checkSensitiveFilePermissions(filename):
    if sys.platform == 'win32':
        # TODO: This might deserve extra checks by someone familiar with
        # Windows systems.
        return True
    elif sys.platform[:7] == 'freebsd':
        # FreeBSD file systems are the same as major Linux file systems
        present_permissions = os.stat(filename)[0]
        disallowed_permissions = stat.S_IRWXG | stat.S_IRWXO
        return present_permissions & disallowed_permissions == 0
    else:
        try:
            # Skip known problems for non-Win32 filesystems
            # without POSIX permissions.
            fstype = subprocess.check_output(
                'stat -f -c "%%T" %s' % (filename),
                shell=True,
                stderr=subprocess.STDOUT
            )
            if 'fuseblk' in fstype:
                logger.info(
                    'Skipping file permissions check for %s.'
                    ' Filesystem fuseblk detected.', filename)
                return True
        except:
            # Swallow exception here, but we might run into trouble later!
            logger.error('Could not determine filesystem type. %s', filename)
        present_permissions = os.stat(filename)[0]
        disallowed_permissions = stat.S_IRWXG | stat.S_IRWXO
        return present_permissions & disallowed_permissions == 0


# Fixes permissions on a sensitive file.
def fixSensitiveFilePermissions(filename, hasEnabledKeys):
    if hasEnabledKeys:
        logger.warning(
            'Keyfile had insecure permissions, and there were enabled'
            ' keys. The truly paranoid should stop using them immediately.')
    else:
        logger.warning(
            'Keyfile had insecure permissions, but there were no enabled keys.'
        )
    try:
        present_permissions = os.stat(filename)[0]
        disallowed_permissions = stat.S_IRWXG | stat.S_IRWXO
        allowed_permissions = ((1 << 32) - 1) ^ disallowed_permissions
        new_permissions = (
            allowed_permissions & present_permissions)
        os.chmod(filename, new_permissions)

        logger.info('Keyfile permissions automatically fixed.')

    except Exception:
        logger.exception('Keyfile permissions could not be fixed.')
        raise


def openKeysFile():
    if 'linux' in sys.platform:
        subprocess.call(["xdg-open", state.appdata + 'keys.dat'])
    else:
        os.startfile(state.appdata + 'keys.dat')
