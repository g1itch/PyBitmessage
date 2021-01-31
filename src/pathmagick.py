import os
import sys


def setup():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_dir)
    sys.path.insert(0, app_dir)
