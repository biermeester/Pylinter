# -*- coding: utf-8 -*-

""" PyLinter

    https://github.com/biermeester/Pylinter
"""

import os.path
import re
import threading
import subprocess
import sublime
import sublime_plugin


settings = sublime.load_settings('Pylinter.sublime-settings')
def get_setting(name, default):
    try:
        v = sublime.active_window().active_view().settings().get('pylinter', {}).get(name, None)
        if v != None:
            return v
    except AttributeError:
        pass
    return settings.get(name, default)


# Regular expression to disect Pylint error messages
P_PYLINT_ERROR = re.compile(r"""
                            ^(?P<file>.+?):(?P<line>[0-9]+):\ # file name and line number
                            \[(?P<type>[a-z])(?P<errno>\d+)   # message type and error number, e.g. E0101
                            (,\ (?P<hint>.+))?\]\             # optional class or function name
                            (?P<msg>.*)                       # finally, the error message
                            """, re.IGNORECASE|re.VERBOSE)

# To override this, set the 'verbose' setting in the configuration file
PYLINTER_VERBOSE = False
PYLINTER_ERRORS = {}

PATH_SEPERATOR = ';' if os.name == "nt" else ':'
SEPERATOR_PATTERN = ';' if os.name == "nt" else '[:;]'

def speak(*msg):
    """ Log messages to the console if VERBOSE is True """
    if PYLINTER_VERBOSE:
        print " - PyLinter: ", " ".join(msg)



def show_errors(view):
    # Icons to be used in the margin
    if get_setting('use_icons', False):
        ICONS = {"C": "../Pylinter/icons/convention",
                 "E": "../Pylinter/icons/error",
                 "F": "../Pylinter/icons/fatal",
                 "I": "../Pylinter/icons/convention",
                 "R": "../Pylinter/icons/refactor",
                 "W": "../Pylinter/icons/warning"}
    else:
        ICONS = {"C": "dot", "E": "dot", "F": "dot", "I":"dot", "R": "dot", "W": "dot"}

    outlines = []
    outlines2 = {"C": [], "E":[], "F": [], "I":[], "R":[], "W":[]}
    for line_num, error in PYLINTER_ERRORS[view.id()].items():
        if not isinstance(line_num, int):
            continue
        line = view.line(view.text_point(line_num, 0))
        outlines2[error[0]].append(line)
        outlines.append(view.line(view.text_point(line_num, 0)))
    for key, regions in outlines2.items():
        view.add_regions('pylinter.' + key, regions, 'pylinter.' + key, ICONS[key], sublime.DRAW_OUTLINED)

class PylinterCommand(sublime_plugin.TextCommand):

    def run(self, edit, **kwargs):

        self._read_settings()

        action = kwargs.get('action', None)
        if action == 'toggle':
            self.toggle_regions()
        elif action == 'list':
            popup_error_list(self.view)
        elif action == 'dump':
            self.dump_errors()
        elif action == 'ignore':
            self.add_ignore()
        else:
            speak("Running Pylinter on %s" % self.view.file_name())

            if self.view.file_name().endswith('.py'):
                thread = PylintThread(self.view,
                                      self.python_bin,
                                      self.python_path,
                                      self.working_dir,
                                      self.pylint_path,
                                      self.pylint_rc,
                                      self.ignore)
                thread.start()
                self.progress_tracker(thread)

    def dump_errors(self):
        import pprint
        pprint.pprint(PYLINTER_ERRORS)

    def _read_settings(self):
        global PYLINTER_VERBOSE

        PYLINTER_VERBOSE = get_setting('verbose', False)
        self.python_bin = get_setting('python_bin', 'python') #pylint: disable=W0201
        self.python_path = PATH_SEPERATOR.join([str(p) for p in get_setting('python_path', [])])  #pylint: disable=W0201
        self.working_dir = get_setting('working_dir', None) or None #pylint: disable=W0201
        self.pylint_path = get_setting('pylint_path', None) #pylint: disable=W0201
        self.pylint_rc = get_setting('pylint_rc', None) or "" #pylint: disable=W0201
        self.ignore = [t.lower() for t in get_setting('ignore', [])] #pylint: disable=W0201

        if not self.pylint_path:
            sublime.error_message("Please define the full path to 'lint.py' in the settings.")
        elif not os.path.exists(self.pylint_path):
            sublime.error_message("Pylint not found at '%s'." % self.pylint_path)

        if self.pylint_rc and not os.path.exists(self.pylint_rc):
            sublime.error_message("Pylint configuration not found at '%s'." % self.pylint_rc)

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
                self.view.erase_regions('pylinter')
            else:
                show_errors(self.view)
            PYLINTER_ERRORS[view_id]['visible'] ^= True
        except KeyError:
            pass

    def add_ignore(self):
        global PYLINTER_ERRORS
        view_id = self.view.id()
        point = self.view.sel()[0].end()
        position = self.view.rowcol(point)
        current_line = position[0]

        pylint_statement = "#pylint: disable=" #pylint: disable=E0012

        # If an error is registered for that line
        if PYLINTER_ERRORS[view_id].has_key(current_line):
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
    def __init__(self, view, python_bin, python_path, working_dir, pylint_path, pylint_rc, ignore):
        self.view = view
        # Grab the file name here, since view cannot be accessed
        # from anywhere but the main application thread
        self.file_name = view.file_name()
        self.python_bin = python_bin
        self.python_path = python_path
        self.working_dir = working_dir
        self.pylint_path = pylint_path
        self.pylint_rc = pylint_rc
        self.ignore = ignore

        threading.Thread.__init__(self)

    def run(self):

        command = [self.python_bin,
                   self.pylint_path,
                   '--output-format=parseable',
                   '--include-ids=y',
                   self.file_name]

        if self.pylint_rc:
            command.insert(-2, '--rcfile=%s' % self.pylint_rc)

        # Prevent the console from popping up
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        else:
            startupinfo = None

        original = os.environ.get('PYTHONPATH', '')

        speak("Current PYTHONPATH is '%s'" % original)

        org_path_lst = [p for p in re.split(SEPERATOR_PATTERN, original) if p]
        pyl_path_lst = [p for p in re.split(SEPERATOR_PATTERN, self.python_path) if p]

        pythonpaths = set(org_path_lst + pyl_path_lst)

        os.environ['PYTHONPATH'] = PATH_SEPERATOR.join(pythonpaths)
        speak("Updated PYTHONPATH is '%s'" % os.environ['PYTHONPATH'])

        speak("Running command:\n    ", " ".join(command))

        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             startupinfo=startupinfo,
                             cwd=self.working_dir)
        output, dummy = p.communicate()

        lines = [line for line in output.split('\n')] #pylint: disable=E1103
        # Call set_timeout to have the error processing done from the main thread
        sublime.set_timeout(lambda: self.process_errors(lines), 100)

    def process_errors(self, lines):
        view_id = self.view.id()
        global PYLINTER_ERRORS
        PYLINTER_ERRORS[view_id] = {"visible": True}

        for line in lines:
            mdic = re.match(P_PYLINT_ERROR, line)
            if mdic:
                m = mdic.groupdict()
                line_num = int(m['line']) - 1
                if m['type'].lower() not in self.ignore:
                    PYLINTER_ERRORS[view_id][line_num] = "%s%s: %s " % (m['type'], m['errno'], m['msg'].strip())
                    speak(PYLINTER_ERRORS[view_id][line_num])

        show_errors(self.view)

class BackgroundPylinter(sublime_plugin.EventListener):
    def __init__(self):
        sublime_plugin.EventListener.__init__(self)
        self.last_selected_line = -1

    def _last_selected_lineno(self, view):
        return view.rowcol(view.sel()[0].end())[0]

    def on_post_save(self, view):
        if view.file_name().endswith('.py') and get_setting('run_on_save', False):
            view.run_command('pylinter')

    def on_selection_modified(self, view):
        view_id = view.id()
        if PYLINTER_ERRORS.has_key(view_id):
            last_selected_line = self._last_selected_lineno(view)

            if last_selected_line != self.last_selected_line:
                self.last_selected_line = last_selected_line
                if PYLINTER_ERRORS[view_id].has_key(self.last_selected_line):
                    sublime.status_message(PYLINTER_ERRORS[view_id][self.last_selected_line])

def popup_error_list(view):
    view_id = view.id()

    if not PYLINTER_ERRORS.has_key(view_id):
        return

    # No errors were found
    if len(PYLINTER_ERRORS[view_id]) == 1:
        sublime.message_dialog("No Pylint errors found")
        return

    errors = [(key + 1, unicode(value, errors='ignore')) for key, value in PYLINTER_ERRORS[view_id].items() if key != 'visible']
    line_nums, panel_items = zip(*sorted(errors, key=lambda error: error[1]))

    def on_done(selected_item):
        if selected_item == -1:
            return
        view.run_command("goto_line", {"line": line_nums[selected_item]})

    view.window().show_quick_panel(list(panel_items), on_done)
