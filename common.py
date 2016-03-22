
import fnmatch
import subprocess
from os import walk, symlink
from os.path import exists, dirname, basename, splitext
from os.path import join as pathJoin
from functools import partial
from sys import stdout, argv

env = type ("Env", (object,), {}) ()
env.verbose = True
env.default = None
env.rules = {}
env.actions = set ()
env.depStack = []
env.gspkgs = {}
env.gspkgAutoUpdate = False
env.cliTargets = []
env.optPrintTree = False

join = lambda x: " ".join (x)
cppDepsTest = lambda x: shell("g++ -MM -MG "+x, dofail=False).replace ("\\\n","")
cppDeps = lambda x: filter (None, cppDepsTest(x).split(" ")[2:])

def shell (cmd, returns = "output", prints = "", dofail = True):
	"""
	returns:
		"output" - return output
		"code" - return code
	prints:
		"" - print nothing
		"o" - print stdout
		"e" - print stderr
		"oe" - print stdout and stderr
	dofail:
		True - FAIL on nonzero exit code
		False - just don't fail
	"""

	if type(cmd) is list:
		cmd = " ".join (cmd)
	
	po = subprocess.Popen (cmd,
		shell = True,
		stdout = subprocess.PIPE,
		stderr = subprocess.PIPE if "e" not in prints else None,
	)
	
	output = ""
	while True:
		oc = po.stdout.read (1)
		if oc == "": break
		output += oc
		if "o" in prints:
			rawPrint (oc)
	
	po.wait ()
	
	if dofail and po.returncode != 0:
		fail ("FAIL", po.returncode)
	elif returns == "output":
		return output.strip (" \n\t")
	elif returns == "code":
		return po.returncode

def fileText (filename):

	try:
		return open (filename).read ()
	except IOError:
		return ""

def recGlob (path, pattern):

	res = []
	for dirpath, dirnames, files in walk (path):
		for filename in fnmatch.filter (files, pattern):
			res.append (pathJoin (dirpath, filename))
	return res

def mergeLists (la, lb):

	lc = []
	for i in la + lb:
		if i not in lc:
			lc.append (i)
	return lc

def pkgConfigLibs (pkgs):

	if type(pkgs) is not list:
		pkgs = pkgs.split ()
	
	return join (shell ("pkg-config --libs "+pkg) for pkg in pkgs)

def pkgConfigCflags (pkgs):

	if type(pkgs) is not list:
		pkgs = pkgs.split ()

	return join (shell ("pkg-config --cflags "+pkg) for pkg in pkgs)

def rawPrint (msg):

	stdout.write (msg)
	stdout.flush ()

def rawPrintFail (msg):

	rawPrint ("\033[91m" + msg + "\033[0m")

def printFail (msg):

	rawPrintFail (msg + "\n")

def rawPrintOk (msg):

	rawPrint ("\033[92m" + msg + "\033[0m")

def printOk (msg):

	rawPrintOk (msg + "\n")

def rawPrintInfo (msg):

	rawPrint ("\033[95m" + msg + "\033[0m")

def printInfo (msg):

	rawPrintInfo (msg + "\n")

def fail (msg, ret = 1):

	rawPrintFail (msg + "(" + str (ret) + ")\n")
	#print "\tDependency Stack: "+str(env.depStack)
	exit (ret)

