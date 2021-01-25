"""
Slim layer providing environment agnostic _translate()
"""

import state


def _tr_dummy(context, text, disambiguation=None, n=None):
    # pylint: disable=unused-argument
    return text


if state.enableGUI and not state.curses:
    try:
        from fallback import qtpy  # noqa:F401
        from qtpy import QtWidgets, QtCore, API
    except ImportError:
        _translate = _tr_dummy
    else:
        if API == 'pyqt5':
            _translate = QtWidgets.QApplication.translate
        else:
            def _translate(context, text, disambiguation=None, n=None):
                return (
                    QtWidgets.QApplication.translate(
                        context, text, disambiguation)
                    if n is None else
                    QtWidgets.QApplication.translate(
                        context, text, disambiguation,
                        QtCore.QCoreApplication.CodecForTr, n)
                )
else:
    _translate = _tr_dummy
