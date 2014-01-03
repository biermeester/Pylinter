Pylinter Sublime Text 2/3 Plugin
------------------------------

Introduction
============

This is a small plugin for Sublime Text 2 and 3 that allows automatic Python
source code checking by Pylint.

Since Pylint can take a while before it has completed its task (multiple
seconds), it is run from a separate thread, so the plugin won't lock up Sublime
Text.

The plugin can be automatically invoked *on save* or by a keyboard shortcut.

Support for Pylint configuration files is included.

**Note**::

    ** Pylint needs to be installed separately!!! **

    If you have installed Pylint into a Virtualenv, you need to launch Sublime
    Text from that Virtualenv for everything to work correctly. This might be
    resolved in the future.

Latest changes
==============

**2014-03-03**

Added support for Pylint plugins. You can add a list of plugin module names into
your configuration using the `plugins` setting.

**2013-11-15**

Some refactoring has been done to make sure Pylinter works better under ST3.
Also, the error handling, in case `Pylint` cannot be found, is improved.

**2013-09-06**

Improved Pylint detection and a Pylint version check bug fix.

**2013-09-01**

This is the first version of Pylinter that is both compatible with Sublime
Text 2 and 3. Please feel free to report any issues. And many thank-yous to
everyone reporting issues and supplying solutions in regards to Python 3
compatibility.

**2013-08-24**

Thanks to dbader for the Pylint 1.0 support

* Pylinter now automatically detects what version of Pylint is used and is both
  compatible with the new 1.0.0 version and the older ones.

**2013-01-20**

Thanks to KristoforMaynard for the following additions:

* When the ``message_stay`` setting is set to ``true``, the error messages will
  be displayed as long as the cursor stays on the offending line.
* The ``disable_outline`` setting can be set to ``true`` to hide the outlines of
  errors.
* The ``disable`` setting can be assigned a list or errors to ignore. E.g.
  ["C0301", "E1011"]

**2012-09-12**

* Pylinter will now try and automatically find the path to Pylint.

**2012-09-06**

* Pylinter now allows for platform and/or host specific configuration to be
  stored in a single configuration file. This is particulary useful for the
  ``pylint_path`` setting.

  Simply change a setting like

  ``"pylint_path": "<your pylint path>"``

  into something like this::

    "pylint_path": {
        "#multiconf#": [
            {"os:windows": "<your windows pylint path>"},
            {"os:linux;host:<host name": "<your linux pylint path>"},
            {"os:linux;host:<other host name": "<your other linux pylint path>"}
        ]
      }

  For more information you can have a look at the following `gist`_.

**2012-08-31**

* Added icons for different message types. You can use these icons by
  setting the option ``use_icons`` to ``true`` (Icons by `Yusuke Kamiyamane`_).

**2012-08-29**

* Added an 'ignore' function, allowing for easy insertion of
  ``#pylint: disable=`` statements/comments.
* Included wuub's error colouring. Either use the included
  ``MonokaiPylinter.tmTheme`` file, or have a look at it to see how you can
  colour the different erros and warnings.



Configuration
=============

Pylinter will try and determine the path to Pylint. If it fails you *must*
provide a full path to the ``lint.py`` module of your Pylint installation!

* **python_bin**: The full path to the Python executable you want to use for
    running   Pylint (e.g. when you are using virtualenv) or simply ``python``
    if you want to use   your default python installation.

* **python_path**: An optional list of paths that will be added to Pylint's
    Python path.

* **working_dir**: An optional path to the working directory from which Pylint
    will be run.

* **pylint_path**: The full path to the ``lint.py`` module.

* **pylint_rc**: The full path to the Pylint configuration file you want to use,
    if any.

* **run_on_save**: If this setting is set to ``true``, Pylint will be invoked
    each time you save a Python source code file.

* **ignore**: A list of Pylint error types which you wish to ignore.

    Possible values:

    * "R" : Refactor for a "good practice" metric violation
    * "C" : Convention for coding standard violation
    * "W" : Warning for stylistic problems, or minor programming issues
    * "E" : Error for important programming issues (i.e. most probably bug)
    * "F" : Fatal for errors which prevented further processing

* **use_icons**: Set to ``true`` if you want to display icons instead of dots in
  the margin.

Multiconf
~~~~~~~~~

Any setting can be replaced by a Multiconf structure ::

    "pylint_path": {
        "#multiconf#": [
            {"os:windows": "<your windows pylint path>"},
            {"os:linux;host:<host name": "<your linux pylint path>"},
            {"os:linux;host:<other host name": "<your other linux pylint path>"}
        ]
      }

For more information you can have a look at the following `gist`_.

Project settings
~~~~~~~~~~~~~~~~

You may also store settings in your *.sublime-project files. Create a
``"pylinter"`` section as shown below and override any or all of the described
settings::

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

.. _gist: https://gist.github.com/3646966
.. _Yusuke Kamiyamane: http://p.yusukekamiyamane.com/
