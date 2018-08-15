from datetime import datetime

import version
import widgets
from address_dialogs import (
    AddAddressDialog, NewAddressDialog, NewSubscriptionDialog,
    RegenerateAddressesDialog, SpecialAddressBehaviorDialog, EmailGatewayDialog
)
from newchandialog import NewChanDialog
from PyQt4 import QtGui
from retranslateui import RetranslateMixin
from tr import _translate


__all__ = [
    "NewChanDialog", "AddAddressDialog", "NewAddressDialog",
    "NewSubscriptionDialog", "RegenerateAddressesDialog",
    "SpecialAddressBehaviorDialog", "EmailGatewayDialog"
]


class AboutDialog(QtGui.QDialog, RetranslateMixin):
    def __init__(self, parent=None):
        super(AboutDialog, self).__init__(parent)
        widgets.load('about.ui', self)

        # Adjusting version, commit and year info
        full_version = version.softwareVersion
        try:  # commit written by sdist setuptools command
            last_commit = version.commit
        except AttributeError:
            import paths
            last_commit = paths.lastCommit()
        commit = last_commit.get('commit')
        if commit:
            full_version += '-' + commit[:7]
        self.labelVersion.setText(
            self.labelVersion.text().replace(
                ':version:', full_version
            ).replace(':branch:', commit or 'v%s' % full_version)
        )
        self.labelVersion.setOpenExternalLinks(True)

        try:  # last copyright year from last commit
            self.label_2.setText(
                self.label_2.text().replace(
                    '2017',
                    str(datetime.fromtimestamp(last_commit.get('time')).year)
                ))
        except AttributeError:
            pass

        self.setFixedSize(QtGui.QWidget.sizeHint(self))


class IconGlossaryDialog(QtGui.QDialog, RetranslateMixin):
    def __init__(self, parent=None, config=None):
        super(IconGlossaryDialog, self).__init__(parent)
        widgets.load('iconglossary.ui', self)

        # FIXME: check the window title visibility here
        self.groupBox.setTitle('')

        self.labelPortNumber.setText(_translate(
            "iconGlossaryDialog",
            "You are using TCP port %1. (This can be changed in the settings)."
        ).arg(config.getint('bitmessagesettings', 'port')))
        self.setFixedSize(QtGui.QWidget.sizeHint(self))


class HelpDialog(QtGui.QDialog, RetranslateMixin):
    def __init__(self, parent=None):
        super(HelpDialog, self).__init__(parent)
        widgets.load('help.ui', self)
        self.setFixedSize(QtGui.QWidget.sizeHint(self))


class ConnectDialog(QtGui.QDialog, RetranslateMixin):
    def __init__(self, parent=None):
        super(ConnectDialog, self).__init__(parent)
        widgets.load('connect.ui', self)
        self.setFixedSize(QtGui.QWidget.sizeHint(self))
