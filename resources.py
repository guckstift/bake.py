
from common import *

def buildResListHeader (resFiles, outfilename):

	result = "".join (
		"extern unsigned long size_" + varName + ";\n" +
		"extern char* res_" + varName + ";\n"
		for varName in map (resourceVarName, resFiles)
	)
	fs = open (outfilename, "w")
	fs.write (result)
	fs.close ()

def resourceToCpp (infilename, outfilename, isBinary = False):

	if env.verbose:
		print "resourceToCpp (",infilename,",",outfilename,")"
	
	fs = open (infilename, "rb")
	data = fs.read ()
	fs.close ()
	
	varName = resourceVarName (infilename)
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


def resourceVarName (infilename):

	return infilename.replace ("/","_").replace (".","_")
	#return basename (infilename).replace (".","_")

