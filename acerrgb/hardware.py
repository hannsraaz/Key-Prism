"""Only the existing verified three-call single-zone protocol is exposed."""
import threading
import time

class Hardware:
    _lock = threading.RLock()

    def __init__(self, live=False, bridge=None):
        self.live = live
        self.bridge = bridge
        self.last = None
        self.writes = 0
        self.skipped = 0
        self.latency_ms = 0.0
        self.last_packet = None
        self._mutex = None
        self._owns_bridge = bridge is None

    def open(self):
        if self.live and self.bridge is None:
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
            kernel.CreateMutexW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self._kernel = kernel
            self._mutex = kernel.CreateMutexW(None, False, 'Local\\AcerRGB.SingleZone')
            if not self._mutex:
                raise ctypes.WinError(ctypes.get_last_error())
            if ctypes.get_last_error() == 183:
                self.close()
                raise RuntimeError('Another AcerRGB instance owns the lighting interface')
            try:
                from .vendor import DCHU
                self.bridge = DCHU()
            except Exception:
                self.close()
                raise

    def write(self, rgb):
        if len(rgb) != 3 or any(type(x) is not int or not 0 <= x <= 255 for x in rgb):
            raise ValueError('RGB output must contain three bytes')
        with self._lock:
            if rgb == self.last:
                self.skipped += 1
                return
            r, g, b = rgb
            packet = bytes((g, r, b, 0xF0))
            started = time.perf_counter()
            if self.live:
                if self.bridge is None:
                    raise RuntimeError('Hardware session is not open')
                # Return values are vendor-specific; never infer HRESULT semantics.
                result = self.bridge.set_dchu_data(0x67, packet)
                if result != 0x67:
                    raise RuntimeError(f'Unexpected SetDCHU_Data result: {result!r}')
                self.bridge.write_app_settings(2, 0x51, bytes((g, r, 0)))
                self.bridge.write_app_settings(2, 0x20, bytes((8,)))
            self.last_packet = packet
            self.last = rgb
            self.writes += 1
            self.latency_ms = (time.perf_counter()-started)*1000

    def snapshot(self):
        # The verified settings write omits blue. There is no verified complete
        # RGB/mode readback: do not fabricate restoration from those bytes.
        # A previously applied colour within this session is fully known.
        return self.last

    def close(self):
        if self._mutex:
            self._kernel.CloseHandle(self._mutex)
            self._mutex = None
        if self._owns_bridge:
            self.bridge = None
