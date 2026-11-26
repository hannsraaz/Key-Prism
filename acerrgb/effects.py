"""Pure, monotonic-time single-zone effects. No hardware calls."""
from dataclasses import dataclass
import colorsys
import math
from .color import BLACK, mix

@dataclass
class Static:
    color: tuple = BLACK
    def render(self, elapsed, dt, pressed=False):
        return self.color

@dataclass
class Rainbow:
    duration: float = 8.0
    saturation: float = 1.0
    def render(self, elapsed, dt, pressed=False):
        return colorsys.hsv_to_rgb((elapsed / self.duration) % 1, self.saturation, 1)

@dataclass
class Breathing:
    color: tuple = (1.0, 0.0, 0.0)
    duration: float = 3.0
    minimum: float = 0.05
    def render(self, elapsed, dt, pressed=False):
        level = self.minimum + (1-self.minimum) * (1-math.cos(2*math.pi*elapsed/self.duration))/2
        return tuple(c * level for c in self.color)

@dataclass
class Typing:
    idle: tuple = BLACK
    flash: tuple = (1.0, 1.0, 1.0)
    intensity: float = 1.0
    duration: float = 0.7
    last_press: float = -math.inf
    def render(self, elapsed, dt, pressed=False):
        if pressed:
            self.last_press = elapsed
        age = max(0.0, elapsed-self.last_press)
        x = min(1.0, age/self.duration)
        # Cubic release reaches idle exactly; rapid presses simply retrigger.
        envelope = (1-x)**2 * (1+2*x)
        return mix(self.idle, self.flash, self.intensity * envelope)

class Music:
    def __init__(self, capture, sensitivity=1.0, attack=0.035, decay=0.35):
        from .audio import Analyzer
        self.capture = capture
        self.analyzer = Analyzer(capture.samplerate)
        self.sensitivity, self.attack, self.decay = sensitivity, attack, decay
        self.color = BLACK
        self.sequence = -1
        self.target = BLACK
        self.beat = 0.0

    def render(self, elapsed, dt, pressed=False):
        sequence, chunk = self.capture.latest()
        if chunk is None:
            self.target = BLACK
        elif sequence != self.sequence:
            self.sequence = sequence
            bands, beat = self.analyzer.analyze(chunk, elapsed)
            self.target = tuple(min(1.0, x*self.sensitivity) for x in bands)
            if beat:
                self.beat = 0.25
        self.beat *= math.exp(-dt/0.15)
        target = tuple(min(1.0, x+self.beat) for x in self.target)
        self.color = tuple(x + (y-x)*(1-math.exp(-dt/(self.attack if y>x else self.decay)))
                           for x,y in zip(self.color, target))
        return self.color
