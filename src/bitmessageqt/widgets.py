import os
from io import BytesIO

from qtpy import QtCore, uic

from pybitmessage import paths


def resource_path(resFile):
    baseDir = paths.codePath()
    if baseDir is None:  # pyqtdeploy bundle
        resFile = QtCore.QFile(
            ':/pybitmessage/bitmessageqt/{}'.format(resFile))
        resFile.open(QtCore.QIODevice.ReadOnly)
        data = resFile.readAll()
        resFile.close()
        return BytesIO(bytes(data))
    for subDir in ('bitmessageqt', 'ui'):
        path = os.path.join(baseDir, subDir, resFile)
        if os.path.isfile(path):
            return path


def load(resFile, widget):
    uic.loadUi(resource_path(resFile), widget)
