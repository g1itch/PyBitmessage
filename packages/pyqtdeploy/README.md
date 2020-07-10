This directory contains the files needed for building pyqtdeploy bundle.

Now you can manually build the bundle for linux. Assuming your sysroot
dir will be in SYSROOTDIR (you'll need about 6GB free space there for
building Qt) and sources - in SOURCEDIR, the build steps are following:

1. cd $SOURCEDIR && exec /path/to/PyBitmessage/packages/pyqtdeploy/download.sh
1. cd /path/to/PyBitmessage/packages/pyqtdeploy
1. pyqtdeploy-sysroot --source-dir $SOURCEDIR --sysroot $SYSROOTDIR --target linux-64 --plugin-dir plugins sysroot.json
1. virtualenv depends
1. source depends/bin/activate
1. pip install enum34 msgpack qtpy stem
1. deactivate
1. pyqtdeploy-build --sysroot $SYSROOTDIR --target linux-64 pybitmessage.pdy
1. cd build-linux-64
1. mv resources/src resources/pybitmessage
1. sed -i "s|src/|pybitmessage/|g" resources/pyqtdeploy.qrc
1. $SYSROOTDIR/host/bin/qmake
1. make

The resulting PyBitmessage binary may require some shared libraries,
particularly openssl.

There is also a possible issue with pyexpat related to `sqlite3`:

```
2020-07-10 18:36:01,135 - WARNING - Using default logger configuration
2020-07-10 18:36:01,517 - CRITICAL - Unhandled exception
Traceback (most recent call last):
  File ":/src/bitmessagemain.py", line 477, in main
  File ":/src/bitmessagemain.py", line 354, in start
  File ":/src/bitmessageqt/__init__.py", line 4288, in run
  File ":/src/bitmessageqt/__init__.py", line 595, in __init__
  File ":/src/bitmessageqt/bitmessageui.py", line 542, in setupUi
  File ":/src/bitmessageqt/blacklist.py", line 18, in __init__
  File ":/src/bitmessageqt/widgets.py", line 25, in load
  File ":/PyQt5/uic/__init__.pyo", line 226, in loadUi
  File ":/PyQt5/uic/Loader/loader.pyo", line 72, in loadUi
  File ":/PyQt5/uic/uiparser.pyo", line 1013, in parse
  File ":/xml/etree/ElementTree.py", line 1182, in parse
  File ":/xml/etree/ElementTree.py", line 651, in parse
  File ":/xml/etree/ElementTree.py", line 1476, in __init__
  File ":/xml/parsers/expat.py", line 4, in <module>
SystemError: _PyImport_FixupExtension: module pyexpat not loaded
```

---
ref:
(pyqtdeploy v2.5.1 User Guide)[https://www.riverbankcomputing.com/static/Docs/pyqtdeploy/index.html]
(medium article)[https://medium.com/@Lola_Dam/packaging-pyqt-application-using-pyqtdeploy-for-both-linux-and-android-32ac7824708b]
