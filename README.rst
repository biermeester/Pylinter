Pylinter Sublime Text 2 Plugin
------------------------------

Latest changes
==============

**2012-08-31**

* Added an 'ignore' function, allowing for easy insertion of ``#pylint: disable=``
  statements/comments.
* Included wuub's error colouring. Either use the included ``MonokaiPylinter.tmTheme``
  file, or have a look at it to see how you can colour the different erros and
  warnings.
* Added icons for different message types. You can use the previous dot icons by
  setting the option ``use_icons`` to ``false`` (Icons by `Yusuke Kamiyamane`_).

Introduction
============

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
  Pylint (e.g. when you are using virtualenv) or simply ``python`` if you want to use
  your default python installation.

* **python_path**: An optional list of paths that will be added to Pylint's Python path.

* **working_dir**: An optional path to the working directory from which Pylint will be run.

* **pylint_path**: The full path to the ``lint.py`` module.

* **pylint_rc**: The full path to the Pylint configuration file you want to use, if any.

* **run_on_save**: If this setting is set to ``true``, Pylint will be invoked each time
  you save a Python source code file.

* **ignore**: A list of Pylint error types which you wish to ignore.

  Possible values:

  * "R" : Refactor for a "good practice" metric violation
  * "C" : Convention for coding standard violation
  * "W" : Warning for stylistic problems, or minor programming issues
  * "E" : Error for important programming issues (i.e. most probably bug)
  * "F" : Fatal for errors which prevented further processing

Project settings
~~~~~~~~~~~~~~~~

You may also store settings in your *.sublime-project files. Create a ``"pylinter"``
section as shown below and override any or all of the described settings::

    {
        "folders":
        [
            {
                "path": "/N/development/fabrix"
            }
        ],
        "settings":
        {
            "pylinter":
            {
            }
        }
    }


Commands & Keyboard Shortcuts
=============================

**Run**

The plugin can be invoked by a keyboard shortcut:

* **OS X**: ``Command+Alt+z``
* **Linux, Windows**: ``Control+Alt+z``

**Add pylint ignore comment/statement**

Add a 'Pylint disable' comment to the end of the line with an error code in it,
so it will be ignored on the next check.

* **OS X**: ``Command+Alt+i``
* **Linux, Windows**: ``Control+Alt+i``

**Toggle Marking**

The marking of the errors in the file can be toggled off and on:

* **OS X**: ``Command+Alt+x``
* **Linux, Windows**: ``Control+Alt+x``

**Quick List**

To see a quick list of all the Pylint errors use:

* **OS X**: ``Command+Alt+c``
* **Linux, Windows**: ``Control+Alt+c``

.. _Yusuke Kamiyamane: http://p.yusukekamiyamane.com/
