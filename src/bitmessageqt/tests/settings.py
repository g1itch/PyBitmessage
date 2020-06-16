from PyQt4 import QtCore, QtTest

import state
from bmconfigparser import BMConfigParser
from bitmessageqt import settings

from main import TestBase


class TestSettings(TestBase):
    """A test case for the "Settings" dialog"""

    def test_dontconnect(self):
        """Check that Settings dialog doesn't remove dontconnect"""
        BMConfigParser().set('bitmessagesettings', 'dontconnect', 'true')
        QtTest.QTest.qSleep(5005)
        self.assertEqual(state.statusIconColor, 'red')
        self.assertEqual(
            BMConfigParser().safeGet(
                'bitmessagesettings', 'socksproxytype'), 'none')
        # self.window.ui.actionSettings.trigger()
        # dialog = self.app.activeWindow()
        # self.assertIsInstance(dialog, settings.SettingsDialog)
        dialog = settings.SettingsDialog(self.window)
        dialog.comboBoxProxyType.setCurrentIndex(2)
        # Accept later
        QtCore.QTimer.singleShot(
            1, lambda:
            QtTest.QTest.mouseClick(
                dialog.buttonBox.button(dialog.buttonBox.Ok),
                QtCore.Qt.LeftButton)
        )
        dialog.exec_()

        self.assertFalse(dialog.net_restart_needed)
        # QtTest.QTest.mouseClick(dialog.checkBoxUPnP, QtCore.Qt.LeftButton)
        # QtTest.QTest.mouseClick(dialog.buttonBox.button(dialog.buttonBox.Ok), QtCore.Qt.LeftButton)
        self.assertEqual(
            BMConfigParser().safeGet(
                'bitmessagesettings', 'socksproxytype'), 'SOCKS5')
        QtTest.QTest.qSleep(5050)
        self.assertTrue(
            BMConfigParser().safeGetBoolean(
                'bitmessagesettings', 'dontconnect'))
