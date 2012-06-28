# -*- coding: utf-8 -*-

""" PyLinter

    https://github.com/biermeester/Pylinter
"""

import os.path
import sys
import re
import threading
import subprocess
import sublime
import sublime_plugin

settings = sublime.load_settings('Pylinter.sublime-settings')

# Regular expression to disect Pylint error messages
P_PYLINT_ERROR = re.compile(r"""
                            ^(?P<file>.+?):(?P<line>[0-9]+):\ # file name and line number
                            \[(?P<type>[a-z])(?P<errno>\d+)   # message type and error number, e.g. E0101
                            (,\ (?P<hint>.+))?\]\             # optional class or function name
                            (?P<msg>.*)                       # finally, the error message
                            """, re.IGNORECASE|re.VERBOSE)

PYLINTER_VERBOSE = False
PYLINTER_ERRORS = {}

def speak(*msg):
    """ Log messages to the console if VERBOSE is True """
    if PYLINTER_VERBOSE:
        print " - PyLinter: ", " ".join(msg)

def show_errors(view):
    outlines = []
    for line_num in [k for k in PYLINTER_ERRORS[view.id()].keys() if isinstance(k, int)]:
        outlines.append(view.line(view.text_point(line_num, 0)))
    view.add_regions('pylinter', outlines, 'pylinter', 'dot', sublime.DRAW_OUTLINED)

class PylinterCommand(sublime_plugin.TextCommand):

    def run(self, edit, **kwargs):

        self._read_settings()

        if kwargs.has_key('action') and kwargs['action'] == 'toggle':
            self.toggle_regions()
        elif kwargs.has_key('action') and kwargs['action'] == 'list':
            popup_error_list(self.view)
        elif kwargs.has_key('action') and kwargs['action'] == 'dump':
            self.dump_errors()
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

        PYLINTER_VERBOSE = settings.get('verbose', False)
        self.python_bin = settings.get('python_bin', 'python')
        self.python_path = ";".join([str(p) for p in settings.get('python_path', [])])
        self.working_dir = settings.get('working_dir', None) or None
        self.pylint_path = settings.get('pylint_path', None)
        self.pylint_rc = settings.get('pylint_rc', None) or ""
        self.ignore = [t.lower() for t in settings.get('ignore', [])]

        # Search for project settings
        try:
            for folder in sublime.active_window().folders():
                files_list = os.listdir(folder)
                for f in [fname for fname in files_list if fname.endswith('sublime-project')]:
                    speak("Scanning projectfile %s for additional settings" % f)
                    import json
                    with open(os.path.join(folder, f),'r') as psettings_file:
                        project_settings = json.load(psettings_file)

                    if project_settings.has_key('settings'):
                        project_settings = project_settings['settings']
                        if project_settings.has_key('pylinter'):
                            project_settings = project_settings['pylinter']

                            if project_settings.has_key('verbose'):
                                PYLINTER_VERBOSE = project_settings.get('verbose', False)
                            if project_settings.has_key('python_bin'):
                                self.python_bin = project_settings.get('python_bin', 'python')
                            if project_settings.has_key('python_path'):
                                self.python_path = ";".join([str(p) for p in project_settings.get('python_path', [])])
                            if project_settings.has_key('working_dir'):
                                self.working_dir = project_settings.get('working_dir', None) or None
                            if project_settings.has_key('pylint_path'):
                                self.pylint_path = project_settings.get('pylint_path', None)
                            if project_settings.has_key('pylint_rc'):
                                self.pylint_rc = project_settings.get('pylint_rc', None) or ""
                            if project_settings.has_key('ignore'):
                                self.ignore = [t.lower() for t in project_settings.get('ignore', [])]

                    raise StopIteration()
        except StopIteration:
            pass


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

    def is_enabled(self):
        file_name = self.view.file_name()
        if file_name:
            return file_name.endswith('.py')

class PylintThread(threading.Thread):
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

        os.environ['PYTHONPATH'] = ";".join([self.python_path, os.environ.get('PYTHONPATH', "")])
        p = subprocess.Popen(command,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             startupinfo=startupinfo,
                             cwd=self.working_dir)
        output, dummy = p.communicate()

        lines = [line for line in output.split('\n')]
        # Call set_timeout to have the error processing done from teh main thread
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
        if view.file_name().endswith('.py') and settings.get('run_on_save', False):
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
