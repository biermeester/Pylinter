# -*- coding: utf-8 -*-

""" PyLinter Sublime Text Plugin

    This is a Pylint plugin for Sublime Text.

    Copyright R. de Laat, Elit 2011-2013

    For more information, go to https://github.com/biermeester/Pylinter#readme
"""

import os.path
import re
import threading
import subprocess
import collections
import sublime
import sublime_plugin

import multiconf

# To override this, set the 'verbose' setting in the configuration file
PYLINTER_VERBOSE = False

# the tag associated with view.set_status messages
PYLINTER_STATUS_TAG = "Pylinter"

def speak(*msg):
    """ Log messages to the console if VERBOSE is True """
    if PYLINTER_VERBOSE:
        print " - PyLinter: ", " ".join(msg)

# Regular expression to disect Pylint error messages
P_PYLINT_ERROR = re.compile(r"""
    ^(?P<file>.+?):(?P<line>[0-9]+):\ # file name and line number
    \[(?P<type>[a-z])(?P<errno>\d+)   # message type and error number
                                      # e.g. E0101
    (,\ (?P<hint>.+))?\]\             # optional class or function name
    (?P<msg>.*)                       # finally, the error message
    """, re.IGNORECASE | re.VERBOSE)

# Prevent the console from popping up
if os.name == "nt":
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
else:
    STARTUPINFO = None

# Try and automatically resolve Pylint's path
PYLINT_PATH = None
try:
    cmd = ["python",
           "-c",
           "import pylint; print pylint.__path__[0]"]
    proc = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            startupinfo=STARTUPINFO)
    out, err = proc.communicate()

    if out != "":
        PYLINT_PATH = os.path.join(out.strip(),  # pylint: disable=E1103
                                   "lint.py")
except ImportError:
    pass


# Pylint error cache
PYLINTER_ERRORS = {}

PATH_SEPERATOR = ';' if os.name == "nt" else ':'
SEPERATOR_PATTERN = ';' if os.name == "nt" else '[:;]'


class PylSet(object):
    """ Pylinter Settings class"""
    settings = sublime.load_settings('Pylinter.sublime-settings')

    @classmethod
    def _get_settings_obj(cls):
        try:
            view_settings = sublime.active_window().active_view().settings()
            view_settings = view_settings.get('pylinter')
            if view_settings:
                return view_settings
        except AttributeError:
            pass
        return cls.settings

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
                settings_obj = cls.settings
        return multiconf.get(settings_obj, setting_name, default)


class PylSetException(Exception):
    pass


class PylinterCommand(sublime_plugin.TextCommand):

    def run(self, edit, **kwargs):

        settings = self._read_settings()

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
            self.add_ignore()
        else:
            speak("Running Pylinter on %s" % self.view.file_name())

            if self.view.file_name().endswith('.py'):
                # erase status message if sitting on an error line
                self.view.erase_status(PYLINTER_STATUS_TAG)
                thread = PylintThread(self.view, *settings)
                thread.start()
                self.progress_tracker(thread)

    def dump_errors(self):
        import pprint
        pprint.pprint(PYLINTER_ERRORS)

    def _read_settings(self):
        global PYLINTER_VERBOSE

        PYLINTER_VERBOSE = PylSet.get_or('verbose', False)
        speak("Verbose is", str(PYLINTER_VERBOSE))
        python_bin = PylSet.get_or('python_bin', 'python')
        python_path = PylSet.get_or('python_path', [])
        python_path = PATH_SEPERATOR.join([str(p) for p in python_path])
        working_dir = PylSet.get_or('working_dir', None)
        pylint_path = PylSet.get_or('pylint_path', None) or PYLINT_PATH
        pylint_rc = PylSet.get_or('pylint_rc', None) or ""
        ignore = [t.lower() for t in PylSet.get_or('ignore', [])]
        disable_msgs = ",".join(PylSet.get_or('disable', []))

        if not pylint_path:
            msg = "Please define the full path to 'lint.py' in the settings."
            sublime.error_message(msg)
            return False
        elif not os.path.exists(pylint_path):
            msg = "Pylint not found at '%s'." % pylint_path
            sublime.error_message(msg)
            return False

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
                disable_msgs)

    @classmethod
    def show_errors(cls, view):
        # Icons to be used in the margin
        if PylSet.get_or('use_icons', False):
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

        # set status message if command finished on an error line
        if PylSet.get_or("message_stay", False):
            view_id = view.id()
            lineno = view.rowcol(view.sel()[0].end())[0]
            if lineno in PYLINTER_ERRORS[view_id]:
                err_str = PYLINTER_ERRORS[view_id][lineno]
                view.set_status(PYLINTER_STATUS_TAG, err_str)


    def popup_error_list(self):
        view_id = self.view.id()

        if not view_id in PYLINTER_ERRORS:
            return

        # No errors were found
        if len(PYLINTER_ERRORS[view_id]) == 1:
            sublime.message_dialog("No Pylint errors found")
            return

        errors = [(key + 1, unicode(value, errors='ignore'))
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

    def add_ignore(self):
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

            edit = self.view.begin_edit()
            self.view.replace(edit, line_region, line_txt)
            self.view.end_edit(edit)

    def is_enabled(self):
        file_name = self.view.file_name()
        if file_name:
            return file_name.endswith('.py')


class PylintThread(threading.Thread):
    """ This class creates a seperate thread to run Pylint in """
    def __init__(self, view, pbin, ppath, cwd, lpath, lrc, ignore,
                 disable_msgs):
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

        threading.Thread.__init__(self)

    def run(self):

        command = [self.python_bin,
                   self.pylint_path,
                   '--output-format=parseable',
                   '--include-ids=y',
                   self.file_name]

        if self.pylint_rc:
            command.insert(-2, '--rcfile=%s' % self.pylint_rc)

        if self.disable_msgs:
            command.insert(-2, '--disable=%s' % self.disable_msgs)

        original = os.environ.get('PYTHONPATH', '')

        speak("Current PYTHONPATH is '%s'" % original)

        org_path_lst = [p for p in re.split(SEPERATOR_PATTERN, original) if p]
        pyl_path_lst = [p for p in re.split(SEPERATOR_PATTERN,
                                            self.python_path) if p]

        pythonpaths = set(org_path_lst + pyl_path_lst)

        os.environ['PYTHONPATH'] = PATH_SEPERATOR.join(pythonpaths)
        speak("Updated PYTHONPATH is '%s'" % os.environ['PYTHONPATH'])

        speak("Running command:\n    ", " ".join(command))
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             startupinfo=STARTUPINFO,
                             cwd=self.working_dir)
        output, eoutput = p.communicate()

        lines = [line for line in output.split('\n')]  # pylint: disable=E1103
        elines = [line for line in eoutput.split('\n')]  # pylint:disable=E1103
        # Call set_timeout to have the error processing done
        # from the main thread
        sublime.set_timeout(lambda: self.process_errors(lines, elines), 100)

    def process_errors(self, lines, errlines):
        view_id = self.view.id()
        global PYLINTER_ERRORS
        PYLINTER_ERRORS[view_id] = {"visible": True}

        # if pylint raised any exceptions, propogate those to the user, for
        # instance, trying to disable a messaage id that does not exist
        if len(errlines) > 2 and "raise" in errlines[-3]:
            sublime.error_message("Fatal pylint error:\n%s" % (errlines[-2]))

        for line in lines:
            mdic = re.match(P_PYLINT_ERROR, line)
            if mdic:
                m = mdic.groupdict()
                line_num = int(m['line']) - 1
                if m['type'].lower() not in self.ignore:
                    PYLINTER_ERRORS[view_id][line_num] =\
                        "%s%s: %s " % (m['type'], m['errno'],
                        m['msg'].strip())
                    speak(PYLINTER_ERRORS[view_id][line_num])

        PylinterCommand.show_errors(self.view)


class BackgroundPylinter(sublime_plugin.EventListener):
    def __init__(self):
        sublime_plugin.EventListener.__init__(self)
        self.last_selected_line = -1
        self.message_stay = PylSet.get_or("message_stay", False)

    def _last_selected_lineno(self, view):
        return view.rowcol(view.sel()[0].end())[0]

    def on_post_save(self, view):
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
                        view.set_status(PYLINTER_STATUS_TAG, err_str)
                    else:
                        sublime.status_message(err_str)
                # if no longer on an error line, but there is a status, erase it
                elif view.get_status(PYLINTER_STATUS_TAG):
                    view.erase_status(PYLINTER_STATUS_TAG)
