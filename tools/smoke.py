"""Bounded four-effect dry run; synthetic audio/typing, no input capture or DLL."""
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from acerrgb.effects import Rainbow, Breathing, Music, Typing
from acerrgb.engine import Engine
from acerrgb.hardware import Hardware

class SyntheticAudio:
    samplerate=48000
    sequence=0
    def latest(self):
        self.sequence+=1
        amplitude=0.3 if self.sequence%5==1 else 0.02
        t=np.arange(2048)/self.samplerate
        return self.sequence, amplitude*np.sin(2*np.pi*100*t)

def run():
    result=[]
    for effect in (Rainbow(),Breathing(),Music(SyntheticAudio()),Typing()):
        hardware=Hardware()
        engine=Engine(hardware)
        engine.select(effect)
        engine.start()
        for _ in range(10):
            if isinstance(effect,Typing):
                engine.press()
            time.sleep(0.1)
        stopped=engine.stop()
        result.append(dict(effect=type(effect).__name__,stopped=stopped,error=engine.error,
                           writes=hardware.writes,last_rgb=hardware.last,
                           last_packet=list(hardware.last_packet or b'')))
    return result

if __name__=='__main__':
    results=run()
    print(json.dumps(results,indent=2))
    raise SystemExit(1 if any(r['error'] or not r['stopped'] or not r['writes'] for r in results) else 0)
