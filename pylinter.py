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

#pylint: disable=E1101

# Constant to differentiate between ST2 and ST3
ST3 = int(sublime.version()) > 3000

if ST3:
    from . import multiconf
else:
    import multiconf

# The version of Python that SublimeText is using
PYTHON_VERSION = sys.version_info[0]

# To override this, set the 'verbose' setting in the configuration file
PYLINTER_VERBOSE = True

# Prevent the console from popping up in Windows
if os.name == "nt":
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
else:
    STARTUPINFO = None

# The output format we want PyLint's error messages to be in
PYLINT_FORMAT = '--msg-template={path}:{line}:{msg_id}:{msg}'
# Pylint error cache
PYLINTER_ERRORS = {}
PATH_SEPERATOR = ';' if os.name == "nt" else ':'
SEPERATOR_PATTERN = ';' if os.name == "nt" else '[:;]'

# The last line selected (i.e. the one we need to display status info for)
LAST_SELECTED_LINE = -1
# Indicates if we're displaying info in the status line
STATUS_ACTIVE = False

# The followig global values will be set by the `set_globals` function
PYLINT_VERSION = None
PYLINT_SETTINGS = None
# Regular expression to disect Pylint error messages
P_PYLINT_ERROR = None

# The default Pylint command will be stored in this variable. It will either be
# ["pylint"] or [<python_bin>, <path_to_lint.py>] if the former is not found.
DEFAULT_PYLINT_COMMAND = None

def speak(*msg):
    """ Log messages to the console if PYLINTER_VERBOSE is True """
    if PYLINTER_VERBOSE:
        print(" - PyLinter: " + " ".join(msg))

def plugin_loaded():
    """ Set all global values """

    global PYLINT_VERSION, PYLINT_SETTINGS, P_PYLINT_ERROR, DEFAULT_PYLINT_COMMAND

    PYLINT_SETTINGS = sublime.load_settings('Pylinter.sublime-settings')
    DEFAULT_PYLINT_COMMAND = PylSet.get_default_pylint_command()
    PYLINT_VERSION = PylSet.get_lint_version()

    # Pylint version < 1.0
    if PYLINT_VERSION[0] == 0:
        # Regular expression to disect Pylint error messages
        P_PYLINT_ERROR = re.compile(r"""
            ^(?P<file>.+?):(?P<line>[0-9]+):\ # file name and line number
            \[(?P<type>[a-z])(?P<errno>\d+)   # message type and error number
                                              # e.g. E0101
            (,\ (?P<hint>.+))?\]\             # optional class or function name
            (?P<msg>.*)                       # finally, the error message
            """, re.IGNORECASE | re.VERBOSE)
    # Pylint version 1.0 or greater
    else:
        P_PYLINT_ERROR = re.compile(r"""
            ^(?P<file>.+?):(?P<line>[0-9]+): # file name and line number
            (?P<type>[a-z])(?P<errno>\d+):   # message type and error number,
                                             # e.g. E0101
            (?P<msg>.*)                      # finally, the error message
            """, re.IGNORECASE | re.VERBOSE)

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
        pylint_path = cls.get_or('pylint_path', None)
        pylint_rc = cls.get_or('pylint_rc', None) or ""
        ignore = [t.lower() for t in cls.get_or('ignore', [])]
        plugins = cls.get_or('plugins', None)

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
                pylint_extra,
                plugins)

    @classmethod
    def get_default_pylint_command(cls):
        """ This class method will check if the `pylint` command is available.

        If it is not, it will try and determine the path to the `lint.py` file
        directly.
        """

        try:
            _ = subprocess.Popen("pylint",
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             startupinfo=STARTUPINFO)
            speak("Pylint executable found")
            return ["pylint"]
        except OSError:
            speak("Pylint executable *not* found")
            speak("Seaching for lint.py module...")

        cmd = ["python", "-c"]

        if PYTHON_VERSION == 2:
            cmd.append("import pylint; print pylint.__path__[0]")
        else:
            cmd.append("import pylint; print(pylint.__path__[0])")

        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                startupinfo=STARTUPINFO)

        out, _ = proc.communicate()

        if out != b"":
            pylint_path = os.path.join(out.strip(),
                                       b"lint.py").decode("utf-8")

        if not pylint_path:
            msg = ("Pylinter could not automatically determined the path to `lint.py`.\n\n"
                   "Please provide one in the settings file using the `pylint_path` variable.\n\n"
                   "NOTE:\nIf you are using a Virtualenv, the problem might be resolved by "
                   "launching Sublime Text from correct Virtualenv.")
            sublime.error_message(msg)
        elif not os.path.exists(pylint_path):
            msg = ("Pylinter could not find `lint.py` at the given path:\n\n'{}'.".format(pylint_path))
            sublime.error_message(msg)
        else:
            speak("Pylint path {0} found".format(pylint_path))
            python_bin = cls.get_or('python_bin', 'python')
            return [python_bin, pylint_path]

    @classmethod
    def get_lint_version(cls):
        """ Return the Pylint version as a (x, y, z) tuple """
        pylint_path = cls.get_or('pylint_path', None)
        python_bin = cls.get_or('python_bin', 'python')
        found = None

        regex = re.compile(b"[lint.py|pylint] ([0-9]+).([0-9]+).([0-9]+)")

        if pylint_path:
            command = [python_bin, pylint_path]
        else:
            command = list(DEFAULT_PYLINT_COMMAND)

        command.append("--version")

        try:
            p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             startupinfo=STARTUPINFO)
            output, _ = p.communicate()
            found = regex.search(output)
        except OSError:
            msg = "Pylinter could not find '%s'" % command[-2]
            sublime.error_message(msg)

        if found:
            found = found.groups()
            if len(found) == 3:
                version = tuple(int(v) for v in found)
                speak("Pylint version %s found" % str(version))
                return version

        speak("Could not determine Pylint version")
        return (1, 0, 0)


class PylSetException(Exception):
    pass


class PylinterCommand(sublime_plugin.TextCommand):

    def run(self, edit, **kwargs):
        """ Run a Pylinter command """
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
        """ Print the found pylint errors """
        import pprint
        pprint.pprint(PYLINTER_ERRORS)

    @classmethod
    def show_errors(cls, view):
        """ Display the errors for the given view """
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
        """ Display a popup list of the errors found """
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
            """ Jump to the line of the item that was selected from the list """
            if selected_item == -1:
                return
            self.view.run_command("goto_line",
                                  {"line": line_nums[selected_item]})

        self.view.window().show_quick_panel(list(panel_items), on_done)

    def progress_tracker(self, thread, i=0):
        """ Display spinner while Pylint is running """
        icons = [u"◐", u"◓", u"◑", u"◒"]
        sublime.status_message("PyLinting %s" % icons[i])
        if thread.is_alive():
            i = (i + 1) % 4
            sublime.set_timeout(lambda: self.progress_tracker(thread, i), 100)
        else:
            sublime.status_message("")

    def toggle_regions(self):
        """ Show/hide the errors found """
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
        """ Make pylint ignore the line that the carret is on """
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
        """ This plugin is only enabled for Python modules """
        file_name = self.view.file_name()
        if file_name:
            return file_name.endswith('.py')
        return False


class PylintThread(threading.Thread):
    """ This class creates a seperate thread to run Pylint in """

    def __init__(self, view, pbin, ppath, cwd, lpath, lrc, ignore,
                 disable_msgs, extra_pylint_args, plugins):
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
        self.plugins = plugins

        threading.Thread.__init__(self)

    def run(self):
        """ Run the pylint command """
        if self.pylint_path:
            command = [self.python_bin, self.pylint_path]
        else:
            command = list(DEFAULT_PYLINT_COMMAND)

        if PYLINT_VERSION[0] == 0:
            options = ['--output-format=parseable',
                       '--include-ids=y']
        else:
            options = ['--reports=n',
                       PYLINT_FORMAT]

            if self.plugins:
                options.extend(["--load-plugins",
                                ",".join(self.plugins)])

        if self.pylint_rc:
            options.append('--rcfile=%s' % self.pylint_rc)

        if self.disable_msgs:
            options.append('--disable=%s' % self.disable_msgs)

        options.append(self.file_name)
        command.extend(options)

        self.set_path()

        speak("Running command with Pylint", str(PYLINT_VERSION))
        speak(" ".join(command))

        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             startupinfo=STARTUPINFO,
                             cwd=self.working_dir)
        output, eoutput = p.communicate()

        if PYTHON_VERSION == 2:
            lines = [line for line in output.split('\n')]  # pylint: disable=E1103
            elines = [line for line in eoutput.split('\n')]  # pylint:disable=E1103
        else:
            lines = [line for line in output.decode().split('\n')]  # pylint: disable=E1103
            elines = [line for line in eoutput.decode().split('\n')]  # pylint:disable=E1103

        # Call set_timeout to have the error processing done
        # from the main thread
        sublime.set_timeout(lambda: self.process_errors(lines, elines), 100)

    def set_path(self):
        """ Adjust the PYTHONPATH variable for this thread """
        original = os.environ.get('PYTHONPATH', '')

        speak("Current PYTHONPATH is '%s'" % original)

        org_path_lst = [p for p in re.split(SEPERATOR_PATTERN, original) if p]
        pyl_path_lst = [p for p in re.split(SEPERATOR_PATTERN,
                                            self.python_path) if p]

        pythonpaths = set(org_path_lst + pyl_path_lst)
        os.environ['PYTHONPATH'] = PATH_SEPERATOR.join(pythonpaths)

        speak("Updated PYTHONPATH is '{0}'".format(os.environ['PYTHONPATH']))


    def process_errors(self, lines, errlines):
        """ Process the error found """
        view_id = self.view.id()
        PYLINTER_ERRORS[view_id] = {"visible": True}

        # if pylint raised any exceptions, propogate those to the user, for
        # instance, trying to disable a messaage id that does not exist
        if len(errlines) > 1:
            err = errlines[-2]
            if not err.startswith("No config file found"):
                sublime.error_message("Fatal pylint error:\n%s" % (errlines[-2]))

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
    """ Process Sublime Text events """
    def _last_selected_lineno(self, view):
        return view.rowcol(view.sel()[0].end())[0]

    def on_post_save(self, view):
        """ Run Pylint on file save """
        if (view.file_name().endswith('.py') and
            PylSet.get_or('run_on_save', False)):
            view.run_command('pylinter')

    def on_selection_modified(self, view):
        """ Show errors in the status line when the carret/selection moves """
        global LAST_SELECTED_LINE, STATUS_ACTIVE
        view_id = view.id()
        if view_id in PYLINTER_ERRORS:
            new_selected_line = self._last_selected_lineno(view)
            if new_selected_line != LAST_SELECTED_LINE:
                LAST_SELECTED_LINE = new_selected_line
                if LAST_SELECTED_LINE in PYLINTER_ERRORS[view_id]:
                    err_str = PYLINTER_ERRORS[view_id][LAST_SELECTED_LINE]
                    if PylSet.get_or("message_stay", False):
                        view.set_status('Pylinter', err_str)
                        STATUS_ACTIVE = True
                    else:
                        sublime.status_message(err_str)
                elif STATUS_ACTIVE:
                    view.erase_status('Pylinter')
                    STATUS_ACTIVE = False

# In SublimeText 2, we need to call this manually.
if not ST3:
    plugin_loaded()
