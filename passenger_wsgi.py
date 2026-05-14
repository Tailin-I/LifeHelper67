import sys
import os

INTERP = sys.executable
if INTERP not in open(__file__).read():
    os.execl(INTERP, INTERP, *sys.argv)

from app import app as application