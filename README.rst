Pylinter Sublime Text 2 Plugin
------------------------------

This is a small plugin for Sublime Text 2 that allows automatic Python
source code checking by Pylint.

Since Pylint can take a while before it has completed its task (multiple seconds),
it is run from a separate thread, so the plugin won't lock up Sublime Text.

The plugin can be automatically invoked *on save* or by a keyboard shortcut.

Support for Pylint configuration files is included.

**Note**::

    Pylint needs to be installed separately!

Configuration
=============

Before the plugin can be used, you *must* provide a full path to the ``lint.py``
module of your Pylint installation!

* **python_bin**: The full path to the Python executable you want to use for running
  Pylint or simply ``python`` if you want to use your default python installation.

* **pylint_path**: The full path to the ``lint.py`` module.

* **pylint_rc**: The full path to the Pylint configuration file you want to use, if any.

* **run_on_save**: If this setting is set to ``true``, Pylint will be invoked each time
  you save a Python sourc code file.

* **ignore**: A list of Pylint error types which you wish to ignore.

  Possible values:

  * "R" : Refactor for a "good practice" metric violation
  * "C" : Convention for coding standard violation
  * "W" : Warning for stylistic problems, or minor programming issues
  * "E" : Error for important programming issues (i.e. most probably bug)
  * "F" : Fatal for errors which prevented further processing

Commands & Keyboard Shortcuts
=============================

**Run**

The plugin can be invoked by a keyboard shortcut:

* **OS X**::

  run: Command+Alt+z

* **Linux, Windows**::

  run: Control+Alt+z

**Toggle Marking**
The marking of the errors in the file can be toggled off and on:

* **OS X**::

  run: Command+Alt+x

* **Linux, Windows**::

  run: Control+Alt+x

**Quick List**
To see a quick list of all the Pylint errors use:

* **OS X**::

  run: Command+Alt+c

* **Linux, Windows**::

  run: Control+Alt+c
