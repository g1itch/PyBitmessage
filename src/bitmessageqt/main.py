from PyQt4 import QtCore, QtGui

import settingsmixin
import widgets
from bmconfigparser import BMConfigParser
from foldertree import AddressBookCompleter
from retranslateui import RetranslateMixin
from tr import _translate


class Window(settingsmixin.SMainWindow, RetranslateMixin):
    """The main PyBitmessage's window"""

    def __init__(self, parent=None):
        super(Window, self).__init__(parent)
        widgets.load('bitmessageui.ui', self)

        self.addressBookCompleter = AddressBookCompleter()
        self.addressBookCompleter.setCompletionMode(
            QtGui.QCompleter.PopupCompletion)
        self.addressBookCompleter.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.addressBookCompleterModel = QtGui.QStringListModel()
        self.addressBookCompleter.setModel(self.addressBookCompleterModel)
        self.lineEditTo.setCompleter(self.addressBookCompleter)

        # splitters
        for splitter in (
            self.inboxHorizontalSplitter,
            self.sendHorizontalSplitter,
            self.subscriptionsHorizontalSplitter,
            self.chansHorizontalSplitter
        ):
            splitter.setStretchFactor(0, 0)
            splitter.setStretchFactor(1, 1)
            splitter.setCollapsible(0, False)
            splitter.setCollapsible(1, False)

        for splitter in (
            self.inboxIdentitiesSplitter,
            self.sendIdentitiesSplitter,
            self.subscriptionsIdentitiesSplitter,
            self.chansIdentitiesSplitter
        ):
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 0)
            splitter.setCollapsible(0, False)
            splitter.setCollapsible(1, False)
            splitter.handle(1).setEnabled(False)

        for splitter in (
            self.inboxMessagecontrolSplitter,
            self.subscriptionsMessagecontrolSplitter,
            self.chansMessagecontrolSplitter
        ):
            splitter.setStretchFactor(0, 0)
            splitter.setStretchFactor(1, 1)
            splitter.setStretchFactor(2, 2)
            splitter.setCollapsible(0, False)
            splitter.setCollapsible(1, False)
            splitter.setCollapsible(2, False)
            splitter.handle(1).setEnabled(False)

        self.sendMessagecontrolSplitter.handle(1).setEnabled(False)

    def updateNetworkSwitchMenuLabel(self, dontconnect=None):
        """
        Set the label for "Go online"/"Go offline" menu action
        depending on 'dontconnect' setting
        """
        if dontconnect is None:
            dontconnect = BMConfigParser().safeGetBoolean(
                'bitmessagesettings', 'dontconnect')
        self.actionNetworkSwitch.setText(
            _translate("MainWindow", "Go online", None)
            if dontconnect else
            _translate("MainWindow", "Go offline", None)
        )