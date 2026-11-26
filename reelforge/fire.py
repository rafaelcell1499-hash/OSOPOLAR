"""Fuego procedural (sin assets externos): se genera con geq/curves y se mezcla en modo 'screen'."""
from __future__ import annotations
import os
from . import ffutil
from .ffutil import Graph

FIRE_DUR = 2.6

_HEAT = {
    "bottom": "pow(Y/H,1.1)*2.6",
    "full": "(0.50+0.50*Y/H)*2.5",
}


def _expr(kind: str) -> str:
    heat = _HEAT[kind]
    return ("255*clip(" + heat + "*(0.5"
            "+0.2*sin(X*0.13+5*sin((Y+T*240)*0.013+X*0.02)+T*2.3)"
            "+0.17*sin(X*0.29-(Y+T*330)*0.027+4*sin(X*0.043+T*6.1))"
            "+0.13*sin(X*0.61+(Y+T*420)*0.05+3*sin((Y+T*300)*0.021-X*0.07)))-"
            + ("0.42" if kind == "bottom" else "0.62") + ",0,1)")


def ensure_assets(workdir: str, W: int, H: int, fps: int, kinds=("bottom", "full"), log=None,
                  cancel=None) -> dict:
    out = {}
    for k in kinds:
        path = os.path.join(workdir, f"fire_{k}.mp4")
        if not os.path.exists(path):
            if log:
                log(f"Generando fuego procedural ({k})…")
            vf = (f"nullsrc=s=270x480:r={fps}:d={FIRE_DUR},format=gray,geq=lum='{_expr(k)}',"
                  "noise=alls=45:allf=t,curves=all='0/0 0.18/0 0.6/0.6 1/1',gblur=sigma=1.2,format=rgb24,"
                  "curves=r='0/0 0.25/0.9 0.5/1 1/1':g='0/0 0.25/0 0.55/0.7 0.85/1 1/1':"
                  "b='0/0 0.65/0 0.9/0.45 1/1',"
                  f"scale={W}:{H}:flags=bicubic,gblur=sigma={max(2, W // 270)},format=yuv420p")
            ffutil.run_ffmpeg(["-f", "lavfi", "-i", vf, "-c:v", "libx264", "-preset", "veryfast",
                               "-crf", "16", "-an", path], cancel=cancel, log=log)
        out[k] = path
    return out


def overlay(g: Graph, src: str, fire_in: str, strength: float, hold: float = 0.25) -> str:
    """Mezcla el flujo de fuego `fire_in` sobre `src` (screen) con fade in/out al inicio del segmento."""
    f = g.f(fire_in, f"setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.10,fade=t=out:st={hold:.2f}:d=0.55,"
                     "format=gbrp")
    b = g.f(src, "format=gbrp")
    out = g.new()
    g.raw(f"[{b}][{f}]blend=all_mode=screen:all_opacity={strength:.2f}:shortest=1:"
          f"enable='lt(t,{hold + 0.7:.2f})'[{out}]")
    return g.f(out, "format=yuv420p")
