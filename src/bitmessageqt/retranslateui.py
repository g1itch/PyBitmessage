from PyQt4 import QtGui

import widgets
from debug import logger


class RetranslateMixin(object):
    """
    Mixin with retranslateUi() method defined to automatically retranslate
    all widgets.
    """
    def retranslateUi(self):
        logger.debug('retranslateUi on %s', self.__class__)
        defaults = self.__class__() if isinstance(
            self, QtGui.QMainWindow) else QtGui.QWidget()
        try:
            widgets.load(self.uifile, defaults)
            # potential AttributeError from widgets.load here ):
        except AttributeError:
            self.uifile = self.__class__.__name__.lower() + '.ui'
            widgets.load(self.uifile, defaults)
        for attr, value in defaults.__dict__.iteritems():
            setTextMethod = getattr(value, "setText", None)
            if callable(setTextMethod):
                try:
                    getattr(self, attr).setText(getattr(defaults, attr).text())
                except AttributeError:  # MessageView, MessageCompose
                    pass
            elif isinstance(value, QtGui.QTableWidget):
                for i in range(value.columnCount()):
                    getattr(self, attr).horizontalHeaderItem(i).setText(
                        getattr(defaults, attr).horizontalHeaderItem(i).text())
                for i in range(value.rowCount()):
                    getattr(self, attr).verticalHeaderItem(i).setText(
                        getattr(defaults, attr).verticalHeaderItem(i).text())
