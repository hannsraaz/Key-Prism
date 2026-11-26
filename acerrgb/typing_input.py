"""Global key-down notification. Never dereferences the key payload."""
import ctypes
from ctypes import wintypes
import os
import threading

class TypingInput:
    def __init__(self, on_press):
        self.on_press = on_press
        self._thread = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._tid = None
        self.error = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        if os.name != 'nt':
            raise RuntimeError('Global typing requires Windows')
        self._ready.clear()
        self._stop.clear()
        self.error = None
        self._thread = threading.Thread(target=self._run, name='Typing notification', daemon=True)
        self._thread.start()
        if not self._ready.wait(2):
            self.stop()
            raise RuntimeError('Keyboard hook startup timed out')
        if self.error:
            raise RuntimeError(self.error)

    def stop(self):
        self._stop.set()
        if self._tid and hasattr(self, '_user'):
            self._user.PostThreadMessageW(self._tid, 0x0012, 0, 0)
        if self._thread:
            self._thread.join(1)

    def _run(self):
        hook = None
        try:
            user = self._user = ctypes.WinDLL('user32', use_last_error=True)
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                                              wintypes.WPARAM, wintypes.LPARAM)
            user.SetWindowsHookExW.argtypes = [ctypes.c_int, callback_type, wintypes.HINSTANCE, wintypes.DWORD]
            user.SetWindowsHookExW.restype = wintypes.HANDLE
            user.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
            user.CallNextHookEx.restype = ctypes.c_ssize_t
            user.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
            user.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            user.GetMessageW.restype = wintypes.BOOL
            user.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
            user.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            kernel.GetCurrentThreadId.restype = wintypes.DWORD
            kernel.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            kernel.GetModuleHandleW.restype = wintypes.HMODULE
            self._tid = kernel.GetCurrentThreadId()
            msg = wintypes.MSG()
            user.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

            @callback_type
            def callback(code, message, payload):
                if code >= 0 and message in (0x0100, 0x0104):
                    # Only key-down occurrence is used. No key code, character,
                    # window title, event history, logging or file access.
                    try:
                        self.on_press()
                    except Exception:
                        pass
                return user.CallNextHookEx(None, code, message, payload)

            hook = user.SetWindowsHookExW(13, callback, kernel.GetModuleHandleW(None), 0)
            if not hook:
                raise ctypes.WinError(ctypes.get_last_error())
            self._ready.set()
            while not self._stop.is_set():
                result = user.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == -1:
                    raise ctypes.WinError(ctypes.get_last_error())
                if result == 0:
                    break
        except Exception as exc:
            self.error = str(exc)
        finally:
            if hook:
                user.UnhookWindowsHookEx(hook)
            self._tid = None
            self._ready.set()
