import os
import shared

try:
    _daemon = shared.thisapp.daemon
except AttributeError:  # inside the plugin
    _daemon = False
if _daemon:
    def _translate(context, text, disambiguation=None, n=None):
        return text
else:
    from qtpy import QtWidgets, QtCore
    if os.environ['QT_API'] == 'pyqt5':
        _translate = QtWidgets.QApplication.translate
    else:
        def _translate(context, text, disambiguation=None, n=None):
            return (
                QtWidgets.QApplication.translate(context, text, disambiguation)
                if n is None else
                QtWidgets.QApplication.translate(
                    context, text, disambiguation,
                    QtCore.QCoreApplication.CodecForTr, n)
            )
