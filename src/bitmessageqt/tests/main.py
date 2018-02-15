"""Common definitions for bitmessageqt tests"""

import unittest

from qtpy import QtWidgets

import bitmessageqt
from tr import _translate


class TestBase(unittest.TestCase):
    """Base class for bitmessageqt test case"""

    def setUp(self):
        self.app = QtWidgets.QApplication([])
        self.window = bitmessageqt.MyForm()

    def tearDown(self):
        self.app.deleteLater()


class TestMain(unittest.TestCase):
    """Test case for main window - basic features"""

    def test_translate(self):
        """Check the results of _translate() with various args"""
        self.assertIsInstance(
            _translate("MainWindow", "Test"),
            unicode
        )
