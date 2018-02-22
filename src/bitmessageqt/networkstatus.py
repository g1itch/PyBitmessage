from qtpy import QtCore, QtGui, QtWidgets
import time
import shared

from tr import _translate
from inventory import Inventory
import knownnodes
import l10n
import network.stats
from retranslateui import RetranslateMixin
from uisignaler import UISignaler
import widgets

from network.connectionpool import BMConnectionPool


class NetworkStatus(QtWidgets.QWidget, RetranslateMixin):
    def __init__(self, parent=None):
        super(NetworkStatus, self).__init__(parent)
        widgets.load('networkstatus.ui', self)

        header = self.tableWidgetConnectionCount.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)

        # Somehow this value was 5 when I tested
        if header.sortIndicatorSection() > 4:
            header.setSortIndicator(0, QtCore.Qt.AscendingOrder)

        self.startup = time.localtime()
        self.labelStartupTime.setText(
            _translate("networkstatus", "Since startup on {0}").format(
                l10n.formatTimestamp(self.startup))
        )

        self.UISignalThread = UISignaler.get()
        self.UISignalThread.updateNumberOfMessagesProcessed.connect(
            self.updateNumberOfMessagesProcessed)
        self.UISignalThread.updateNumberOfPubkeysProcessed.connect(
            self.updateNumberOfPubkeysProcessed)
        self.UISignalThread.updateNumberOfBroadcastsProcessed.connect(
            self.updateNumberOfBroadcastsProcessed)
        self.UISignalThread.updateNetworkStatusTab.connect(
            self.updateNetworkStatusTab)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.runEveryTwoSeconds)

    def startUpdate(self):
        Inventory().numberOfInventoryLookupsPerformed = 0
        self.runEveryTwoSeconds()
        self.timer.start(2000)  # milliseconds

    def stopUpdate(self):
        self.timer.stop()

    def formatBytes(self, num):
        for x in [
                _translate("networkstatus", "byte(s)", None, num),
                "kB", "MB", "GB"
        ]:
            if num < 1000.0:
                return "%3.0f %s" % (num, x)
            num /= 1000.0
        return "%3.0f %s" % (num, 'TB')

    def formatByteRate(self, num):
        num /= 1000
        return "%4.0f kB" % num

    def updateNumberOfObjectsToBeSynced(self):
        self.labelSyncStatus.setText(
            _translate(
                "networkstatus", "Object(s) to be synced: %n", None,
                network.stats.pendingDownload() + network.stats.pendingUpload()
        ))

    def updateNumberOfMessagesProcessed(self):
        self.updateNumberOfObjectsToBeSynced()
        self.labelMessageCount.setText(_translate(
            "networkstatus", "Processed %n person-to-person message(s).",
            None, shared.numberOfMessagesProcessed))

    def updateNumberOfBroadcastsProcessed(self):
        self.updateNumberOfObjectsToBeSynced()
        self.labelBroadcastCount.setText(_translate(
            "networkstatus", "Processed %n broadcast message(s).", None,
            shared.numberOfBroadcastsProcessed))

    def updateNumberOfPubkeysProcessed(self):
        self.updateNumberOfObjectsToBeSynced()
        self.labelPubkeyCount.setText(_translate(
            "networkstatus", "Processed %n public key(s).", None,
            shared.numberOfPubkeysProcessed))

    def updateNumberOfBytes(self):
        """
        This function is run every two seconds, so we divide the rate of bytes
        sent and received by 2.
        """
        self.labelBytesRecvCount.setText(_translate(
            "networkstatus", "Down: {0}/s  Total: {1}"
            ).format(
                self.formatByteRate(network.stats.downloadSpeed()),
                self.formatBytes(network.stats.receivedBytes())
        ))
        self.labelBytesSentCount.setText(_translate(
            "networkstatus", "Up: {0}/s  Total: {1}").format(
                self.formatByteRate(network.stats.uploadSpeed()),
                self.formatBytes(network.stats.sentBytes())
        ))

    def updateNetworkStatusTab(self, outbound, add, destination):
        if outbound:
            try:
                c = BMConnectionPool().outboundConnections[destination]
            except KeyError:
                if add:
                    return
        else:
            try:
                c = BMConnectionPool().inboundConnections[destination]
            except KeyError:
                try:
                    c = BMConnectionPool().inboundConnections[destination.host]
                except KeyError:
                    if add:
                        return

        self.tableWidgetConnectionCount.setUpdatesEnabled(False)
        self.tableWidgetConnectionCount.setSortingEnabled(False)
        if add:
            self.tableWidgetConnectionCount.insertRow(0)
            self.tableWidgetConnectionCount.setItem(0, 0,
                QtWidgets.QTableWidgetItem("%s:%i" % (destination.host, destination.port))
                )
            self.tableWidgetConnectionCount.setItem(0, 2,
                QtWidgets.QTableWidgetItem("%s" % (c.userAgent))
                )
            self.tableWidgetConnectionCount.setItem(0, 3,
                QtWidgets.QTableWidgetItem("%s" % (c.tlsVersion))
                )
            self.tableWidgetConnectionCount.setItem(0, 4,
                QtWidgets.QTableWidgetItem("%s" % (",".join(map(str,c.streams))))
                )
            try:
                # FIXME hard coded stream no
                rating = "%.1f" % (knownnodes.knownNodes[1][destination]['rating'])
            except KeyError:
                rating = "-"
            self.tableWidgetConnectionCount.setItem(0, 1,
                QtWidgets.QTableWidgetItem("%s" % (rating))
                )
            if outbound:
                brush = QtGui.QBrush(QtGui.QColor("yellow"), QtCore.Qt.SolidPattern)
            else:
                brush = QtGui.QBrush(QtGui.QColor("green"), QtCore.Qt.SolidPattern)
            for j in (range(1)):
                self.tableWidgetConnectionCount.item(0, j).setBackground(brush)
            self.tableWidgetConnectionCount.item(0, 0).setData(QtCore.Qt.UserRole, destination)
            self.tableWidgetConnectionCount.item(0, 1).setData(QtCore.Qt.UserRole, outbound)
        else:
            for i in range(self.tableWidgetConnectionCount.rowCount()):
                if self.tableWidgetConnectionCount.item(i, 0).data(QtCore.Qt.UserRole) != destination:
                    continue
                if self.tableWidgetConnectionCount.item(i, 1).data(QtCore.Qt.UserRole) == outbound:
                    self.tableWidgetConnectionCount.removeRow(i)
                    break
        self.tableWidgetConnectionCount.setUpdatesEnabled(True)
        self.tableWidgetConnectionCount.setSortingEnabled(True)
        self.labelTotalConnections.setText(_translate(
            "networkstatus", "Total Connections: {0}").format(
                self.tableWidgetConnectionCount.rowCount()
        ))
       # FYI: The 'singlelistener' thread sets the icon color to green when it receives an incoming connection, meaning that the user's firewall is configured correctly.
        if self.tableWidgetConnectionCount.rowCount() and shared.statusIconColor == 'red':
            self.window().setStatusIcon('yellow')
        elif self.tableWidgetConnectionCount.rowCount() == 0 and shared.statusIconColor != "red":
            self.window().setStatusIcon('red')

    # timer driven
    def runEveryTwoSeconds(self):
        self.labelLookupsPerSecond.setText(_translate(
            "networkstatus", "Inventory lookups per second: {0}").format(
                Inventory().numberOfInventoryLookupsPerformed/2
        ))
        Inventory().numberOfInventoryLookupsPerformed = 0
        self.updateNumberOfBytes()
        self.updateNumberOfObjectsToBeSynced()

    def retranslateUi(self):
        super(NetworkStatus, self).retranslateUi()
        self.labelStartupTime.setText(
            _translate("networkstatus", "Since startup on {0}").format(
                l10n.formatTimestamp(self.startup)
            ))
