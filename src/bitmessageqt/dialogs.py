from qtpy import QtWidgets
from tr import _translate
from retranslateui import RetranslateMixin
import widgets

from newchandialog import NewChanDialog
from address_dialogs import (
    AddAddressDialog, NewAddressDialog, NewSubscriptionDialog,
    RegenerateAddressesDialog, SpecialAddressBehaviorDialog, EmailGatewayDialog
)

import paths
from version import softwareVersion


__all__ = [
    "NewChanDialog", "AddAddressDialog", "NewAddressDialog",
    "NewSubscriptionDialog", "RegenerateAddressesDialog",
    "SpecialAddressBehaviorDialog", "EmailGatewayDialog"
]


class AboutDialog(QtWidgets.QDialog, RetranslateMixin):
    def __init__(self, parent=None):
        super(AboutDialog, self).__init__(parent)
        widgets.load('about.ui', self)
        last_commit = paths.lastCommit()
        version = softwareVersion
        commit = last_commit.get('commit')
        if commit:
            version += '-' + commit[:7]
        self.labelVersion.setText(
            self.labelVersion.text().replace(
                ':version:', version
                ).replace(':branch:', commit or 'v%s' % version)
        )
        self.labelVersion.setOpenExternalLinks(True)

        try:
            self.label_2.setText(
                self.label_2.text().replace(
                    '2017', str(last_commit.get('time').year)
                ))
        except AttributeError:
            pass

        self.setFixedSize(QtWidgets.QWidget.sizeHint(self))


class IconGlossaryDialog(QtWidgets.QDialog, RetranslateMixin):
    def __init__(self, parent=None, config=None):
        super(IconGlossaryDialog, self).__init__(parent)
        widgets.load('iconglossary.ui', self)

        # FIXME: check the window title visibility here
        self.groupBox.setTitle('')

        self.labelPortNumber.setText(_translate(
            "iconGlossaryDialog",
            "You are using TCP port {0}."
            " (This can be changed in the settings)."
            ).format(config.getint('bitmessagesettings', 'port')))
        self.setFixedSize(QtWidgets.QWidget.sizeHint(self))


class HelpDialog(QtWidgets.QDialog, RetranslateMixin):
    def __init__(self, parent=None):
        super(HelpDialog, self).__init__(parent)
        widgets.load('help.ui', self)
        self.setFixedSize(QtWidgets.QWidget.sizeHint(self))


class ConnectDialog(QtWidgets.QDialog, RetranslateMixin):
    def __init__(self, parent=None):
        super(ConnectDialog, self).__init__(parent)
        widgets.load('connect.ui', self)
        self.setFixedSize(QtWidgets.QWidget.sizeHint(self))
