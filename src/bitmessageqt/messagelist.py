from collections import OrderedDict

from PyQt4 import QtCore, QtGui

import account
import foldertree
import l10n
import widgets
from bmconfigparser import BMConfigParser
from debug import logger
from helper_sql import sqlQuery, sqlExecute
from tr import _translate
from utils import avatarize


class InboxFilter(dict):
    def __init__(self, *args, **kwargs):
        self.fields = kwargs.pop('fields')
        super(InboxFilter, self).__init__(*args, **kwargs)

    def __str__(self):
        terms = ' AND '.join([
            '%s = %r' % (key, val)
            for key, val in self.iteritems()
            if key in self.fields
        ])

        return 'WHERE %s' % terms if terms else ''


class CacheDict(OrderedDict):
    def __init__(self, *args, **kwargs):
        self._maxlen = kwargs.pop('maxlen')
        super(CacheDict, self).__init__(*args, **kwargs)
        self._check_len()

    def __setitem__(self, key, value):
        super(CacheDict, self).__setitem__(key, value)
        self._check_len()

    def _check_len(self):
        if self._maxlen:
            while len(self) > self._maxlen:
                # TODO: use Counter
                self.popitem(last=False)


class TimestampFormatter(object):
    def __call__(self, value, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            return l10n.formatTimestamp(value)


class AccountFormatter(object):
    def __init__(self):
        self.addrs = CacheDict(maxlen=100)

    def __call__(self, addr, role=QtCore.Qt.DisplayRole):
        account = self.addrs.get(addr, {})
        if not account:
            self.addrs[addr] = account

        label = account.get('label')
        if label is None:
            account['label'] = label = (
                BMConfigParser().safeGet(addr, 'label') or
                ''
            )

        if role == QtCore.Qt.DisplayRole:
            return label or addr
        elif role == QtCore.Qt.ToolTipRole:
            return '%s (%s)' % (label, addr) if label else addr
        elif role == QtCore.Qt.DecorationRole:
            icon = account.get('icon')
            if not icon:
                account['icon'] = icon = avatarize(addr)
            return icon


class InboxTableModel(QtCore.QAbstractTableModel):
    table = 'inbox'
    fields = (
        'msgid', 'folder', 'toaddress', 'fromaddress', 'subject', 'received', 'read')
    header = (
        {'field': 'fromaddress',
         'label': _translate("MainWindow", "From"),
         'formatter': AccountFormatter()},
        {'field': 'subject',
         'label': _translate("MainWindow", "Subject")},
        {'field': 'received',
         'label': _translate("MainWindow", "Received"),
         'formatter': TimestampFormatter()}
    )
    attributes = ('msgid', 'read')

    def __init__(self, parent=None):
        super(InboxTableModel, self).__init__()
        # folder='*' gives empty set
        self.filter = InboxFilter(folder='*', fields=self.fields)
        self.fields = ','.join(self.fields)
        self.query = 'SELECT %%s FROM %s ' % self.table
        self.sort = ' ORDER BY received DESC'
        self.column_count = len(self.header)

    def columnCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return 0
        return self.column_count

    def rowCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return 0
        return sqlQuery('%s %s' % (self.query, self.filter) % 'COUNT(*)')[0][0]

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.FontRole:
            font = QtGui.QFont()
            font.setBold(
                not sqlQuery(
                    '%s %s %s' % (self.query, self.filter, self.sort) % 'read'
                )[index.row()][0]
            )
            return font
        if not index.isValid() or role not in (
            QtCore.Qt.DisplayRole, QtCore.Qt.ToolTipRole,
            QtCore.Qt.DecorationRole
        ):
            return QtCore.QVariant()

        try:
            column = self.header[index.column()]['field']
        except IndexError:
            # virtual columns: 3 - msgid, 4 - read
            column = self.attributes[index.column() - len(self.header)]

        result = sqlQuery(
            '%s %s %s' % (self.query, self.filter, self.sort) % column
        )[index.row()][0]

        try:
            result = self.header[index.column()].get('formatter')(result, role)
        except (IndexError, TypeError):
            pass

        return result

    def headerData(self, column, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Vertical:
            return
        if role == QtCore.Qt.DisplayRole:
            return self.header[column]['label']

    def setRead(self, row, read=True):
        msgid = self.data(self.createIndex(row, 3))
        sqlExecute('UPDATE inbox SET read = ? WHERE msgid = ?', read, msgid)

    def getMessage(self, row):
        msgid = self.data(self.createIndex(row, 3))
        logger.debug('Selected msgid: %r' % msgid)
        return sqlQuery(
            'SELECT message FROM inbox WHERE msgid = ?', msgid
        )[0][0]

    def updateFilter(self, *args, **kwargs):
        prev = self.filter.__str__()
        self.filter.update(*args, **kwargs)
        if prev != self.filter.__str__():
            self.emit(QtCore.SIGNAL("layoutChanged()"))


class InboxMessagelist(QtGui.QTableView):
    def __init__(self, parent=None):
        super(InboxMessagelist, self).__init__(parent)
        self.setModel(InboxTableModel())

    def currentChanged(self, cur_id, prev_id):
        row = cur_id.row()
        if row and row == prev_id.row():
            return
        # what if folder changed?
        self.model().setRead(row)
        msg = self.model().getMessage(row)
        self.emit(QtCore.SIGNAL("messageSelected(QString)"), msg)

    def folderChanged(self, cur_folder, prev_folder):
        if cur_folder == prev_folder:
            return
        try:
            folder = cur_folder.folderName
        except AttributeError:
            folder = 'inbox'
        update = {'folder': folder}
        if cur_folder.address:
            update['toaddress'] = cur_folder.address
        self.model().updateFilter(update)
        self.selectRow(0)


class TreeWidgetIdentities(QtGui.QTreeWidget):
    def __init__(self, parent):
        super(TreeWidgetIdentities, self).__init__(parent)
        folders = ('inbox', 'new', 'sent', 'trash')
        accounts = account.getSortedAccounts() + account.getSortedSubscriptions().keys()
        top = foldertree.Ui_AddressWidget(self, 0, None, 0, True)
        for i, folder in enumerate(folders):
            foldertree.Ui_FolderWidget(top, i, None, folder, 0)
        for i, addr in enumerate(accounts):
            top = foldertree.Ui_AddressWidget(
                self, i, addr, 0,
                BMConfigParser().safeGetBoolean(addr, 'enabled'))
            for j, folder in enumerate(folders):
                foldertree.Ui_FolderWidget(top, j, addr, folder, 0)
        self.header().setSortIndicator(0, QtCore.Qt.AscendingOrder)

    def filterAccountType(self, account_type):
        header = self.headerItem()
        if account_type == foldertree.AccountMixin.CHAN:
            header.setText(0, _translate("MainWindow", "Chans"))
            header.setIcon(0, QtGui.QIcon(":/newPrefix/images/can-icon-16px.png"))
        elif account_type == foldertree.AccountMixin.SUBSCRIPTION:
            header.setText(0, _translate("MainWindow", "Subscriptions"))
            header.setIcon(0, QtGui.QIcon(":/newPrefix/images/subscriptions.png"))
        for i in xrange(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item.type != account_type:
                self.setItemHidden(item, True)


class MessagelistControl(QtGui.QWidget):
    @QtCore.pyqtProperty(int)
    def AccountType(self):
        return self._account_type

    def setAccountType(self, value):
        self._account_type = value

    def __init__(self, parent=None):
        super(MessagelistControl, self).__init__(parent)
        widgets.load('messagelistcontrol.ui', self)

        self.horizontalSplitter.setStretchFactor(0, 0)
        self.horizontalSplitter.setStretchFactor(1, 1)
        self.horizontalSplitter.setCollapsible(0, False)
        self.horizontalSplitter.setCollapsible(1, False)

        self.verticalSplitter.setStretchFactor(0, 0)
        self.verticalSplitter.setStretchFactor(1, 1)
        self.verticalSplitter.setStretchFactor(2, 2)
        self.verticalSplitter.setCollapsible(0, False)
        self.verticalSplitter.setCollapsible(1, False)
        self.verticalSplitter.setCollapsible(2, False)
        self.verticalSplitter.handle(1).setEnabled(False)

        self.treeWidget.filterAccountType(self.AccountType)
