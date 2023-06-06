import sys
sys.path.insert(0, '..')
import os
import subprocess
import time
import signal
import subprocess
import tempfile
import pyautogui
import psutil
import win32con
from pywinauto import win32api
import win32gui
import win32process

from linguflex_interfaces import TextToSpeechModule_IF
from linguflex_log import log, DEBUG_LEVEL_OFF, DEBUG_LEVEL_MIN, DEBUG_LEVEL_MID, DEBUG_LEVEL_MAX
from linguflex_config import cfg, set_section, get_section, configuration_parsing_error_message
from linguflex_message import LinguFlexMessage

set_section('edge_texttospeech')

try:
    minimize_window = cfg[get_section()].getboolean('minimize_window', False)
    launch_wait_time_before_tts_init = cfg[get_section()].getfloat('launch_wait_time_before_tts_init', 0.75)
    tts_wait_time_before_minimize_init = cfg[get_section()].getfloat('tts_wait_time_before_minimize_init', 0.75)
    max_wait_time_for_close_windows = cfg[get_section()].getfloat('max_wait_time_for_close_windows', 1)
except Exception as e:
    raise ValueError(configuration_parsing_error_message + ' ' + str(e))

EDGE_FILENAME_READ_ALOUD = "linguflex_edge_read_aloud.html"

class TextToSpeechModule_Edge(TextToSpeechModule_IF):
    def __init__(self):
        temp_file_path = tempfile.gettempdir()
        self.path = os.path.join(temp_file_path, EDGE_FILENAME_READ_ALOUD)
        self.edge_path = os.path.join("C:\\", "Program Files (x86)", "Microsoft", "Edge", "Application", "msedge.exe")        

    def perform_text_to_speech(self, 
            message: LinguFlexMessage) -> None: 
        with open(self.path, 'w', encoding='utf-8') as file:
            file.write(message.output_user)
        # Search and kill running edge instances
        self.close_all_edge_windows()       
        # Start edge and wait for idle
        cmd = [self.edge_path, "file:///" + self.path]
        subprocess.Popen(cmd)
        time.sleep(launch_wait_time_before_tts_init)
        # Send read aloud hotkey 
        pyautogui.hotkey("ctrl", "shift", "u")
        time.sleep(tts_wait_time_before_minimize_init)
        if minimize_window: self.min_edge_windows()

    def find_edge_hwnds(self):
        edge_hwnds = []
        def window_enum_callback(hwnd, pids):
            _, process_id = win32process.GetWindowThreadProcessId(hwnd)
            if process_id in pids:
                edge_hwnds.append(hwnd)
                return True
        edge_processes = [p for p in psutil.process_iter() if p.name() == 'msedge.exe' and p.status() == 'running']
        if not edge_processes:
            log(DEBUG_LEVEL_MAX, 'no edge processes found')
            return []
        else:
            edge_pids = [p.pid for p in edge_processes]
            win32gui.EnumWindows(window_enum_callback, edge_pids)
            return edge_hwnds

    def min_edge_windows(self):
        hwnds = self.find_edge_hwnds()
        if hwnds:
            def minimize_window(hwnd):
                win32api.SendMessage(hwnd, win32con.WM_SYSCOMMAND, win32con.SC_MINIMIZE, 0)
            for hwnd in hwnds:
                minimize_window(hwnd)

    def close_edge_windows(self):
        hwnds = self.find_edge_hwnds()
        if hwnds:
            def close_window_wm_close(hwnd):
                win32api.SendMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            for hwnd in hwnds:
                close_window_wm_close(hwnd)

    def is_running_edge_process(self, p):
        try:
            return psutil.pid_exists(p.pid) and p.name() == 'msedge.exe' and p.status() == 'running'
        except psutil.NoSuchProcess:
            return False
        
    def shutdown(self):
        self.close_all_edge_windows()        

    def close_all_edge_windows(self):
        while True:
            edge_processes = [p for p in psutil.process_iter() if self.is_running_edge_process(p)]
            if not edge_processes: 
                break
            start_time = time.time()
            while time.time() - start_time < max_wait_time_for_close_windows:
                self.close_edge_windows()
                edge_processes = [p for p in psutil.process_iter() if self.is_running_edge_process(p)]
                if not edge_processes: 
                    break
            if not edge_processes: 
                break
            start_time = time.time()
            while time.time() - start_time < max_wait_time_for_close_windows:
                edge_processes = [p for p in psutil.process_iter() if self.is_running_edge_process(p)]
                if not edge_processes: 
                    break
                for edge_process in edge_processes:
                    try:
                        os.kill(edge_process.pid, signal.SIGTERM)
                    except OSError:
                        pass
            break # we don't want to loop, we only use 'while True', so we can abort early with break