"""Uso sin interfaz: python -m reelforge.cli --videos a.mp4 b.mp4 --audio musica.mp3 --out reel.mp4"""
import argparse, json
from .config import Settings, apply_preset, PRESETS
from . import engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", nargs="+", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", default="reel.mp4")
    ap.add_argument("--preset", default="Hype / Phonk", choices=list(PRESETS))
    ap.add_argument("--duration", type=float, default=30)
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--auto-window", action="store_true")
    ap.add_argument("--text", default="")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    s = apply_preset(Settings(), a.preset)
    s.duration, s.start, s.auto_window, s.seed, s.preview = a.duration, a.start, a.auto_window, a.seed, a.preview
    if a.text:
        s.text_enabled, s.text = True, a.text
    engine.render(s, a.videos, a.audio, a.out,
                  progress=lambda f, m="": print(f"\r{f*100:5.1f}% {m}      ", end="", flush=True),
                  log=print)
    print()


if __name__ == "__main__":
    main()
