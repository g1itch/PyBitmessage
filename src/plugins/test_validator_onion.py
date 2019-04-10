import unittest

from pybitmessage.state import Peer

try:
    from validator_onion import OnionValidator
    validator_onion = True
except ImportError:
    validator_onion = False


@unittest.skipIf(not validator_onion, 'OnionValidator is not available')
class TestOnionValidator(unittest.TestCase):
    """Test case for OnionValidator"""
    @classmethod
    def setUpClass(cls):
        cls.check = OnionValidator()

    def test_valid(self):
        """Ensure validator returns True for valid nodes"""
        # not onion node
        self.assertTrue(self.check(Peer('5.45.99.75', 8444)))
        # default onion node
        self.assertTrue(self.check(Peer('quzwelsuziwqgpt2.onion', 8444)))

    def test_invalid(self):
        """Ensure validator returns False for invalid hostnames"""
        # is not base32
        self.assertFalse(self.check(Peer('test.onion', 8444)))
        # no descriptor
        self.assertFalse(self.check(Peer('aaaaaaaaaaaaaaaa.onion', 8444)))
