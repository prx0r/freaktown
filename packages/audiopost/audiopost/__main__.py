"""CLI.
  python -m audiopost run --vo vo.wav --plan plan.json --preset goodnight-studio --seed 7 --out DIR
  python -m audiopost measure FILE...
  python -m audiopost dry --vo vo.wav --out dry.wav
  python -m audiopost demo --out DIR        (synthetic tone-burst 'voice' through the chain; no TTS needed)
"""
import argparse
import json
import sys

from . import process
from .master import measure


def main(argv=None):
    ap = argparse.ArgumentParser(prog="audiopost")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--vo", required=True); r.add_argument("--plan", required=True)
    r.add_argument("--preset", default="goodnight-studio"); r.add_argument("--seed", type=int, default=1); r.add_argument("--out", required=True)
    r.add_argument("--set", action="append", default=[], help="override a knob: mic_drift.dip_db=3.0")
    m = sub.add_parser("measure"); m.add_argument("files", nargs="+")
    d = sub.add_parser("dry"); d.add_argument("--vo", required=True); d.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        P = process.load_preset(a.preset)
        for kv in a.set:
            k, v = kv.split("=", 1)
            node = P
            ks = k.split(".")
            for kk in ks[:-1]:
                node = node[kk]
            node[ks[-1]] = json.loads(v)
        rep = process.run(a.vo, json.load(open(a.plan)), P, a.seed, a.out)
        print(json.dumps({k: rep[k] for k in ("mix", "master", "sha256_master")}, indent=1))
    elif a.cmd == "measure":
        for f in a.files:
            print(f, json.dumps(measure(f)))
    elif a.cmd == "dry":
        print(json.dumps(process.dry_master(a.vo, a.out)))


if __name__ == "__main__":
    sys.exit(main())
