"""
Test the alternatives for crypto primitives
"""

import hashlib
import time
import unittest
from abc import ABCMeta, abstractmethod
from binascii import hexlify, unhexlify
from struct import pack

from pybitmessage import highlevelcrypto, protocol
from pybitmessage.pyelliptic import arithmetic
from pybitmessage.addresses import (
    calculateInventoryHash, decodeAddress, decodeVarint, encodeVarint
)

try:
    from Crypto.Hash import RIPEMD
except ImportError:
    RIPEMD = None


# These keys are from addresses test script
sample_pubsigningkey = unhexlify(
    '044a367f049ec16cb6b6118eb734a9962d10b8db59c890cd08f210c43ff08bdf09d'
    '16f502ca26cd0713f38988a1237f1fc8fa07b15653c996dc4013af6d15505ce')
sample_pubencryptionkey = unhexlify(
    '044597d59177fc1d89555d38915f581b5ff2286b39d022ca0283d2bdd5c36be5d3c'
    'e7b9b97792327851a562752e4b79475d1f51f5a71352482b241227f45ed36a9')
sample_privatesigningkey = \
    '93d0b61371a54b53df143b954035d612f8efa8a3ed1cf842c2186bfd8f876665'
sample_privateencryptionkey = \
    '4b0b73a54e19b059dc274ab69df095fe699f43b17397bca26fdf40f4d7400a3a'
sample_ripe = '003cd097eb7f35c87b5dc8b4538c22cb55312a9f'
# stream: 1, version: 2
sample_address = 'BM-onkVu1KKL2UaUss5Upg9vXmqd3esTmV79'

sample_time = 1602927067
sample_sig = unhexlify(
    '30440220744286c66a885f0d0b30f6b07e5f8c6735fc83a2e87340d37ae90e95793539080'
    '22065aa3deddcbcd909a10272d7d0ba1f02f5abb358aa55225d4213a67d19f70880')

_sha = hashlib.new('sha512')
_sha.update(sample_pubsigningkey + sample_pubencryptionkey)

pubkey_sha = _sha.digest()


class RIPEMD160TestCase(object):
    """Base class for RIPEMD160 test case"""
    # pylint: disable=too-few-public-methods,no-member
    __metaclass__ = ABCMeta

    @abstractmethod
    def _hashdigest(self, data):
        """RIPEMD160 digest implementation"""
        pass

    def test_hash_string(self):
        """Check RIPEMD160 hash function on string"""
        self.assertEqual(hexlify(self._hashdigest(pubkey_sha)), sample_ripe)


class TestHashlib(RIPEMD160TestCase, unittest.TestCase):
    """RIPEMD160 test case for hashlib"""
    @staticmethod
    def _hashdigest(data):
        hasher = hashlib.new('ripemd160')
        hasher.update(data)
        return hasher.digest()


@unittest.skipUnless(RIPEMD, 'pycrypto package not found')
class TestCrypto(RIPEMD160TestCase, unittest.TestCase):
    """RIPEMD160 test case for Crypto"""
    @staticmethod
    def _hashdigest(data):
        return RIPEMD.RIPEMD160Hash(data).digest()


class TestAddresses(unittest.TestCase):
    """Test addresses manipulations"""
    def test_privtopub(self):
        """Generate public keys and check the result"""
        hexsig = hexlify(sample_pubsigningkey)
        self.assertEqual(hexsig, arithmetic.privtopub(sample_privatesigningkey))
        self.assertEqual(
            hexsig, highlevelcrypto.privToPub(sample_privatesigningkey))
        hexenc = hexlify(sample_pubencryptionkey)
        self.assertEqual(hexenc, arithmetic.privtopub(sample_privateencryptionkey))
        self.assertEqual(
            hexenc, highlevelcrypto.privToPub(sample_privateencryptionkey))

    def test_address(self):
        """Create address and check the result"""
        from pybitmessage import addresses
        from pybitmessage.fallback import RIPEMD160Hash

        sha = hashlib.new('sha512')
        sha.update(sample_pubsigningkey + sample_pubencryptionkey)
        ripe_hash = RIPEMD160Hash(sha.digest()).digest()
        self.assertEqual(ripe_hash, unhexlify(sample_ripe))

        self.assertEqual(
            addresses.encodeAddress(2, 1, ripe_hash), sample_address)

        self.assertEqual(
            addresses.decodeAddress(sample_address),
            ('success', 2, 1, ripe_hash))

    def test_pubkey(self):
        """Create and validate the pubkey object"""
        # Assemble
        payload = pack('>Q', sample_time + 28 * 24 * 3600)
        payload += '\x00\x00\x00\x01'  # object type: pubkey
        # address version 3, stream 1
        payload += encodeVarint(3) + encodeVarint(1)
        payload += protocol.getBitfield(sample_address)
        payload += sample_pubsigningkey[1:] + sample_pubencryptionkey[1:]
        # noncetrialsperbyte, payloadlengthextrabytes
        diff_parameter = encodeVarint(1000)
        payload += diff_parameter + diff_parameter
        signature = highlevelcrypto.sign(payload, sample_privatesigningkey)
        print('sig: %r' % hexlify(signature))
        payload += encodeVarint(len(signature)) + signature

        # Check
        readPosition = 12
        readPosition += decodeVarint(
            payload[readPosition:readPosition + 10])[1]
        readPosition += decodeVarint(
            payload[readPosition:readPosition + 10])[1]
        readPosition += 4
        pubsigningkey = '\x04' + payload[readPosition:readPosition + 64]
        self.assertEqual(pubsigningkey, sample_pubsigningkey)
        readPosition += 64
        pubencryptionkey = '\x04' + payload[readPosition:readPosition + 64]
        self.assertEqual(pubencryptionkey, sample_pubencryptionkey)
        readPosition += 64
        readPosition += decodeVarint(
            payload[readPosition:readPosition + 10])[1]
        readPosition += decodeVarint(
            payload[readPosition:readPosition + 10])[1]
        endOfSignedDataPosition = readPosition
        # Signature
        signatureLength, signatureLengthLength = decodeVarint(
            payload[readPosition:readPosition + 10])
        readPosition += signatureLengthLength
        signature = payload[readPosition:readPosition + signatureLength]
        self.assertTrue(
            highlevelcrypto.verify(
                payload[:endOfSignedDataPosition],
                signature, hexlify(pubsigningkey)))
        self.assertTrue(
            highlevelcrypto.verify(
                payload[:endOfSignedDataPosition],
                sample_sig, hexlify(pubsigningkey)))
