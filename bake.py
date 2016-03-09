#!/usr/bin/python2

#
# bake.py - a python-style make tool
#  author: Danny Raufeisen
#  email: guckstift@posteo.de
#

import subprocess
import fnmatch
import sys
from os import walk, symlink
from os.path import exists, dirname, basename, splitext
from os.path import join as pathJoin
from hashlib import md5
from sys import stdout, argv
from functools import partial
from urllib2 import urlopen
from zipfile import ZipFile
from shutil import copy, rmtree

bakeLauncherScript = """#!/usr/bin/python2

\"""
This is the launcher script for bake.py, which can be placed in and called from your projects root
directory. If the actual bake.py script is missing, it will be downloaded automatically from the
github repository.
\"""

import subprocess
import sys
import os
from os.path import exists, isfile, isdir

def shell (cmd, noError = False, retCode = False):

	if type(cmd) is list:
		cmd = " ".join (cmd)
	try:
		if retCode:
			return subprocess.call (cmd, shell=True,
				stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		else:
			return subprocess.check_output (cmd, shell=True).strip (" \\n\\t")
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

	print "\\033[91m"+msg+"\\033[0m"
	exit (ret)

if not exists ("bake.py"):
	print ("\\033[95mDownload bake.py\\033[0m")
	shell ("git clone git@github.com:guckstift/bake.py.git")

exec (fileText (
	"./bake.py" if isfile ("./bake.py") else
	"./bake.py/bake.py" if isfile ("./bake.py/bake.py") else
	""
))
"""

cppDepsTest = lambda x: shell("g++ -MM -MG "+x, True).replace ("\\\n","")
cppDeps = lambda x: filter (None, cppDepsTest(x).split(" ")[2:])
join = lambda x: " ".join (x)
projectFileNames = [ "project.py", "Project" ]
env = type ("Env", (object,), {}) ()
env.verbose = True
env.default = None
env.rules = {}
env.actions = set ()
env.depStack = []
env.gspkgs = {}
env.gspkgAutoUpdate = False
env.cliTargets = []

class GsPkg:
	def __init__ (self, name, gspkgDeps, pkgDeps, cpps):
		self.name = name
		self.gspkgDeps = gspkgDeps
		self.pkgDeps = pkgDeps
		self.cpps = cpps
	def recCpps (self):
		res = self.cpps
		for dep in self.gspkgDeps:
			gspkgdep = env.gspkgs [dep]
			subres = gspkgdep.recCpps ()
			res = mergeLists (res, subres)
		return res
	def recPkgDeps (self):
		res = self.pkgDeps
		for dep in self.gspkgDeps:
			gspkgdep = env.gspkgs [dep]
			subres = gspkgdep.recPkgDeps ()
			res = mergeLists (res, subres)
		return res
		

def main ():

	bakeInit ()

	loadHashCache ()
	
	projectFileFound = None
	
	for pfname in projectFileNames:
		if exists (pfname):
			projectFileFound = pfname
			break
	
	if projectFileFound is None:
		print "\033[91mProject file is missing.\033[0m"
		print "\033[95mCreating \"" + projectFileNames [0] + "\" ...\033[0m"
		initProjectFile ()
		projectFileFound = projectFileNames [0]
		print "\033[92mOK\033[0m"
		exit (0)
	
	evalCliOptions ()

	exec (fileText (projectFileFound))

	if len (env.cliTargets) != 0:
		for target in env.cliTargets:
			update (target)
	elif env.default:
		update (env.default)
	else:
		fail ("Neither command line targets nor \"default\" target was set.")
	
	storeHashCache ()

def bakeInit ():

	if not exists ("./bake"):
		print "\033[95mCopying 'bake' launcher into the current directory ...\033[0m"
		#symlink ("./bake.py/bake.py", "./bake")
		fs = open ("bake", "w")
		fs.write (bakeLauncherScript)
		fs.close ()
		shell ("chmod +x ./bake")
	
	if not exists (".gitignore"):
		open (".gitignore", "w").close ()
	
	gitIgnores = fileText (".gitignore").split ("\n")
	
	if "bake.py" not in gitIgnores:
		print "\033[95mAdding 'bake.py' directory to your .gitignore ...\033[0m"
		gitIgnores.append ("bake.py")
	
	fs = open (".gitignore", "w")
	fs.write ("\n".join (gitIgnores))
	fs.close ()

	missing = []
	
	if shell ("git --version", True, True) != 0:
		missing.append ("'git'")
	if shell ("pkg-config --version", True, True) != 0:
		missing.append ("'pkg-config'")
	if shell ("g++ --version", True, True) != 0:
		missing.append ("'g++'")
	
	if missing:
		fail (
			"Some dependencies needed by bake.py are missing: " + ",".join (missing) + "\n" +
			"Please install these dependencies!"
		)

def evalCliOptions ():

	args = sys.argv[1:]
	targets = list (filter (lambda a: not a.startswith ("-"), args))
	opts = list (filter (lambda a: a.startswith ("-"), args))
	
	if "-u" in opts:
		env.gspkgAutoUpdate = True
	
	env.cliTargets = targets

def addRule (target, deps = [], recipe = []):

	if type(deps) is not list:
		deps = [deps]
	if type(recipe) is not list:
		recipe = [recipe]
	env.rules[target] = (target, deps[:], recipe[:])
	return target

def addCppObject (obj, cpp, cFlags = "", nodeptest = False):

	if nodeptest:
		return addRule (obj, cpp,
			"g++ -o "+obj+" -c "+cpp+" "+cFlags
		)
	else:
		return addRule (obj, [cpp] + cppDeps(cpp),
			"g++ -o "+obj+" -c "+cpp+" "+cFlags
		)

def addBinary (bin, objs, libFlags, otherDeps = []):

	return addRule (bin, otherDeps + objs,
		"g++ -o "+bin+" "+" ".join(objs)+" "+libFlags
	)

def addResObj (resFile, resCpp, resObj, cFlags, isBinary = False):

	addRule (resCpp, resFile, partial (resourceToCpp, resFile, resCpp, isBinary))
	addCppObject (resObj, resCpp, cFlags, True)
	return resFile

def addCppBinary (bin, cpps, objs, resFiles, resCpps, resObjs, libFlags, cFlags, otherDeps = []):

	addBinary (bin, objs + resObjs, libFlags, otherDeps)
	for cpp, obj in zip (cpps, objs):
		addCppObject (obj, cpp, cFlags)
	for resFile, resCpp, resObj in zip (resFiles, resCpps, resObjs):
		addResObj (resFile, resCpp, resObj, cFlags, True)
	
	return bin

def addCppBinaryM (bin, cpps, resFiles = [], cFlags = "", pkgs = [], libFlags = "", gspkgs = []):

	cFlags += " -Igspkgs "
	
	for gspkg in gspkgs:
		loadGsPkg (gspkg)
		cpps = mergeLists (cpps, env.gspkgs [gspkg].recCpps ())
		pkgs = mergeLists (pkgs, env.gspkgs [gspkg].recPkgDeps ())

	buildDir = dirname (bin)
	objs = [buildDir+"/"+splitext(cpp)[0]+".o" for cpp in cpps]
	
	libFlags += " " + pkgConfigLibs (pkgs)
	cFlags += " " + pkgConfigCflags (pkgs)
	
	resCpps = []
	resObjs = []
	for resFile in resFiles:
		resBasename = basename(resFile).replace(".","_")
		resDirname = dirname(resFile)
		resCpp = buildDir+"/"+resDirname+"/"+resBasename+".cpp"
		resObj = buildDir+"/"+resDirname+"/"+resBasename+".o"
		resCpps.append (resCpp)
		resObjs.append (resObj)
	
	return addCppBinary (bin, cpps, objs, resFiles, resCpps, resObjs, libFlags, cFlags)

def loadGsPkg (name):

	if name not in env.gspkgs:
	
		pkgDirName = "gspkgs/" + name
		pkgZipName = pkgDirName + "/gspkg.zip"
		pkgPyName = pkgDirName + "/gspkg.py"
		pkgGithubUrl = "git@github.com:guckstift/gspkg-" + name + ".git"
	
		shell ("mkdir -p " + pkgDirName, True)
	
		if not exists (pkgPyName):
			print ("\033[95mDownload guckstift-package '" + name + "'\033[0m")
			shell ("git clone " + pkgGithubUrl + " " + pkgDirName)
		elif env.gspkgAutoUpdate:
			print ("\033[95mUpdate guckstift-package '" + name + "'\033[0m")
			shell ("git -C " + pkgDirName + " pull origin master")
	
		exec (fileText (pkgPyName))
		
		cpps = recGlob ("gspkgs/" + name + "/", "*.cpp")
		gspkg = GsPkg (name, gspkgDeps, pkgDeps, cpps)
		env.gspkgs [name] = gspkg
		
		for depname in gspkgDeps:
			loadGsPkg (depname)

def addAction (name, deps = [], recipe = []):

	if type(deps) is str:
		deps = [deps]
	if type(recipe) is str:
		recipe = [recipe]
	env.rules[name] = (name, deps[:], recipe[:])
	env.actions.add (name)
	
	return name

def addRemoveAction (name, filename):

	return addAction (name, [], "rm -rf " + filename)

def addLaunchAction (name, bin):

	return addAction (name, bin, "./"+bin)

def update (name):

	env.depStack.append (name)

	if name in env.rules:
		return updateTarget (env.rules[name])
	else:
		return updateSource (name)
	
	env.depStack.pop ()

def updateTarget (rule):

	target, deps, recipe = rule
	
	depsChanged = False
	for dep in deps:
		depsChanged = update (dep) or depsChanged
		
	if target in env.actions:
	
		if env.verbose:
			print "\033[95mDo\033[0m \""+target+"\""+(" (deps: "+", ".join(deps)+")" if deps else "")
		else:
			rawPrint ("\033[95mDo\033[0m \""+target+"\" ")
		
		bakeRecipe (recipe)
		print "\033[92mOK\033[0m"
		hasChanged = depsChanged
	
	elif not exists (target) or depsChanged:
	
		if env.verbose:
			print "\033[95mUpdate\033[0m \""+target+"\""+(" (deps: "+", ".join(deps)+")" if deps else "")
		else:
			rawPrint ("\033[95mUpdate\033[0m \""+target+"\" ")
		
		shell ("mkdir -p "+dirname(target), True)
		
		bakeRecipe (recipe)
		
		if not exists (target):
			fail ("Error: Target \""+target+"\" was not baked by its rule.")
		else:
			print "\033[92mOK\033[0m"
		
		hasChanged = True
	
	else:
		hasChanged = False # target has not changed at all
	
	return hasChanged

def updateSource (name):

	if not exists (name):
		fail ("Error: There is no rule for \""+name+"\".")

	curHash = fileHash (name)
	hasChanged = curHash != cachedHash (name)
	cacheHash (name, curHash)
	
	return hasChanged

def bakeRecipe (recipe):

	for cmd in recipe:
		if callable (cmd):
			cmd ()
		else:
			if env.verbose:
				print cmd
			shell (cmd)

def loadHashCache ():

	env.hashes = dict(i.split(" ") for i in filter (None,fileText("HashCache").split("\n")))

def storeHashCache ():

	open("HashCache","w").write("\n".join(k+" "+v for k,v in env.hashes.items()))

def cachedHash (filename):

	try:
		return env.hashes[filename]
	except KeyError:
		return ""

def cacheHash (filename, curHash):

	env.hashes[filename] = curHash

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

def pkgConfigLibs (pkgs):

	if type(pkgs) is not list:
		pkgs = pkgs.split ()
	
	return join (shell ("pkg-config --libs "+pkg) for pkg in pkgs)

def pkgConfigCflags (pkgs):

	if type(pkgs) is not list:
		pkgs = pkgs.split ()

	return join (shell ("pkg-config --cflags "+pkg) for pkg in pkgs)

def resourceToCpp (infilename, outfilename, isBinary = False):

	if env.verbose:
		print "resourceToCpp (",infilename,",",outfilename,")"
	fs = open (infilename, "rb")
	data = fs.read ()
	fs.close ()
	
	varName = basename (infilename).replace (".","_")
	result = ""
	result += "unsigned long size_" + varName + " = " + str(len(data)) + ";\n"
	if isBinary:
		result += "unsigned char res_" + varName + "[] = "
		result += "{" + ",".join (str(ord(i)) for i in data) + "};\n"
	else:
		result += "char *res_" + varName + " = "
		result += '"' + "".join (repr(i)[1:-1] for i in data) + '";\n'
	
	fs = open (outfilename, "w")
	fs.write (result)
	fs.close ()

def recGlob (path, pattern):

	res = []
	for dirpath, dirnames, files in walk (path):
		for filename in fnmatch.filter (files, pattern):
			res.append (pathJoin (dirpath, filename))
	return res

def fileText (filename):

	try:
		return open (filename).read ()
	except IOError:
		return ""

def fileHash (filename):

	m = md5 ()
	m.update (fileText (filename))
	return m.hexdigest ()

def rawPrint (msg):

	stdout.write (msg)
	stdout.flush ()

def fail (msg, ret = 1):

	print "\033[91m"+msg+"\033[0m"
	#print "\tDependency Stack: "+str(env.depStack)
	exit (ret)

def initProjectFile ():

	initialProjectFile = "\n"
	initialProjectFile += 'bin = addCppBinaryM (\n'
	initialProjectFile += '\t"build/myproject",\n'
	initialProjectFile += '\trecGlob ("src","*.cpp"),\n'
	initialProjectFile += '\tcFlags = "-std=c++11 -Wno-write-strings -Wno-pointer-arith",\n'
	initialProjectFile += ')\n\n'
	initialProjectFile += 'build = addAction ("build", bin)\n'
	initialProjectFile += 'clean = addRemoveAction ("clean", dirname (bin))\n'
	initialProjectFile += 'rebuild = addAction ("rebuild", [clean, build])\n'
	initialProjectFile += 'launch = addLaunchAction ("launch", bin)\n\n'
	initialProjectFile += 'env.default = build\n'
	initialProjectFile += 'env.verbose = True\n\n'
	
	fs = open (projectFileNames [0], "w")
	fs.write (initialProjectFile)
	fs.close ()

def mergeLists (la, lb):

	lc = []
	for i in la + lb:
		if i not in lc:
			lc.append (i)
	return lc

if __name__ == "__main__":
	main ()

