# -*- coding: utf-8 -*-

""" PyLinter Sublime Text Plugin

    This is a Pylint plugin for Sublime Text.

    Copyright R. de Laat, Elit 2011-2013

    For more information, go to https://github.com/biermeester/Pylinter#readme
"""

import os.path
import sys
import re
import threading
import subprocess
import collections
import sublime
import sublime_plugin

ST3 = int(sublime.version()) > 3000

if ST3:
    from . import multiconf
else:
    import multiconf

PY_VERSION = sys.version_info[0]

#pylint: disable=E1101

# To override this, set the 'verbose' setting in the configuration file
PYLINTER_VERBOSE = False

# Flag to check whether settings are loaded.
LOADED = False

def speak(*msg):
    """ Log messages to the console if VERBOSE is True """
    if PYLINTER_VERBOSE:
        print(" - PyLinter: " + " ".join(msg))

# Prevent the console from popping up
if os.name == "nt":
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
else:
    STARTUPINFO = None

# Define placeholder globals for the globals that require the settings file
PYLINT_SETTINGS = None
P_PYLINT_ERROR = None
PYLINT_VERSION = None

class PylSet(object):
    """ Pylinter Settings class"""
    @classmethod
    def _get_settings_obj(cls):
        try:
            view_settings = sublime.active_window().active_view().settings()
            view_settings = view_settings.get('pylinter')
            if view_settings:
                return view_settings
        except AttributeError:
            pass

        return PYLINT_SETTINGS

    @classmethod
    def get(cls, setting_name):
        value = cls.get_or(setting_name, None)
        if value is None:
            raise PylSetException("No value found for '%s'" % setting_name)
        return value

    @classmethod
    def get_or(cls, setting_name, default):
        settings_obj = cls._get_settings_obj()
        if isinstance(settings_obj, collections.Iterable):
            if not setting_name in settings_obj:
                settings_obj = PYLINT_SETTINGS
        return multiconf.get(settings_obj, setting_name, default)

    @classmethod
    def read_settings(cls):
        global PYLINTER_VERBOSE

        PYLINTER_VERBOSE = cls.get_or('verbose', False)
        speak("Verbose is", str(PYLINTER_VERBOSE))
        python_bin = cls.get_or('python_bin', 'python')
        python_path = cls.get_or('python_path', [])
        python_path = PATH_SEPERATOR.join([str(p) for p in python_path])
        working_dir = cls.get_or('working_dir', None)
        pylint_path = cls.get_lint_path(py_bin=python_bin)
        pylint_rc = cls.get_or('pylint_rc', None) or ""
        ignore = [t.lower() for t in cls.get_or('ignore', [])]

        # Add custom runtime settings
        pylint_extra = PylSet.get_or('pylint_extra', None)

        disable = cls.get_or('disable', [])
        # Added ignore for trailing whitespace (false positives bug in
        # pylint 1.0.0)
        if PYLINT_VERSION[0] != 0:
            disable.append('C0303')
        disable_msgs = ",".join(disable)

        if pylint_rc and not os.path.exists(pylint_rc):
            msg = "Pylint configuration not found at '%s'." % pylint_rc
            sublime.error_message(msg)
            return False

        return (python_bin,
                python_path,
                working_dir,
                pylint_path,
                pylint_rc,
                ignore,
                disable_msgs,
                pylint_extra)

    @classmethod
    def get_lint_path(cls, py_bin = "python"):
        pylint_path = PylSet.get_or('pylint_path', None)

        if not pylint_path:
            cmd = [py_bin,
                   "-c"]
            if PY_VERSION == 2:
                cmd.append("import pylint; print pylint.__path__[0]")
            else:
                cmd.append("import pylint; print(pylint.__path__[0])")
            proc = subprocess.Popen(cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    startupinfo=STARTUPINFO)
            out, _ = proc.communicate()

            if out != "":
                pylint_path = os.path.join(out.strip(),
                                           b"lint.py").decode("utf-8")

        if not pylint_path:
            msg = "Please define the full path to 'lint.py' in the settings."
            sublime.error_message(msg)
        elif not os.path.exists(pylint_path):
            msg = "Pylint not found at '{0}'.".format(pylint_path)
            sublime.error_message(msg)
        else:
            speak("Pylint path {0} found".format(pylint_path))
            return pylint_path

    @classmethod
    def get_lint_version(cls):
        import imp
        pp = os.path.join(
                os.path.dirname(PylSet.get_lint_path()),
                '__pkginfo__.py')
        lintpackage = imp.load_source('lint', pp)
        speak("Pylint version {0} found".format(lintpackage.numversion))
        return lintpackage.numversion

class PylSetException(Exception):
    pass



# The output format we want PyLint's error messages to be in
PYLINT_FORMAT = '--msg-template={path}:{line}:{msg_id}:{msg}'

# Pylint error cache
PYLINTER_ERRORS = {}

PATH_SEPERATOR = ';' if os.name == "nt" else ':'
SEPERATOR_PATTERN = ';' if os.name == "nt" else '[:;]'

def setPylinterGlobals():
    global P_PYLINT_ERROR
    global PYLINT_VERSION
    if LOADED:
        PYLINT_VERSION = PylSet.get_lint_version()
        # Regular expression to disect Pylint error messages
        if PYLINT_VERSION[0] == 0:
            # Regular expression to disect Pylint error messages
            P_PYLINT_ERROR = re.compile(r"""
                ^(?P<file>.+?):(?P<line>[0-9]+):\ # file name and line number
                \[(?P<type>[a-z])(?P<errno>\d+)   # message type and error number
                                                  # e.g. E0101
                (,\ (?P<hint>.+))?\]\             # optional class or function name
                (?P<msg>.*)                       # finally, the error message
                """, re.IGNORECASE | re.VERBOSE)
        else:
            P_PYLINT_ERROR = re.compile(r"""
                ^(?P<file>.+?):(?P<line>[0-9]+): # file name and line number
                (?P<type>[a-z])(?P<errno>\d+):   # message type and error number,
                                                 # e.g. E0101
                (?P<msg>.*)                      # finally, the error message
                """, re.IGNORECASE | re.VERBOSE)
    else:
        PYLINT_VERSION = None


class PylinterCommand(sublime_plugin.TextCommand):

    def run(self, edit, **kwargs):
        global PYLINT_VERSION
        global LOADED
        if LOADED:
            setPylinterGlobals()

        settings = PylSet.read_settings()

        if not settings:
            return

        action = kwargs.get('action', None)

        if action == 'toggle':
            self.toggle_regions()
        elif action == 'list':
            self.popup_error_list()
        elif action == 'dump':
            self.dump_errors()
        elif action == 'ignore':
            if not ST3:
                edit = self.view.begin_edit()
            self.add_ignore(edit)
        else:
            speak("Running Pylinter on %s" % self.view.file_name())

            if self.view.file_name().endswith('.py'):
                thread = PylintThread(self.view, *settings)
                thread.start()
                self.progress_tracker(thread)

    def dump_errors(self):
        import pprint
        pprint.pprint(PYLINTER_ERRORS)

    @classmethod
    def show_errors(cls, view):
        # Icons to be used in the margin
        if PylSet.get_or('use_icons', False):
            if ST3:
                icons = {"C": "Packages/Pylinter/icons/convention.png",
                         "E": "Packages/Pylinter/icons/error.png",
                         "F": "Packages/Pylinter/icons/fatal.png",
                         "I": "Packages/Pylinter/icons/convention.png",
                         "R": "Packages/Pylinter/icons/refactor.png",
                         "W": "Packages/Pylinter/icons/warning.png"}
            else:
                icons = {"C": "../Pylinter/icons/convention",
                         "E": "../Pylinter/icons/error",
                         "F": "../Pylinter/icons/fatal",
                         "I": "../Pylinter/icons/convention",
                         "R": "../Pylinter/icons/refactor",
                         "W": "../Pylinter/icons/warning"}
        else:
            icons = {"C": "dot",
                     "E": "dot",
                     "F": "dot",
                     "I": "dot",
                     "R": "dot",
                     "W": "dot"}

        if PylSet.get_or('disable_outline', False):
            region_flag = sublime.HIDDEN
        else:
            region_flag = sublime.DRAW_OUTLINED

        outlines = {"C": [], "E": [], "F": [], "I": [], "R": [], "W": []}

        for line_num, error in PYLINTER_ERRORS[view.id()].items():
            if not isinstance(line_num, int):
                continue
            line = view.line(view.text_point(line_num, 0))
            outlines[error[0]].append(line)

        for key, regions in outlines.items():
            view.add_regions('pylinter.' + key, regions,
                             'pylinter.' + key, icons[key],
                             region_flag)

    def popup_error_list(self):
        view_id = self.view.id()

        if not view_id in PYLINTER_ERRORS:
            return

        # No errors were found
        if len(PYLINTER_ERRORS[view_id]) == 1:
            sublime.message_dialog("No Pylint errors found")
            return

        errors = [(key + 1, value)
                  for key, value in PYLINTER_ERRORS[view_id].items()
                  if key != 'visible']
        line_nums, panel_items = zip(*sorted(errors,
                                             key=lambda error: error[1]))

        def on_done(selected_item):
            if selected_item == -1:
                return
            self.view.run_command("goto_line",
                                  {"line": line_nums[selected_item]})

        self.view.window().show_quick_panel(list(panel_items), on_done)

    def progress_tracker(self, thread, i=0):
        icons = [u"◐", u"◓", u"◑", u"◒"]
        sublime.status_message("PyLinting %s" % icons[i])
        if thread.is_alive():
            i = (i + 1) % 4
            sublime.set_timeout(lambda: self.progress_tracker(thread, i), 100)
        else:
            sublime.status_message("")

    def toggle_regions(self):
        view_id = self.view.id()
        try:
            if PYLINTER_ERRORS[view_id]['visible']:
                speak("Hiding errors")
                for category in ["C", "E", "F", "I", "R", "W"]:
                    self.view.erase_regions('pylinter.' + category)
            else:
                speak("Showing errors")
                self.show_errors(self.view)
            PYLINTER_ERRORS[view_id]['visible'] ^= True
        except KeyError:
            pass

    def add_ignore(self, edit):
        global PYLINTER_ERRORS

        view_id = self.view.id()
        point = self.view.sel()[0].end()
        position = self.view.rowcol(point)
        current_line = position[0]

        pylint_statement = "".join(("#", "pyl", "int: ", "disable="))

        # If an error is registered for that line
        if current_line in PYLINTER_ERRORS[view_id]:
            #print position
            line_region = self.view.line(point)
            line_txt = self.view.substr(line_region)

            err_code = PYLINTER_ERRORS[view_id][current_line]
            err_code = err_code[:err_code.find(':')]

            if pylint_statement not in line_txt:
                line_txt += " " + pylint_statement + err_code
            else:
                line_txt += "," + err_code

            self.view.replace(edit, line_region, line_txt)
            self.view.end_edit(edit)

    def is_enabled(self):
        file_name = self.view.file_name()
        if file_name:
            return file_name.endswith('.py')
        return False


class PylintThread(threading.Thread):
    """ This class creates a seperate thread to run Pylint in """
    def __init__(self, view, pbin, ppath, cwd, lpath, lrc, ignore,
                 disable_msgs, extra_pylint_args):
        self.view = view
        # Grab the file name here, since view cannot be accessed
        # from anywhere but the main application thread
        self.file_name = view.file_name()
        self.python_bin = pbin
        self.python_path = ppath
        self.working_dir = cwd
        self.pylint_path = lpath
        self.pylint_rc = lrc
        self.ignore = ignore
        self.disable_msgs = disable_msgs
        self.extra_pylint_args = extra_pylint_args

        threading.Thread.__init__(self)

    def run(self):
        if PYLINT_VERSION[0] == 0:
            command = [self.python_bin,
                       self.pylint_path,
                       '--output-format=parseable',
                       '--include-ids=y',
                       self.file_name]
        else:
            command = [self.python_bin,
                       self.pylint_path,
                       '--reports=n',
                       PYLINT_FORMAT,
                       self.file_name]

        if self.pylint_rc:
            command.insert(-2, '--rcfile=%s' % self.pylint_rc)

        if self.disable_msgs:
            command.insert(-2, '--disable=%s' % self.disable_msgs)

        self.set_path()

        speak("Running command")
        speak(" ".join(command))

        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             startupinfo=STARTUPINFO,
                             cwd=self.working_dir)
        output, eoutput = p.communicate()

        lines = [line for line in output.decode().split('\n')]  # pylint: disable=E1103
        elines = [line for line in eoutput.decode().split('\n')]  # pylint:disable=E1103
        # Call set_timeout to have the error processing done
        # from the main thread
        sublime.set_timeout(lambda: self.process_errors(lines, elines), 100)

    def set_path(self):
        original = os.environ.get('PYTHONPATH', '')

        speak("Current PYTHONPATH is '%s'" % original)

        org_path_lst = [p for p in re.split(SEPERATOR_PATTERN, original) if p]
        pyl_path_lst = [p for p in re.split(SEPERATOR_PATTERN,
                                            self.python_path) if p]

        pythonpaths = set(org_path_lst + pyl_path_lst)
        os.environ['PYTHONPATH'] = PATH_SEPERATOR.join(pythonpaths)

        speak("Updated PYTHONPATH is '{0}'".format(os.environ['PYTHONPATH']))


    def process_errors(self, lines, errlines):
        view_id = self.view.id()
        global PYLINTER_ERRORS
        PYLINTER_ERRORS[view_id] = {"visible": True}

        # if pylint raised any exceptions, propogate those to the user, for
        # instance, trying to disable a messaage id that does not exist
        if len(errlines) > 1:
            err = errlines[-2]
            if not err.startswith("No config file found"):
                sublime.error_message("Fatal pylint error:\n%s" % (errlines[-2]))
        # Guard against uninitialised globals
        if P_PYLINT_ERROR is None:
            setPylinterGlobals()

        for line in lines:
            mdic = re.match(P_PYLINT_ERROR, line)
            if mdic:
                m = mdic.groupdict()
                line_num = int(m['line']) - 1
                if m['type'].lower() not in self.ignore:
                    PYLINTER_ERRORS[view_id][line_num] = \
                        "%s%s: %s " % (m['type'], m['errno'],
                        m['msg'].strip())
                    speak(PYLINTER_ERRORS[view_id][line_num])

        if len(PYLINTER_ERRORS[view_id]) <= 1:
            speak("No errors found")

        PylinterCommand.show_errors(self.view)


class BackgroundPylinter(sublime_plugin.EventListener):
    def __init__(self):
        sublime_plugin.EventListener.__init__(self)
        self.last_selected_line = -1
        # self.message_stay = PylSet.get_or("message_stay", False)
        self.message_stay = None;
        self.status_active = False

    def _last_selected_lineno(self, view):
        return view.rowcol(view.sel()[0].end())[0]

    def on_post_save(self, view):
        # "Lazy" initialisation to guard against
        # unprepared global settings
        if self.message_stay is None:
            self.message_stay = PylSet.get_or("message_stay", False)
        if view.file_name().endswith('.py') and PylSet.get_or('run_on_save',
                                                              False):
            view.run_command('pylinter')

    def on_selection_modified(self, view):
        view_id = view.id()
        if view_id in PYLINTER_ERRORS:
            last_selected_line = self._last_selected_lineno(view)

            if last_selected_line != self.last_selected_line:
                self.last_selected_line = last_selected_line
                if self.last_selected_line in PYLINTER_ERRORS[view_id]:
                    err_str = PYLINTER_ERRORS[view_id][self.last_selected_line]
                    if self.message_stay:
                        view.set_status('Pylinter', err_str)
                        self.status_active = True
                    else:
                        sublime.status_message(err_str)
                elif self.status_active:
                    view.erase_status('Pylinter')
                    self.status_active = False

def plugin_loaded():
    """Load the settings file when the Sublime API is ready"""
    global LOADED
    global PYLINT_SETTINGS
    PYLINT_SETTINGS = sublime.load_settings('Pylinter.sublime-settings')
    if PYLINT_SETTINGS.get("pylint_path") is None:
        sublime.error_message("Cannot load Pylinter settings")
    else:
        LOADED = True
