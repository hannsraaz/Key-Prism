"""Hardware-free scheduler benchmark. Never loads the DLL or captures input."""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acerrgb.hardware import Hardware
from acerrgb.engine import Engine
from acerrgb.effects import Rainbow

def benchmark(seconds=3):
    results=[]
    for fps in (10,15,20,30):
        hardware=Hardware()
        engine=Engine(hardware,fps=fps)
        engine.select(Rainbow())
        cpu=time.process_time()
        wall=time.monotonic()
        engine.start()
        time.sleep(seconds)
        engine.stop()
        elapsed=time.monotonic()-wall
        results.append(dict(fps=fps,frames=engine.frames,writes=hardware.writes,
                            actual_fps=round(engine.frames/elapsed,2),
                            cpu_ms=round((time.process_time()-cpu)*1000,2),error=engine.error))
    return results

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--seconds',type=float,default=3)
    args=parser.parse_args()
    print(json.dumps(benchmark(max(1,args.seconds)),indent=2))
