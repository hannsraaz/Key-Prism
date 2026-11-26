"""Default launch is a hardware-free preview. --live explicitly enables DLL I/O."""
import argparse
from acerrgb.app import main

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AcerRGB single-zone controls')
    parser.add_argument('--live',action='store_true',help='Enable verified vendor hardware writes')
    parser.add_argument('--autostart',action='store_true',help='Start saved effect immediately')
    args = parser.parse_args()
    raise SystemExit(main(args.live,args.autostart))
