# -*- coding: utf-8 -*-

import socket
import sublime
import re

""" Multiconf is a module that allows you to read platforma and/or host
specific configuration values to be used by Sublime Text 2 plugins.

Using this module's `get` function, allows the user to replace any settings
value in a '.settings' file with a dictionary containing multiple values.

Mulitconf does this by using a dictionary with a special identifier
"#multiconf#"  and a list of dictionaries identified by a qualifier of the form

    "<qualifier name>:<qualifier value>[;<qualifier name>:<qualifier value>]..."

For example, the following setting

    "user_home": "/home"

would result in `get("user_home")` returning the value "/home" but it could also
be replaced with

    "user_home":  {
                    "#multiconf#": [
                        {"os:windows": "C:\\Users"},
                        {"os:linux;host:his_pc": "/home"},
                        {"os:linux;host:her_pc": "/home/her/special"}
                    ]
    }

Now the same configuration file will provide different values depending on the
machine it's on. On an MS Windows machine the value returned by `get` will be
"C:\\Users", and on a Linux machine with the host name 'his_pc' the value will be
"/home".
"""

__version__ = "1.0"

__CURRENT_HOSTNAME = socket.gethostname().lower()
__CURRENT_PLATFORM = sublime.platform()

QUALIFIERS = r"""([A-Za-z\d_]*):([^;]*)(?:;|$)"""

def isstr(s):
    try:
        return isinstance(s, basestring)
    except NameError:
        return isinstance(s, str)

def get(settings_obj, key, default=None, callback=None):
    """
    Return a Sublime Text plugin setting value

    Parameters:
      settings_obj - a sublime.Settings object or a dictionary containing
                     settings
      key          - the name of the setting
      default      - the default value to return if the key value is not found.
      callback     - a callback function that, if provided, will be called with
                     the found and default values as parameters.

    """
    # Parameter validation
    if not isinstance(settings_obj, (dict, sublime.Settings)):
        raise AttributeError("Invalid settings object")
    if not isstr(key):
        raise AttributeError("Invalid callback function")
    if callback != None and not hasattr(callback, '__call__'):
        raise AttributeError("Invalid callback function")

    setting = settings_obj.get(key, default)
    final_val = None

    if isinstance(setting, dict) and "#multiconf#" in setting:
        reject_item = False
        for entry in setting["#multiconf#"]:
            reject_item = False if isinstance(entry, dict) and len(entry) else True

            k, v = entry.popitem()

            if reject_item:
                continue

            for qual in re.compile(QUALIFIERS).finditer(k):
                if Qualifications.exists(qual.group(1)):
                    reject_item = not Qualifications.eval_qual(qual.group(1), qual.group(2))
                else:
                    reject_item = True
                if reject_item:
                    break

            if not reject_item:
                final_val = v
                break

        if reject_item:
            final_val = default
    else:
        final_val = setting

    return callback(final_val, default) if callback else final_val


class QualException(Exception):
    pass


class Qualifications(object):
    __qualifiers = {}

    @classmethod
    def add_qual(cls, key, callback):
        if isstr(key) and re.match(r"^[a-zA-Z][a-zA-Z\d_]*$", key) == None:
            raise QualException("'%s' is not a valid function name." % key)
        if not hasattr(callback, '__call__'):
            raise QualException("Bad function callback.")
        if key in cls.__qualifiers:
            raise QualException("'%s' qualifier already exists." % key)

        cls.__qualifiers[key] = callback

    @classmethod
    def exists(cls, key):
        return (key in cls.__qualifiers)

    @classmethod
    def eval_qual(cls, key, value):
        try:
            return cls.__qualifiers[key](value)
        except:
            raise QualException("Failed to execute %s qualifier" % key)


def __host_match(h):
    return (h.lower() == __CURRENT_HOSTNAME)


def __os_match(os):
    return (os == __CURRENT_PLATFORM)


Qualifications.add_qual("host", __host_match)
Qualifications.add_qual("os", __os_match)
