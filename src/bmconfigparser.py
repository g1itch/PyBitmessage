"""
BMConfigParser class definition and default configuration settings
"""

import ConfigParser
import shutil
import os
from datetime import datetime

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


@Singleton
class BMConfigParser(ConfigParser.SafeConfigParser):
    """Singleton class inherited from ConfigParser.SafeConfigParser
    with additional methods specific to bitmessage config."""

    def set(self, section, option, value=None):
        if self._optcre is self.OPTCRE or value:
            if not isinstance(value, basestring):
                raise TypeError("option values must be strings")
        if not self.validate(section, option, value):
            raise ValueError("Invalid value %s" % value)
        return ConfigParser.ConfigParser.set(self, section, option, value)

    def get(self, section, option, raw=False, variables=None):
        try:
            if section == "bitmessagesettings" and option == "timeformat":
                return ConfigParser.ConfigParser.get(
                    self, section, option, raw, variables)
            return ConfigParser.ConfigParser.get(
                self, section, option, True, variables)
        except ConfigParser.InterpolationError:
            return ConfigParser.ConfigParser.get(
                self, section, option, True, variables)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
            try:
                return BMConfigDefaults[section][option]
            except (KeyError, ValueError, AttributeError):
                raise e

    def safeGetBoolean(self, section, field):
        try:
            return self.getboolean(section, field)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError,
                ValueError, AttributeError):
            return False

    def safeGetInt(self, section, field, default=0):
        try:
            return self.getint(section, field)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError,
                ValueError, AttributeError):
            return default

    def safeGet(self, section, option, default=None):
        try:
            return self.get(section, option)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError,
                ValueError, AttributeError):
            return default

    def items(self, section, raw=False, variables=None):
        return ConfigParser.ConfigParser.items(self, section, True, variables)

    def addresses(self):
        return filter(
            lambda x: x.startswith('BM-'), BMConfigParser().sections())

    def read(self, filenames):
        """Read config from file or list of files"""
        ConfigParser.ConfigParser.read(self, filenames)
        if isinstance(filenames, str):
            self._src = filenames
        for section in self.sections():
            for option in self.options(section):
                try:
                    if not self.validate(
                        section, option,
                        ConfigParser.ConfigParser.get(self, section, option)
                    ):
                        try:
                            newVal = BMConfigDefaults[section][option]
                        except KeyError:
                            continue
                        ConfigParser.ConfigParser.set(
                            self, section, option, newVal)
                except ConfigParser.InterpolationError:
                    continue

    def save(self, filename=None):
        """Save config to filename or to file from which it was read"""
        if not filename:
            filename = self._src
        filename_bak = '.'.join([
            filename, datetime.now().strftime("%Y%j%H%M%S%f"), 'bak'])
        # create a backup copy to prevent the accidental loss due to
        # the disk write failure
        try:
            shutil.copyfile(filename, filename_bak)
            # The backup succeeded.
            fileNameExisted = True
        except (IOError, Exception):
            # The backup failed. This can happen if the file
            # didn't exist before.
            fileNameExisted = False
        # write the file
        with open(filename, 'wb') as configfile:
            self.write(configfile)
        # delete the backup
        if fileNameExisted:
            os.remove(filename_bak)

    def validate(self, section, option, value):
        try:
            return getattr(self, 'validate_%s_%s' % (section, option))(value)
        except AttributeError:
            return True

    def validate_bitmessagesettings_maxoutboundconnections(self, value):
        try:
            value = int(value)
        except ValueError:
            return False
        if value < 0 or value > 8:
            return False
        return True
