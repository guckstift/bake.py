#!/usr/bin/python2

"""
This is the launcher script for bake.py, which can be placed in and called from your projects root
directory. If the actual bake.py script is missing, it will be downloaded automatically from the
github repository.
"""

import subprocess
import sys
import os
from os.path import exists, isfile, isdir
from sys import path as sysPath

def shell (cmd, noError = False, retCode = False):

	if type(cmd) is list:
		cmd = " ".join (cmd)
	try:
		if retCode:
			return subprocess.call (cmd, shell=True,
				stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		else:
			return subprocess.check_output (cmd, shell=True).strip (" \n\t")
	except subprocess.CalledProcessError as e:
		if retCode:
			return e.returncode
		elif noError:
			return ""
		else:
			fail ("FAIL", e.returncode)

def fileText (filename):

	try:
		return open (filename).read ()
	except IOError:
		return ""

def fail (msg, ret = 1):

	print "\033[91m"+msg+"\033[0m"
	exit (ret)

if not exists ("bake.py"):
	print ("\033[95mDownload bake.py\033[0m")
	shell ("git clone git@github.com:guckstift/bake.py.git")

if isfile ("./bake.py/bake.py"):
	sysPath.insert (0, "bake.py")

from bake import main
main ()

