"""WASAPI playback loopback only; bounded buffers, retry and stale-data expiry."""
import math
import threading
import time
from collections import deque
import numpy as np

class Analyzer:
    def __init__(self, samplerate=48000, noise_floor=0.001):
        self.samplerate, self.noise_floor = samplerate, noise_floor
        self.peaks = np.full(3, 0.02)
        self.flux = deque(maxlen=40)
        self.previous_bass = 0.0
        self.last_beat = -math.inf
        self.last_time = None
        self._n = 0

    def analyze(self, samples, now):
        mono = np.asarray(samples, dtype=float)
        if mono.ndim > 1:
            mono = mono.mean(axis=1)
        if len(mono) < 64 or not np.isfinite(mono).all():
            return (0.0, 0.0, 0.0), False
        mono = mono-mono.mean()  # reject DC offset
        rms = float(np.sqrt(np.mean(mono*mono)))
        dt = max(0, now-self.last_time) if self.last_time is not None else 0.1
        self.last_time = now
        if rms < self.noise_floor:
            self.previous_bass = 0
            self.flux.append(0)
            return (0.0, 0.0, 0.0), False
        n = len(mono)
        if self._n != n:
            self._n = n
            self.window = np.hanning(n)
            freqs = np.fft.rfftfreq(n, 1/self.samplerate)
            self.masks = [(freqs >= lo) & (freqs < hi) for lo, hi in
                          ((20, 250), (250, 2500), (2500, 12000))]
        spectrum = abs(np.fft.rfft(mono*self.window))*2/self.window.sum()
        energy = np.array([np.sqrt(np.sum(spectrum[m]**2)) for m in self.masks])
        self.peaks = np.maximum(energy, np.maximum(0.02, self.peaks*math.exp(-dt/5)))
        normalized = np.minimum(1, energy/self.peaks)
        flux = max(0, float(normalized[0])-self.previous_bass)
        # A short history cannot estimate variance reliably. Bound the learned
        # threshold below the normalized full-scale onset so strong beats remain
        # detectable after repeated kick/silence alternation.
        threshold = min(0.8, max(0.08, float(np.mean(self.flux)+1.5*np.std(self.flux)))) if len(self.flux) >= 8 else 0.08
        beat = flux > threshold and now-self.last_beat >= 0.2
        if beat:
            self.last_beat = now
        self.previous_bass = float(normalized[0])
        self.flux.append(flux)
        return tuple(float(x) for x in normalized), beat

class Loopback:
    def __init__(self, samplerate=48000, chunk_size=2048, backend=None):
        self.samplerate, self.chunk_size = samplerate, chunk_size
        self.backend = backend
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._data = None
        self._timestamp = 0
        self._sequence = 0
        self.status = 'Stopped'

    def latest(self):
        with self._lock:
            return self._sequence, self._data if time.monotonic()-self._timestamp < 0.3 else None

    def start(self):
        if self._thread and self._thread.is_alive():
            if self._stop.is_set():
                raise RuntimeError('Previous audio stream is still stopping')
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='WASAPI loopback', daemon=True)
        self._thread.start()

    def stop(self, timeout=1):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
        with self._lock:
            self._data = None
        return not (self._thread and self._thread.is_alive())

    def _run(self):
        while not self._stop.is_set():
            try:
                if self.backend is None:
                    import soundcard
                    self.backend = soundcard
                speaker = self.backend.default_speaker()
                if speaker is None:
                    raise RuntimeError('No default playback device')
                # Match endpoint IDs, not ambiguous friendly names. Never select
                # an unrelated loopback endpoint or a physical microphone.
                device = next((m for m in self.backend.all_microphones(include_loopback=True)
                               if m.isloopback and m.id == speaker.id), None)
                if device is None:
                    raise RuntimeError('Default playback loopback unavailable')
                self.status = f'Listening: {speaker.name}'
                check_at = time.monotonic()+1
                with device.recorder(samplerate=self.samplerate, channels=2,
                                     blocksize=self.chunk_size) as recorder:
                    while not self._stop.is_set():
                        data = recorder.record(numframes=self.chunk_size)
                        with self._lock:
                            self._data = data
                            self._timestamp = time.monotonic()
                            self._sequence += 1
                        if time.monotonic() >= check_at:
                            current = self.backend.default_speaker()
                            if current is None or current.id != speaker.id:
                                break
                            check_at = time.monotonic()+1
            except Exception as exc:
                self.status = f'Audio unavailable; retrying: {exc}'
                with self._lock:
                    self._data = None
                self._stop.wait(1)
        self.status = 'Stopped'
