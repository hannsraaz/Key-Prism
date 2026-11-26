"""Validated, atomic per-user JSON configuration. No input/audio history."""
from dataclasses import dataclass, asdict, fields
from pathlib import Path
import json
import math
import os
import tempfile
from .color import parse_color

def config_path():
    return Path(os.environ.get('APPDATA', str(Path.home()))) / 'AcerRGB-SingleZone' / 'settings.json'

@dataclass
class Settings:
    effect: str = 'Rainbow'
    color: str = '2080ff'
    flash_color: str = 'ffffff'
    brightness: float = 0.7
    gamma: float = 2.2
    duration: float = 5.0
    saturation: float = 1.0
    minimum: float = 0.05
    sensitivity: float = 1.0
    intensity: float = 1.0
    decay: float = 0.7
    startup: bool = False

    def validate(self):
        if self.effect not in ('Static', 'Rainbow', 'Breathing', 'Music', 'Typing'):
            raise ValueError('Unknown effect')
        parse_color(self.color)
        parse_color(self.flash_color)
        for name, lo, hi in [('brightness',0,1), ('gamma',1,3), ('duration',0.2,120),
                             ('saturation',0,1), ('minimum',0,1), ('sensitivity',0.1,5),
                             ('intensity',0,1), ('decay',0.1,10)]:
            value = getattr(self, name)
            if type(value) not in (int,float) or not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError(f'Invalid {name}')
        if type(self.startup) is not bool:
            raise ValueError('Invalid startup preference')
        return self

    def save(self, path=None):
        self.validate()
        path = Path(path) if path else config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf8') as stream:
                json.dump(asdict(self), stream, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    @classmethod
    def load(cls, path=None):
        path = Path(path) if path else config_path()
        try:
            data = json.loads(path.read_text(encoding='utf8'))
            if not isinstance(data, dict):
                return cls()
            known = {f.name for f in fields(cls)}
            return cls(**{k:v for k,v in data.items() if k in known}).validate()
        except (OSError, ValueError, TypeError, AttributeError):
            return cls()
