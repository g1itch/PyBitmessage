"""
BMConfigParser class definition and default configuration settings
"""

import os
import shutil
from datetime import datetime
try:
    from ConfigParser import (
        ConfigParser, InterpolationError, NoOptionError, NoSectionError,
        SafeConfigParser)
except ImportError:
    from configparser import (
        ConfigParser, InterpolationError, NoOptionError, NoSectionError)
    SafeConfigParser = ConfigParser

import state
from singleton import Singleton


BMConfigDefaults = {
    "bitmessagesettings": {
        "maxaddrperstreamsend": 500,
        "maxbootstrapconnections": 20,
        "maxdownloadrate": 0,
        "maxoutboundconnections": 8,
        "maxtotalconnections": 200,
        "maxuploadrate": 0,
        "apiinterface": "127.0.0.1",
        "apiport": 8442
    },
    "threads": {
        "receive": 3,
    },
    "network": {
        "bind": '',
        "dandelion": 90,
    },
    "inventory": {
        "storage": "sqlite",
        "acceptmismatch": False,
    },
    "knownnodes": {
        "maxnodes": 20000,
    },
    "zlib": {
        'maxsize': 1048576
    }
}


class Parser(SafeConfigParser):
    """
    An ancestor of :class:`SafeConfigParser`
    with additional methods specific to bitmessage config.
    """
    # pylint: disable=too-many-ancestors

    _temp = {}

    def set(self, section, option, value=None):
        if self._optcre is self.OPTCRE or value:
            if not isinstance(value, basestring):
                raise TypeError("option values must be strings")
        if not self.validate(section, option, value):
            raise ValueError("Invalid value %s" % value)
        return ConfigParser.set(self, section, option, value)

    def get(self, section, option, raw=False, variables=None):
        # pylint: disable=arguments-differ
        try:
            if section == "bitmessagesettings" and option == "timeformat":
                return ConfigParser.get(
                    self, section, option, raw, variables)
            try:
                return self._temp[section][option]
            except KeyError:
                pass
            return ConfigParser.get(
                self, section, option, True, variables)
        except InterpolationError:
            return ConfigParser.get(
                self, section, option, True, variables)
        except (NoSectionError, NoOptionError) as e:
            try:
                return BMConfigDefaults[section][option]
            except (KeyError, ValueError, AttributeError):
                raise e

    def setTemp(self, section, option, value=None):
        """Temporary set option to value, not saving."""
        try:
            self._temp[section][option] = value
        except KeyError:
            self._temp[section] = {option: value}

    def safeGetBoolean(self, section, field):
        """Return value as boolean, False on exceptions"""
        try:
            return self.getboolean(section, field)
        except (NoSectionError, NoOptionError, ValueError, AttributeError):
            return False

    def safeGetInt(self, section, field, default=0):
        """Return value as integer, default on exceptions,
        0 if default missing"""
        try:
            return self.getint(section, field)
        except (NoSectionError, NoOptionError, ValueError, AttributeError):
            return default

    def safeGet(self, section, option, default=None):
        """Return value as is, default on exceptions, None if default missing"""
        try:
            return self.get(section, option)
        except (NoSectionError, NoOptionError, ValueError, AttributeError):
            return default

    def items(self, section, raw=False, variables=None):
        """Return section variables as parent,
        but override the "raw" argument to always True"""
        # pylint: disable=arguments-differ
        return ConfigParser.items(self, section, True, variables)

    @staticmethod
    def addresses():
        """Return a list of local bitmessage addresses (from section labels)"""
        return [
            x for x in BMConfigParser().sections() if x.startswith('BM-')]

    def _reset(self):
        """Reset current config. There doesn't appear to be a built in
           method for this"""
        sections = self.sections()
        for x in sections:
            self.remove_section(x)

    def read(self, filenames):
        """Read config and populate defaults"""
        self._reset()
        ConfigParser.read(self, filenames)
        for section in self.sections():
            for option in self.options(section):
                try:
                    if not self.validate(
                        section, option,
                        ConfigParser.get(self, section, option)
                    ):
                        try:
                            newVal = BMConfigDefaults[section][option]
                        except KeyError:
                            continue
                        ConfigParser.set(
                            self, section, option, newVal)
                except InterpolationError:
                    continue

    def save(self):
        """Save the runtime config onto the filesystem"""
        fileName = os.path.join(state.appdata, 'keys.dat')
        fileNameBak = '.'.join([
            fileName, datetime.now().strftime("%Y%j%H%M%S%f"), 'bak'])
        # create a backup copy to prevent the accidental loss due to
        # the disk write failure
        try:
            shutil.copyfile(fileName, fileNameBak)
            # The backup succeeded.
            fileNameExisted = True
        except (IOError, Exception):
            # The backup failed. This can happen if the file
            # didn't exist before.
            fileNameExisted = False
        # write the file
        with open(fileName, 'wb') as configfile:
            self.write(configfile)
        # delete the backup
        if fileNameExisted:
            os.remove(fileNameBak)

    def validate(self, section, option, value):
        """Input validator interface (using factory pattern)"""
        try:
            return getattr(self, 'validate_%s_%s' % (section, option))(value)
        except AttributeError:
            return True

    @staticmethod
    def validate_bitmessagesettings_maxoutboundconnections(value):
        """Reject maxoutboundconnections that are too high or too low"""
        try:
            value = int(value)
        except ValueError:
            return False
        if value < 0 or value > 8:
            return False
        return True


@Singleton
class BMConfigParser(Parser):
    """Singleton class inherited from :class:`Parser`"""
    pass
