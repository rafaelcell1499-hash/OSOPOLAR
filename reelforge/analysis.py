"""Análisis de los videos de origen (movimiento) y selección inteligente de fragmentos."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from . import ffutil

RATE = 5  # muestras de movimiento por segundo
TW, TH = 48, 80


@dataclass
class Clip:
    path: str
    duration: float
    motion: np.ndarray
    used: list


def motion_profile(path: str) -> np.ndarray:
    raw = ffutil.read_pipe(["-t", "1500", "-i", path, "-an", "-vf",
                            f"fps={RATE},scale={TW}:{TH}:force_original_aspect_ratio=increase,"
                            f"crop={TW}:{TH},format=gray", "-f", "rawvideo", "-"])
    a = np.frombuffer(raw, dtype=np.uint8)
    n = len(a) // (TW * TH)
    if n < 2:
        return np.ones(max(n, 1))
    a = a[:n * TW * TH].reshape(n, TW * TH).astype(np.float32)
    mot = np.abs(np.diff(a, axis=0, prepend=a[:1])).mean(axis=1)
    bright = a.mean(axis=1)
    mot = mot * np.clip((bright - 12) / 40.0, 0.05, 1.0)   # penaliza negros
    return mot


class ClipPool:
    def __init__(self, paths, log=None, cancel=None):
        self.clips: list[Clip] = []
        for p in paths:
            if cancel is not None and cancel.is_set():
                raise ffutil.Cancelled()
            info = ffutil.probe(p)
            if not info["has_video"]:
                continue
            if log:
                log(f"Analizando movimiento: {p.split('/')[-1].split(chr(92))[-1]}")
            try:
                mot = motion_profile(p)
            except Exception:
                mot = np.ones(max(1, int(info["duration"] * RATE)))
            self.clips.append(Clip(p, info["duration"], mot, []))
        if not self.clips:
            raise RuntimeError("No hay videos válidos.")
        self.i = 0

    def pick(self, src_len: float, power: float, rng):
        """Elige (clip, inicio). Energía alta -> prefiere movimiento; baja -> planos calmados."""
        clip = self.clips[self.i % len(self.clips)]
        self.i += 1
        d = clip.duration
        if d <= src_len + 0.2:
            return clip, 0.0, True            # hay que hacer loop
        margin = min(0.4, d * 0.05)
        n = int((d - src_len - 2 * margin) * RATE)
        if n <= 0:
            return clip, margin, False
        win = max(1, int(src_len * RATE))
        m = clip.motion
        cs = np.concatenate([[0], np.cumsum(m)])
        idx = np.arange(n)
        hi = np.minimum(idx + win, len(m))
        lo = np.minimum(idx, len(m) - 1)
        score = (cs[hi] - cs[lo]) / np.maximum(hi - lo, 1)
        score = score / (score.max() + 1e-9)
        pref = score if power > 0.5 else (1.2 - score)
        w = np.clip(pref, 0.02, None) ** (1.0 + 2.0 * abs(power - 0.5))
        for (a, b) in clip.used:               # evita repetir tramos
            t = margin + idx / RATE
            w = np.where((t + src_len > a) & (t < b), w * 0.04, w)
        w = w / w.sum()
        k = int(rng.choices(range(n), weights=list(w))[0])
        t0 = margin + k / RATE
        clip.used.append((t0, t0 + src_len))
        return clip, float(t0), False
