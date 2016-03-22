
from hashlib import md5

from common import *

def fileHash (filename):

	m = md5 ()
	m.update (fileText (filename))
	return m.hexdigest ()

def loadHashCache ():

	env.hashes = dict(i.split(" ") for i in filter (None,fileText("HashCache").split("\n")))
	env.newHashes = dict (env.hashes)

def storeHashCache ():

	open("HashCache","w").write("\n".join(k+" "+v for k,v in env.newHashes.items()))

def cachedHash (filename):

	try:
		return env.hashes[filename]
	except KeyError:
		return ""

def cacheHash (filename, curHash):

	env.newHashes[filename] = curHash

