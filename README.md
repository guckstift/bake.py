bake.py
=======

bake.py is a make tool written in Python for GNU/Linux currently optimized for C++ projects.

Easily install it into your own project with:

* `git clone git@github.com:guckstift/bake.py.git`

This will clone bake.py into a subdirectory `./bake.py/`.

Then do an initial call to bake.py with:

* `./bake.py/bake.py`

Now you have a launcher script `bake` in your project's root directory and an initial `project.py`.
Also bake.py will add its own subdirectory to your `.gitignore` list to prevent it from being
checked in into your own project's repository.

project.py
----------

This Python script is where you setup all your project's build configuration. It consists of a
couple of `add* ()` calls to set up rules for each target to be build, as well as some environment
variable settings for bake.py.

Documentation on each of the `add* ()` methods will follow soon...
