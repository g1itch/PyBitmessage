from qtpy import QtCore, QtWidgets


class SettingsMixin(object):
    def warnIfNoObjectName(self):
        if self.objectName() == "":
            # TODO: logger
            pass

    def writeState(self, source):
        self.warnIfNoObjectName()
        settings = QtCore.QSettings()
        settings.beginGroup(self.objectName())
        settings.setValue("state", source.saveState())
        settings.endGroup()

    def writeGeometry(self, source):
        self.warnIfNoObjectName()
        settings = QtCore.QSettings()
        settings.beginGroup(self.objectName())
        settings.setValue("geometry", source.saveGeometry())
        settings.endGroup()

    def readGeometry(self, target):
        self.warnIfNoObjectName()
        settings = QtCore.QSettings()
        try:
            geom = settings.value(
                "/".join([str(self.objectName()), "geometry"]))
            target.restoreGeometry(geom)
        except Exception:
            pass

    def readState(self, target):
        self.warnIfNoObjectName()
        settings = QtCore.QSettings()
        try:
            state = settings.value("/".join([str(self.objectName()), "state"]))
            target.restoreState(state)
        except Exception:
            pass


class SMainWindow(QtWidgets.QMainWindow, SettingsMixin):
    def loadSettings(self):
        self.readGeometry(self)
        self.readState(self)

    def saveSettings(self):
        self.writeState(self)
        self.writeGeometry(self)


class STableWidget(QtWidgets.QTableWidget, SettingsMixin):
    def loadSettings(self):
        self.readState(self.horizontalHeader())

    def saveSettings(self):
        self.writeState(self.horizontalHeader())


class SSplitter(QtWidgets.QSplitter, SettingsMixin):
    def loadSettings(self):
        self.readState(self)

    def saveSettings(self):
        self.writeState(self)


class STreeWidget(QtWidgets.QTreeWidget, SettingsMixin):
    def loadSettings(self):
        # recurse children
        # self.readState(self)
        pass

    def saveSettings(self):
        # recurse children
        # self.writeState(self)
        pass
