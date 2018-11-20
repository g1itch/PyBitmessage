"""
A tests for MainWindow
"""

import unittest

from PyQt4 import QtCore, QtGui, QtTest

import bitmessageqt
from tr import _translate

app = QtGui.QApplication([])


class TestMain(unittest.TestCase):
    """A test case for MainWindow"""

    def setUp(self):
        self.window = bitmessageqt.MainWindow()

    def test_defaults(self):
        tab_widget = self.window.tabWidget
        self.assertEqual(tab_widget.count(), 6)
        self.assertEqual(tab_widget.currentIndex(), 0)
        self.assertEqual(
            tab_widget.tabText(0), _translate("MainWindow", "Messages"))
        self.assertEqual(
            tab_widget.tabText(1), _translate("MainWindow", "Send"))
        self.assertEqual(
            tab_widget.tabText(2), _translate("MainWindow", "Subscriptions"))
        self.assertEqual(
            tab_widget.tabText(3), _translate("MainWindow", "Chans"))
        self.assertEqual(
            tab_widget.tabText(5),
            _translate("MainWindow", "Network Status"))

        menu_actions = self.window.menubar.actions()
        self.assertEqual(len(menu_actions), 3)
        self.assertEqual(
            menu_actions[0].text(), _translate("MainWindow", "File"))
        self.assertEqual(
            menu_actions[1].text(), _translate("MainWindow", "Settings"))
        self.assertEqual(
            menu_actions[2].text(), _translate("MainWindow", "Help"))
