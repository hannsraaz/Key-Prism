"""One worker owns rendering and serialized DLL I/O; callers never wait on I/O."""
import threading
import time
from .color import BLACK, encode, mix

class Engine:
    def __init__(self, hardware, fps=10, brightness=1.0, gamma=2.2, transition=0.35):
        if not 1 <= fps <= 30:
            raise ValueError('FPS must be between 1 and 30')
        self.hardware = hardware
        self.fps, self.brightness, self.gamma = fps, brightness, gamma
        self.transition = transition
        self._condition = threading.Condition()
        self._stop = False
        self._pending = None
        self._pressed = False  # one bit, never a key code or text
        self._thread = None
        self.error = None
        self.frames = 0
        self.last_color = BLACK
        self.restore_supported = False

    def select(self, effect, brightness=None, gamma=None):
        with self._condition:
            self._pending = (effect, brightness, gamma)
            self._pressed = False
            self._condition.notify()

    def press(self):
        with self._condition:
            self._pressed = True
            self._condition.notify()

    def start(self):
        with self._condition:
            if self._thread and self._thread.is_alive():
                return
            self._stop = False
            self.error = None
            self._thread = threading.Thread(target=self._run, name='RGB scheduler', daemon=True)
            self._thread.start()

    def stop(self, timeout=3):
        with self._condition:
            self._stop = True
            self._condition.notify_all()
        if self._thread:
            self._thread.join(timeout)
            return not self._thread.is_alive()
        return True

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def _run(self):
        effect = None
        previous = None
        last_tick = time.monotonic()
        deadline = last_tick
        changed = last_tick
        origin = BLACK
        failures = 0
        settled = False
        try:
            self.hardware.open()
            previous = self.hardware.snapshot()
            self.restore_supported = previous is not None
            while True:
                with self._condition:
                    while not self._stop:
                        delay = deadline-time.monotonic()
                        has_work = self._pending is not None or self._pressed or (effect is not None and not settled)
                        if delay <= 0 and has_work:
                            break
                        self._condition.wait(max(0.001, delay) if has_work else None)
                    if self._stop:
                        break
                    now = time.monotonic()
                    pending, self._pending = self._pending, None
                    pressed, self._pressed = self._pressed, False
                if pending:
                    effect, brightness, gamma = pending
                    origin, changed = self.last_color, now
                    if brightness is not None:
                        self.brightness = brightness
                    if gamma is not None:
                        self.gamma = gamma
                dt = max(0, now-last_tick)
                last_tick = now
                color = effect.render(now-changed, dt, pressed)
                # Blend in output space so changing brightness/gamma cannot jump.
                output = tuple(x/255 for x in encode(color, self.brightness, self.gamma))
                fraction = min(1.0, (now-changed)/self.transition) if self.transition else 1.0
                eased = fraction*fraction*(3-2*fraction)
                self.last_color = mix(origin, output, eased)
                rgb = tuple(round(x*255) for x in self.last_color)
                try:
                    self.hardware.write(rgb)
                    failures = 0
                except Exception as exc:
                    failures += 1
                    if failures >= 3:
                        raise RuntimeError('Hardware stopped after three failed writes') from exc
                self.frames += 1
                from .effects import Static, Typing
                settled = failures == 0 and fraction >= 1 and (
                    isinstance(effect, Static) or
                    isinstance(effect, Typing) and now-changed-effect.last_press >= effect.duration
                )
                # No catch-up bursts. Space complete three-call transactions.
                deadline = time.monotonic()+1/self.fps
        except Exception as exc:
            self.error = str(exc)
        finally:
            try:
                if previous is not None:
                    time.sleep(1/self.fps)
                    self.hardware.write(previous)
            except Exception as exc:
                self.error = f'Restoration failed: {exc}'
            finally:
                self.hardware.close()
