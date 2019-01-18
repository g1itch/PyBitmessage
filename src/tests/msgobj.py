"""Tests for messagetypes module"""

import unittest

import messagetypes


class TestMessagetypes(unittest.TestCase):
    """A test case for messagetypes"""
    _valid_msgdict = {"": "message", "subject": "subject", "body": "body"}
    _invalid_msgdict = {"": "vote", "msgid": "msgid"}

    def _test_msgObj(self, data):
        """Construct and process msg from dict"""
        msgObj = messagetypes.constructObject(data)
        if msgObj is None:
            self.fail("Failed to construct msg object")
        # Hope ERROR will be sufficient
        msgObj.process()

    def test_msgType(self):
        """No empty string in dict"""
        data = {"fsck": 1}
        with self.assertRaises(KeyError):
            data[""]

    def test_msgObj(self):
        """Test valid and invalid message dicts"""
        self._test_msgObj(self._valid_msgdict)
        with self.assertRaises(AssertionError):
            self._test_msgObj(self._invalid_msgdict)
