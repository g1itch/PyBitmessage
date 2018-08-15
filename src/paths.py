import os
import re
import sys

# When using py2exe or py2app, the variable frozen is added to the sys
# namespace.  This can be used to setup a different code path for
# binary distributions vs source distributions.
frozen = getattr(sys, 'frozen', None)


def lookupExeFolder():
    if frozen:
        if frozen == "macosx_app":
            # targetdir/Bitmessage.app/Contents/MacOS/Bitmessage
            exeFolder = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(sys.executable)
            )))
        else:
            exeFolder = os.path.dirname(sys.executable)
    elif __file__:
        exeFolder = os.path.dirname(__file__)
    else:
        return ''
    return exeFolder + os.path.sep


def lookupAppdataFolder():
    APPNAME = "PyBitmessage"
    try:  # for daemon
        dataFolder = os.environ["BITMESSAGE_HOME"]
        if dataFolder[-1] not in (os.path.sep, os.path.altsep):
            dataFolder += os.path.sep
    except KeyError:
        pass
    else:
        return dataFolder

    if sys.platform == 'darwin':
        try:
            dataFolder = os.path.join(
                os.environ["HOME"], "Library/Application Support/", APPNAME)
        except KeyError:
            log_msg = (
                'Could not find home folder, please report this message'
                ' and your OS X version to the BitMessage Github.'
            )
            try:
                logger.critical(log_msg)
            except NameError:
                print(log_msg)
            sys.exit(1)

    elif 'win32' in sys.platform or 'win64' in sys.platform:
        dataFolder = os.path.join(os.environ['APPDATA'].decode(
            sys.getfilesystemencoding(), 'ignore'), APPNAME)
    else:
        from shutil import move
        try:
            config_dir = os.environ["XDG_CONFIG_HOME"]
        except KeyError:
            config_dir = os.path.join(os.environ["HOME"], ".config")

        dataFolder = os.path.join(config_dir, APPNAME)

        # Migrate existing data to the proper location
        # if this is an existing install
        try:
            move(
                os.path.join(os.environ["HOME"], ".%s" % APPNAME), dataFolder)
            log_msg = "Moving data folder to %s" % dataFolder
            try:
                logger.info(log_msg)
            except NameError:
                print(log_msg)
        except IOError:
            # Old directory may not exist.
            pass

    return dataFolder + os.path.sep


def codePath():
    if frozen == "macosx_app":
        codePath = os.environ.get("RESOURCEPATH")
    elif frozen:  # windows
        codePath = sys._MEIPASS
    else:
        codePath = os.path.dirname(__file__)
    return codePath


def tail(f, lines=20):
    total_lines_wanted = lines

    BLOCK_SIZE = 1024
    f.seek(0, 2)
    block_end_byte = f.tell()
    lines_to_go = total_lines_wanted
    block_number = -1
    # blocks of size BLOCK_SIZE, in reverse order starting
    # from the end of the file
    blocks = []
    while lines_to_go > 0 and block_end_byte > 0:
        if (block_end_byte - BLOCK_SIZE > 0):
            # read the last block we haven't yet read
            f.seek(block_number * BLOCK_SIZE, 2)
            blocks.append(f.read(BLOCK_SIZE))
        else:
            # file too small, start from begining
            f.seek(0, 0)
            # only read what was not read
            blocks.append(f.read(block_end_byte))
        lines_found = blocks[-1].count('\n')
        lines_to_go -= lines_found
        block_end_byte -= BLOCK_SIZE
        block_number -= 1
    all_read_text = ''.join(reversed(blocks))
    return '\n'.join(all_read_text.splitlines()[-total_lines_wanted:])


def lastCommit():
    githeadfile = os.path.join(codePath(), '..', '.git', 'logs', 'HEAD')
    result = {}
    if os.path.isfile(githeadfile):
        try:
            with open(githeadfile, 'rt') as githead:
                line = tail(githead, 1)
            result.update(
                commit=line.split()[1],
                time=float(re.search(r'>\s*(.*?)\s', line).group(1))
            )
        except (IOError, AttributeError, TypeError):
            pass
    return result
