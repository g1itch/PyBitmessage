import state


def _translate(context, text, disambiguation=None, n=None):
    return translateText(context, text, n)


def translateText(context, text, n=None):
    """Translate text in context"""
    try:
        enableGUI = state.enableGUI
    except AttributeError:  # inside the plugin
        enableGUI = True
    if enableGUI:
        from qtpy import QtWidgets, QtCore
        if n is None:
            return QtWidgets.QApplication.translate(context, text)
        else:
            return QtWidgets.QApplication.translate(
                context, text, None, QtCore.QCoreApplication.CodecForTr, n)
    else:
        return text
