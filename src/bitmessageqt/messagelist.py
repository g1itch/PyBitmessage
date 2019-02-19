from PyQt4 import QtCore, QtGui

from debug import logger
from helper_sql import sqlQuery, sqlExecute
from tr import _translate


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


class InboxTableItem(QtCore.QAbstractItemModel):
    pass


class InboxTableModel(QtCore.QAbstractTableModel):
    fields = (
        'msgid', 'toaddress', 'fromaddress', 'subject', 'received', 'read')
    header = (
        {'field': 'fromaddress',
         'label': _translate("MainWindow", "From")},
        {'field': 'subject',
         'label': _translate("MainWindow", "Subject")},
        {'field': 'received',
         'label': _translate("MainWindow", "Received")}
    )
    attributes = ('msgid', 'read')
    table = 'inbox'

    def __init__(self, parent=None):
        super(InboxTableModel, self).__init__()
        self.filter = InboxFilter(fields=self.fields)
        self.fields = ','.join(self.fields)
        self.query = 'SELECT %%s FROM %s ' % self.table
        self.sort = ' ORDER BY received DESC'
        self.column_count = len(self.header)
        self.item = InboxTableItem()

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
                QtCore.Qt.DisplayRole, QtCore.Qt.ToolTipRole
        ):
            return QtCore.QVariant()

        try:
            column = self.header[index.column()]['field']
        except IndexError:
            # virtual columns: 3 - msgid, 4 - read
            column = self.attributes[index.column() - len(self.header)]

        return sqlQuery(
            '%s %s %s' % (self.query, self.filter, self.sort) % column
        )[index.row()][0]

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


class InboxMessagelist(QtGui.QTableView):
    def __init__(self, parent=None):
        super(InboxMessagelist, self).__init__(parent)
        self.setModel(InboxTableModel())

    def currentChanged(self, cur_id, prev_id):
        row = cur_id.row()
        if row == prev_id.row():
            return
        self.model().setRead(row)
        msg = self.model().getMessage(row)
        self.emit(QtCore.SIGNAL("messageSelected(QString)"), msg)
