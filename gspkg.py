
from common import *
from resource import *

class GsPkg:
	def __init__ (self, name, gspkgDeps, pkgDeps, cpps, resFiles):
		self.name = name
		self.gspkgDeps = gspkgDeps
		self.pkgDeps = pkgDeps
		self.cpps = cpps
		self.resFiles = [ "gspkgs/"+name+"/"+resFile for resFile in resFiles ]
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
	def recResFiles (self):
		res = self.resFiles
		for dep in self.gspkgDeps:
			gspkgdep = env.gspkgs [dep]
			subres = gspkgdep.recResFiles ()
			res = mergeLists (res, subres)
		return res

def loadGsPkg (name):

	if name not in env.gspkgs:
	
		pkgDirName = "gspkgs/" + name
		pkgZipName = pkgDirName + "/gspkg.zip"
		pkgPyName = pkgDirName + "/gspkg.py"
		pkgGithubUrl = "git@github.com:guckstift/gspkg-" + name + ".git"
		pkgGithubUrl2 = "git@github.com:guckstift/" + name + ".git"
	
		shell ("mkdir -p " + pkgDirName, prints="oe", dofail=False)
	
		if not exists (pkgPyName):
			print ("\033[95mDownload guckstift-package '" + name + "'\033[0m")
			code = shell (
				"git clone " + pkgGithubUrl + " " + pkgDirName,
				returns="code", prints="oe", dofail=False
			)
			if code != 0:
				code = shell (
					"git clone " + pkgGithubUrl2 + " " + pkgDirName,
					returns="code", prints="oe", dofail=False
				)
			if code != 0:
				fail ("could not download guckstift package '" + name + "'.")
		elif env.gspkgAutoUpdate:
			print ("\033[95mUpdate guckstift-package '" + name + "'\033[0m")
			shell ("git -C " + pkgDirName + " pull origin master", prints="oe")
	
		exec (fileText (pkgPyName))
		
		cpps = recGlob ("gspkgs/" + name + "/", "*.cpp")
		gspkg = GsPkg (name, gspkgDeps, pkgDeps, cpps, resFiles)
		env.gspkgs [name] = gspkg
		
		for depname in gspkgDeps:
			loadGsPkg (depname)

