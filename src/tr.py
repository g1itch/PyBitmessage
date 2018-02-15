import shared


def _translate(context, text, disambiguation=None, n=None):
    return translateText(context, text, n)


def translateText(context, text, n=None):
    try:
        is_daemon = shared.thisapp.daemon
    except AttributeError:  # inside the plugin
        is_daemon = False
    if not is_daemon:
        from qtpy import QtWidgets, QtCore
        if n is None:
            return QtWidgets.QApplication.translate(context, text)
        else:
            return QtWidgets.QApplication.translate(
                context, text, None, QtCore.QCoreApplication.CodecForTr, n)
    else:
        return text
