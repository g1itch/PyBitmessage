from qtpy import uic
import os
import paths


def resource_path(resFile):
    baseDir = paths.codePath()
    for subDir in ["ui", "bitmessageqt"]:
        if (
            os.path.isdir(os.path.join(baseDir, subDir))
            and os.path.isfile(os.path.join(baseDir, subDir, resFile))
        ):
            return os.path.join(baseDir, subDir, resFile)


def load(resFile, widget):
    uic.loadUi(resource_path(resFile), widget)
