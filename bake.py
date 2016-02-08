#!/usr/bin/python2

#
# bake.py - a python-style make tool
#  author: Danny Raufeisen
#  email: guckstift@posteo.de
#

import subprocess
from os.path import exists, dirname, basename, splitext
from hashlib import md5
from sys import stdout, argv
from functools import partial

cppDepsTest = lambda x: shell("g++ -MM -MG "+x, True).replace ("\\\n","")
cppDeps = lambda x: filter (None, cppDepsTest(x).split(" ")[2:])

def main ():

	global env
	class Env: pass
	env = Env ()
	
	env.verbose = True
	env.default = None
	env.rules = {}
	env.actions = set()
	env.depStack = []

	loadHashCache ()

	if exists ("Project"):
		exec (fileText ("Project"))
	else:
		fail ("\"Project\" file is missing.")

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

def addCppObject (obj, cpp, cFlags = "", nodeptest = False):

	if nodeptest:
		addRule (obj, cpp,
			"g++ -o "+obj+" -c "+cpp+" "+cFlags
		)
	else:
		addRule (obj, [cpp] + cppDeps(cpp),
			"g++ -o "+obj+" -c "+cpp+" "+cFlags
		)

def addBinary (bin, objs, libFlags):

	addRule (bin, objs,
		"g++ -o "+bin+" "+" ".join(objs)+" "+libFlags
	)

def addResObj (resFile, resCpp, resObj, cFlags, isBinary = False):

	addRule (resCpp, resFile, partial (resourceToCpp, resFile, resCpp, isBinary))
	addCppObject (resObj, resCpp, cFlags, True)

def addCppBinary (bin, cpps, objs, resFiles, resCpps, resObjs, libFlags, cFlags):

	addBinary (bin, objs + resObjs, libFlags)
	for cpp, obj in zip (cpps, objs):
		addCppObject (obj, cpp, cFlags)
	for resFile, resCpp, resObj in zip (resFiles, resCpps, resObjs):
		addResObj (resFile, resCpp, resObj, cFlags)

def addCppBinaryM (exeName, buildDir, cpps, resFiles = [], libFlags = "", cFlags = ""):

	bin = buildDir+"/"+exeName
	objs = [buildDir+"/"+splitext(cpp)[0]+".o" for cpp in cpps]
	resCpps = [buildDir+"/"+basename(resFile).replace(".","_")+".cpp" for resFile in resFiles]
	resObjs = [buildDir+"/"+basename(resFile).replace(".","_")+".o" for resFile in resFiles]
	addCppBinary (bin, cpps, objs, resFiles, resCpps, resObjs, libFlags, cFlags)

def addAction (name, deps = [], recipe = []):

	if type(deps) is str:
		deps = [deps]
	if type(recipe) is str:
		recipe = [recipe]
	env.rules[name] = (name, deps[:], recipe[:])
	env.actions.add (name)

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
		
		shell ("mkdir -p "+dirname(target))
		
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

def pkgConfigLibs (pkg):

	return shell ("pkg-config --libs "+pkg)

def pkgConfigCflags (pkg):

	return shell ("pkg-config --cflags "+pkg)

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

if __name__ == "__main__":
	main ()

