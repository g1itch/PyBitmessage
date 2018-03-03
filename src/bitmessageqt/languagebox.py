import glob
import os
from qtpy import QtCore, QtWidgets
from tr import _translate

from bmconfigparser import BMConfigParser
import paths


class LanguageBox(QtWidgets.QComboBox):
    languageName = {
        "system": "System Settings",
        "eo": "Esperanto",
        "en_pirate": "Pirate English"
    }

    def __init__(self, parent=None):
        super(LanguageBox, self).__init__(parent)
        self.populate()

    def populate(self):
        self.clear()
        self.addItem(
            _translate("settingsDialog", "System Settings", "system"),
            "system"
        )
        self.setCurrentIndex(0)
        self.setInsertPolicy(QtWidgets.QComboBox.InsertAlphabetically)

        localesPath = os.path.join(paths.codePath(), 'translations')
        for translationFile in sorted(
            glob.glob(os.path.join(localesPath, "bitmessage_*.qm"))
        ):
            localeShort = \
                os.path.split(translationFile)[1].split("_", 1)[1][:-3]
            if localeShort in LanguageBox.languageName:
                self.addItem(
                    LanguageBox.languageName[localeShort], localeShort)
            else:
                locale = QtCore.QLocale(localeShort)
                self.addItem(
                    locale.nativeLanguageName() or localeShort, localeShort)
        configuredLocale = BMConfigParser().safeGet(
            'bitmessagesettings', 'userlocale', "system")
        for i in range(self.count()):
            if self.itemData(i) == configuredLocale:
                self.setCurrentIndex(i)
                break
