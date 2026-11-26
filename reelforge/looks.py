"""Looks de color/arte y acentos temporales (flash, glitch, etc.)."""
from __future__ import annotations
from .ffutil import Graph

SIMPLE = {
    "natural": "eq=contrast=1.06:saturation=1.1",
    "contrast": "eq=contrast=1.2:saturation=1.3:gamma=0.95,unsharp=5:5:0.7",
    "bw": "hue=s=0,eq=contrast=1.4:brightness=-0.03",
    "teal_orange": ("colorbalance=rs=-0.1:bs=0.12:rh=0.15:bh=-0.12:gh=0.03,"
                    "eq=contrast=1.12:saturation=1.2"),
    "fire_grade": ("colorbalance=rs=0.22:gs=0.02:bs=-0.2:rm=0.18:bm=-0.14:rh=0.15:bh=-0.12,"
                   "eq=contrast=1.2:saturation=1.35:gamma=0.95"),
    "ice": ("colorbalance=rs=-0.15:bs=0.22:rm=-0.1:bm=0.15:bh=0.1,"
            "eq=contrast=1.1:saturation=0.95:brightness=0.02"),
    "vaporwave": ("colorbalance=rs=0.12:bs=0.2:rm=0.05:bm=0.15:gm=-0.1:rh=0.12:bh=0.15,"
                  "eq=saturation=1.5:contrast=1.1"),
    "sepia": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131,eq=contrast=1.1",
    "vintage": "curves=preset=vintage,noise=alls=10:allf=t,eq=saturation=0.9",
    "vhs": ("chromashift=crh=6:cbh=-6,noise=alls=16:allf=t,eq=saturation=1.3:contrast=1.05,"
            "unsharp=3:3:-0.8"),
    "posterize": ("lutyuv=y='trunc(val/36)*36+10':u='trunc(val/40)*40+8':v='trunc(val/40)*40+8',"
                  "eq=saturation=1.6:contrast=1.1"),
}


def _glow(g: Graph, src: str, sigma: float, opacity: float, pre: str = "") -> str:
    a, b = g.new(), g.new()
    g.raw(f"[{src}]split[{a}][{b}]")
    bl = g.f(b, "gblur=sigma=%s" % sigma)
    out = g.new()
    g.raw(f"[{a}][{bl}]blend=all_mode=screen:all_opacity={opacity}[{out}]")
    return out


def apply_look(g: Graph, src: str, name: str) -> str:
    if name in SIMPLE:
        return g.f(src, SIMPLE[name])
    if name == "neon":
        x = g.f(src, "eq=saturation=1.8:contrast=1.25,colorbalance=rs=0.15:bs=0.2:gh=-0.08")
        return _glow(g, x, 22, 0.55)
    if name == "cyber":
        x = g.f(src, "colorbalance=rs=0.2:bs=0.25:gm=-0.1:rh=0.1,eq=saturation=1.5:contrast=1.2,"
                     "rgbashift=rh=4:bh=-4")
        return _glow(g, x, 14, 0.4)
    if name == "dream":
        x = g.f(src, "eq=brightness=0.03:saturation=1.15:contrast=0.97")
        return _glow(g, x, 18, 0.6)
    if name == "comic":
        a, b = g.new(), g.new()
        g.raw(f"[{src}]split[{a}][{b}]")
        base = g.f(a, SIMPLE["posterize"])
        edges = g.f(b, "edgedetect=low=0.08:high=0.25:mode=wires,negate,format=yuv420p")
        base = g.f(base, "format=yuv420p")
        out = g.new()
        g.raw(f"[{base}][{edges}]blend=all_mode=multiply[{out}]")
        return out
    if name == "neon_edges":
        a, b = g.new(), g.new()
        g.raw(f"[{src}]split[{a}][{b}]")
        base = g.f(a, "eq=brightness=-0.28:saturation=0.9,format=yuv420p")
        edges = g.f(b, "edgedetect=low=0.06:high=0.2:mode=colormix,eq=brightness=0.1:saturation=2.4,"
                       "gblur=sigma=1.2,format=yuv420p")
        out = g.new()
        g.raw(f"[{base}][{edges}]blend=all_mode=screen[{out}]")
        return _glow(g, out, 10, 0.5)
    return src


def apply_accents(g: Graph, src: str, hit: float, flags: dict) -> str:
    """flags: flash(bool), rgb(bool), negate(bool), bwflash(bool)."""
    x = src
    if flags.get("flash"):
        x = g.f(x, f"eq=brightness='0.6*gte(t,{hit:.3f})*exp(-9*(t-{hit:.3f}))':eval=frame")
    if flags.get("rgb"):
        x = g.f(x, f"rgbashift=rh=16:bh=-16:gv=7:enable='between(t,{hit:.3f},{hit + 0.16:.3f})'")
    if flags.get("negate"):
        x = g.f(x, f"negate=enable='between(t,{hit:.3f},{hit + 0.07:.3f})'")
    if flags.get("bwflash"):
        x = g.f(x, f"hue=s=0:enable='between(t,{hit:.3f},{hit + 0.14:.3f})'")
    return x


def finishing(g: Graph, src: str, vignette: bool, grain: bool) -> str:
    x = src
    if vignette:
        x = g.f(x, "vignette=angle=PI/4.2")
    if grain:
        x = g.f(x, "noise=alls=7:allf=t")
    return x
