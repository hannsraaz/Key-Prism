"""Explicit opt-in Windows startup for the current user only."""
import subprocess
import sys
from pathlib import Path

def set_enabled(enabled, live=False):
    import winreg
    key_name = r'Software\Microsoft\Windows\CurrentVersion\Run'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_name) as key:
        if enabled:
            executable = Path(sys.executable)
            pythonw = executable.with_name('pythonw.exe')
            command = [str(pythonw if pythonw.exists() else executable),
                       str(Path(__file__).resolve().parents[1]/'launch.py'), '--autostart']
            if live:
                command.append('--live')
            winreg.SetValueEx(key, 'AcerRGB-SingleZone', 0, winreg.REG_SZ, subprocess.list2cmdline(command))
        else:
            try:
                winreg.DeleteValue(key, 'AcerRGB-SingleZone')
            except FileNotFoundError:
                pass
