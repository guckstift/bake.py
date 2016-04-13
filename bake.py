#!/usr/bin/python2

"""
  bake.py - a python-style make tool
   author: Danny Raufeisen
   email: guckstift@posteo.de
"""

import sys
from shutil import copy, rmtree

from common import *
from targets import *
from resources import *
from gspkg import *
from cache import *

projectFileNames = [ "project.py", "Project" ]

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
	
	if env.optPrintTree:
		printDepTree ()
	elif len (env.cliTargets) != 0:
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
		fs = open ("bake", "w")
		fs.write (open ("./bake.py/launcher.py", "r").read ())
		fs.close ()
		shell ("chmod +x ./bake", prints="oe")
	
	if not exists (".gitignore"):
		open (".gitignore", "w").close ()
	
	gitIgnores = filter (None, fileText (".gitignore").split ("\n"))
	
	if "bake.py" not in gitIgnores:
		print "\033[95mAdding 'bake.py' directory to your .gitignore ...\033[0m"
		gitIgnores.append ("bake.py")
		fs = open (".gitignore", "w")
		fs.write ("\n".join (gitIgnores))
		fs.close ()
	if "gspkgs" not in gitIgnores:
		print "\033[95mAdding 'gspkgs' directory to your .gitignore ...\033[0m"
		gitIgnores.append ("gspkgs")
		fs = open (".gitignore", "w")
		fs.write ("\n".join (gitIgnores))
		fs.close ()

	missing = []
	
	if shell ("git --version", "code", dofail=False) != 0:
		missing.append ("'git'")
	if shell ("pkg-config --version", "code", dofail=False) != 0:
		missing.append ("'pkg-config'")
	if shell ("g++ --version", "code", dofail=False) != 0:
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
	if "-t" in opts:
		env.optPrintTree = True
	
	env.cliTargets = targets

def printDepTree (target = None, indentLvl = 0):

	if target is None:
		target = env.default
		
	print "  "*indentLvl + target
	
	if target in env.rules:
		for dep in env.rules [target][1]:
			printDepTree (dep, indentLvl + 1)

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
	
		rawPrintInfo ("Do")
		if env.verbose:
			print ' "' + target + '"' + (" (deps: " + ", ".join (deps) + ")" if deps else "")
		else:
			rawPrint ('"' + target + '" ')
		
		bakeRecipe (recipe)
		printOk ("OK")
		hasChanged = depsChanged
	
	elif not exists (target) or depsChanged:
	
		rawPrintInfo ("Update")
		if env.verbose:
			print '"' + target + '"' + (" (deps: " + ", ".join (deps) + ")" if deps else "")
		else:
			rawPrint ('"' + target + '" ')
		
		shell ("mkdir -p " + dirname (target), prints="oe", dofail=False)
		
		bakeRecipe (recipe)
		
		if not exists (target):
			fail ("Error: Target \""+target+"\" was not baked by its rule.")
		else:
			printOk ("OK")
		
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
			shell (cmd, prints="oe")

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

