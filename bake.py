#!/usr/bin/python2

#
# bake.py - a python-style make tool
#  author: Danny Raufeisen
#  email: guckstift@posteo.de
#

import subprocess
import fnmatch
import sys
from os import walk
from os.path import exists, dirname, basename, splitext
from os.path import join as pathJoin
from hashlib import md5
from sys import stdout, argv
from functools import partial
from urllib2 import urlopen
from zipfile import ZipFile
from shutil import copy, rmtree

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

def main ():

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

	exec (fileText (projectFileFound))

	if len(argv) > 1:
		update (argv[1])
	elif env.default:
		update (env.default)
	else:
		fail ("No \"default\" target was set.")
	
	storeHashCache ()

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
		for gspkgCpp in recGlob ("gspkgs/", "*.cpp"):
			cpps.append (gspkgCpp)
	
	for gspkg in env.gspkgs:
		pkgs += env.gspkgs [gspkg]

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

def manualLoadGsPkg (gspkg):

	pkgDirName = "gspkgs/" + gspkg
	pkgZipName = pkgDirName + "/gspkg.zip"
	pkgPyName = pkgDirName + "/gspkg.py"
	
	shell ("mkdir -p " + pkgDirName, True)
	
	if not exists (pkgPyName):
		if not exists (pkgZipName):
			print ("\033[95mDownload guckstift-package '" + gspkg + "'\033[0m")
			ufs = urlopen ("https://github.com/guckstift/gspkg-" + gspkg + "/archive/master.zip")
			fs = open (pkgZipName, "wb")
			fs.write (ufs.read ())
			fs.close ()
		print ("Unpack gs package '" + gspkg + "'")
		unzippedDir = pkgDirName + "/gspkg-" + gspkg + "-master"
		zf = ZipFile (pkgZipName)
		zf.extractall (pkgDirName)
		zf.close ()
		fileList = recGlob (unzippedDir,"*")
		for f in fileList:
			copy (f, pkgDirName)
		rmtree (unzippedDir)
	
	exec (fileText (pkgPyName))
	
	for gspkgDep in gspkgDeps:
		manualLoadGsPkg (gspkgDep)

def loadGsPkg (gspkg):

	pkgDirName = "gspkgs/" + gspkg
	pkgZipName = pkgDirName + "/gspkg.zip"
	pkgPyName = pkgDirName + "/gspkg.py"
	pkgGithubUrl = "https://github.com/guckstift/gspkg-" + gspkg + ".git"
	
	shell ("mkdir -p " + pkgDirName, True)
	
	if not exists (pkgPyName):
		print ("\033[95mDownload guckstift-package '" + gspkg + "'\033[0m")
		shell ("git clone " + pkgGithubUrl + " " + pkgDirName)
	else:
		print ("\033[95mUpdate guckstift-package '" + gspkg + "'\033[0m")
		shell ("git -C "+pkgDirName+" pull origin master")
	
	exec (fileText (pkgPyName))
	
	for gspkgDep in gspkgDeps:
		loadGsPkg (gspkgDep)

	if gspkg not in env.gspkgs:
		env.gspkgs [gspkg] = pkgDeps

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

def shell (cmd, noError = False):

	if type(cmd) is list:
		cmd = " ".join (cmd)
	try:
		return subprocess.check_output (cmd, shell=True).strip (" \n\t")
	except subprocess.CalledProcessError as e:
		if noError:
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

if __name__ == "__main__":
	main ()

