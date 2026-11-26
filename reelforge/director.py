"""Director: decide cortes, velocidad, cámara, look, transición y acentos de cada segmento."""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from . import audio, ffutil
from .config import TRANSITION_XFADE


@dataclass
class Seg:
    idx: int
    B0: float                # límite (beat) inicial, relativo al audio
    B1: float
    energy: float
    power: float
    trans: str = "cut"       # cut | nombre xfade
    trans_kind: str = "cut"  # nombre lógico (fire, flash, whip...)
    td: float = 0.0
    L: float = 0.0           # duración visible renderizada
    avg: float = 1.0
    S: float = 0.0           # duración tomada del origen
    speed_kind: str = "none"
    speed_w: float = 0.0
    cams: list = field(default_factory=list)
    look: str = "natural"
    accents: dict = field(default_factory=dict)
    fire: str | None = None
    fire_strength: float = 0.8
    # asignados al renderizar
    clip: str = ""
    src_start: float = 0.0
    loop: bool = False

    @property
    def D(self):
        return self.B1 - self.B0

    @property
    def a(self):
        return self.td / 2


@dataclass
class Plan:
    start: float
    end: float
    segs: list


def _wchoice(rng, items, weights):
    return rng.choices(items, weights=weights)[0]


def make_plan(s, an: audio.AudioAnalysis, start: float, end: float) -> Plan:
    rng = random.Random(s.seed)
    bounds = audio.plan_cuts(an, start, end, s.sync_mode, s.min_cut)
    n = len(bounds) - 1
    xf_ok = ffutil.capabilities()["xfade"] or set()
    segs: list[Seg] = []
    prev_look = None
    looks = list(s.looks) or ["natural"]
    for k in range(n):
        B0, B1 = bounds[k], bounds[k + 1]
        e = an.mean_energy(B0, B1)
        power = min(1.0, max(0.0, e * 0.55 + s.intensity * 0.45 + rng.uniform(-0.05, 0.05)))
        sg = Seg(k, B0, B1, e, power)

        # ---- transición hacia este segmento ----
        if k > 0:
            pool = list(s.transitions) or ["cut"]
            tk = rng.choice(pool)
            if tk == "fire" and rng.random() > 0.3 + 0.7 * max(s.fire_amount, 0.2):
                tk = "flash" if "flash" in pool else rng.choice(pool)
            if tk == "cut" and power < 0.35 and len(pool) > 1:
                tk = rng.choice([p for p in pool if p != "cut"])
            sg.trans_kind = tk
            if tk in ("cut", "glitchcut"):
                sg.trans, sg.td = "cut", 0.0
                if tk == "glitchcut":
                    sg.accents.update(rgb=True, negate=rng.random() < 0.4)
            else:
                names = [x for x in TRANSITION_XFADE.get(tk, ["fade"]) if x in xf_ok]
                if not names:
                    names = ["fade"] if "fade" in xf_ok else []
                if not names:
                    sg.trans, sg.td = "cut", 0.0
                else:
                    sg.trans = rng.choice(names)
                    base = {"flash": 0.18, "whip": 0.2, "fire": 0.28}.get(tk, 0.38 - 0.24 * power)
                    sg.td = max(0.1, base)
                if tk == "fire":
                    sg.fire, sg.fire_strength = "full", 0.95
            lim = 0.5 * min(segs[-1].D, sg.D)
            sg.td = min(sg.td, lim)
            if sg.td < 0.08:
                sg.trans, sg.td = "cut", 0.0

        # ---- velocidad ----
        if s.speed_curves and s.speed_kinds and rng.random() < 0.3 + 0.6 * power:
            kinds = list(s.speed_kinds)
            wts = []
            for kd in kinds:
                if kd in ("impact", "bullet"):
                    wts.append(2.0 if power > 0.5 else 0.8)
                elif kd == "rampup":
                    wts.append(1.5 if power < 0.6 else 1.0)
                else:
                    wts.append(1.0)
            sg.speed_kind = _wchoice(rng, kinds, wts)
            sg.speed_w = min(0.85, 0.25 + 0.6 * s.speed_amount * (0.5 + 0.5 * power))
            sg.avg = (0.85 + (1.0 + 0.6 * s.speed_amount - 0.85) * power) * rng.uniform(0.92, 1.05)
        else:
            sg.avg = 1.0

        # ---- cámara ----
        cams = list(s.camera_fx)
        if cams:
            w = []
            for c in cams:
                if c == "punch":
                    w.append(2.2 if power > 0.5 else 0.6)
                elif c == "shake":
                    w.append(1.6 if power > 0.62 else 0.15)
                elif c in ("zoom_in", "zoom_out"):
                    w.append(1.2 if power < 0.7 else 0.7)
                else:
                    w.append(0.9)
            first = _wchoice(rng, cams, w)
            sg.cams = [first]
            extra = [c for c in ("shake", "punch", "roll") if c in cams and c != first]
            if extra and rng.random() < 0.5 * power:
                sg.cams.append(rng.choice(extra))

        # ---- look ----
        if s.look_mode == "fixed" or len(looks) == 1:
            sg.look = looks[0]
        elif s.look_mode == "energy":
            half = max(1, len(looks) // 2)
            pool = looks[:half] if power < 0.62 else looks[half:]
            sg.look = rng.choice(pool or looks)
        else:
            cand = [l for l in looks if l != prev_look] or looks
            sg.look = rng.choice(cand)
        prev_look = sg.look

        # ---- acentos ----
        acc = set(s.accents)
        if "flash" in acc and rng.random() < 0.2 + 0.55 * power and sg.trans_kind not in ("flash", "fire"):
            sg.accents["flash"] = True
        if "glitch" in acc and rng.random() < 0.08 + 0.5 * power ** 2:
            t = rng.choice(["rgb", "negate", "bwflash"])
            sg.accents[t] = True
        if ("fire" in acc and s.fire_amount > 0 and sg.fire is None and power > 0.55
                and rng.random() < s.fire_amount * power):
            sg.fire = "bottom" if rng.random() < 0.75 else "full"
            sg.fire_strength = 0.55 + 0.4 * s.fire_amount
        segs.append(sg)

    # ---- duraciones visibles y fuente ----
    for k, sg in enumerate(segs):
        nxt = segs[k + 1].td if k + 1 < len(segs) else 0.0
        sg.L = sg.D + sg.td / 2 + nxt / 2
        sg.S = sg.L * sg.avg
    return Plan(start, end, segs)
