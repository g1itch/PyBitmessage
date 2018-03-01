from qtpy import QtCore, QtWidgets
from tr import _translate


class MessageCompose(QtWidgets.QTextEdit):

    def __init__(self, parent=None):
        super(MessageCompose, self).__init__(parent)
        # we'll deal with this later when we have a new message format
        self.setAcceptRichText(False)
        self.defaultFontPointSize = self.currentFont().pointSize()

    def wheelEvent(self, event):
        if (
            (QtWidgets.QApplication.queryKeyboardModifiers()
             & QtCore.Qt.ControlModifier) == QtCore.Qt.ControlModifier
            and event.angleDelta().y() != 0
        ):
            if event.delta() > 0:
                self.zoomIn(1)
            else:
                self.zoomOut(1)
            zoom = self.currentFont().pointSize() * 100 / self.defaultFontPointSize
            QtWidgets.QApplication.activeWindow().statusbar.showMessage(
                _translate("MainWindow", "Zoom level {0}%").format(zoom))
        else:
            # in QTextEdit, super does not zoom, only scroll
            super(MessageCompose, self).wheelEvent(event)

    def reset(self):
        self.setText('')
