"""Floating point perceptual RGB; gamma is applied once at the output."""
import math

BLACK = (0.0, 0.0, 0.0)

def clamp(value):
    return max(0.0, min(1.0, value))

def parse_color(value):
    value = value.lstrip('#')
    if len(value) != 6:
        raise ValueError('Use six hexadecimal colour digits')
    return tuple(int(value[i:i+2], 16) / 255 for i in (0, 2, 4))

def mix(a, b, amount):
    amount = clamp(amount)
    return tuple(x + (y - x) * amount for x, y in zip(a, b))

def encode(color, brightness=1.0, gamma=2.2):
    if not math.isfinite(brightness) or not math.isfinite(gamma) or gamma <= 0:
        raise ValueError('Invalid brightness or gamma')
    if len(color) != 3 or not all(math.isfinite(x) for x in color):
        raise ValueError('Invalid RGB frame')
    return tuple(round(clamp(x * brightness) ** gamma * 255) for x in color)
