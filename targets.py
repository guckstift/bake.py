
from gspkg import *
from resource import *

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

	if type (otherDeps) is not list:
		otherDeps = [otherDeps]
	
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
		addResObj (resFile, resCpp, resObj, cFlags) #, True)
	
	return bin

def addCppBinaryM (bin, cpps, resFiles = [], cFlags = "", pkgs = [], libFlags = "", gspkgs = []):
	"""
	Adds a target to build the binary 'bin' from several C++ source files 'cpps' including
	resource files 'resFiles' via the resource loading system, with compiler flags 'cFlags',
	additional library flags 'libFlags' packages included through the 'pkg-config' tool and
	guckstift packages 'gspkgs'.
	"""

	cFlags += " -Igspkgs "
	
	for gspkg in gspkgs:
		loadGsPkg (gspkg)
		cpps = mergeLists (cpps, env.gspkgs [gspkg].recCpps ())
		pkgs = mergeLists (pkgs, env.gspkgs [gspkg].recPkgDeps ())
		resFiles = mergeLists (resFiles, env.gspkgs [gspkg].recResFiles ())
	
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
	
	# add target for resource list header
	resListHeaderDir = buildDir + "/reslist"
	resListHeader = resListHeaderDir + "/reslist.h"
	cFlags += " -I" + resListHeaderDir + " "
	addRule (
		resListHeader, resFiles, partial (
			buildResListHeader, resFiles, resListHeader
		)
	)
	
	return addCppBinary (
		bin, cpps, objs, resFiles, resCpps, resObjs, libFlags, cFlags, resListHeader
	)

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

