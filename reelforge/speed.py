"""Curvas de velocidad (speed ramps) como expresiones de setpts.

Se define una función de easing E(u), u=t_origen/S en [0,1], con E(0)=0 y E(1)=1.
El tiempo de salida es L*E(u); la velocidad instantánea es avg/E'(u).
"""
from __future__ import annotations
import math


def _ease_expr(kind: str, w: float, u: str) -> str:
    w = max(0.0, min(0.92, w))
    if kind == "impact":        # lento al inicio (golpe), acelera hacia el final
        p = 2.6
        return f"((1-{w:.3f})*{u}+{w:.3f}*(1-pow(1-{u},{p})))"
    if kind == "rampup":        # rápido al inicio, cámara lenta al final
        p = 2.6
        return f"((1-{w:.3f})*{u}+{w:.3f}*pow({u},{p}))"
    if kind == "bullet":        # rápido - LENTO - rápido
        return f"({u}-{w:.3f}*sin(2*PI*{u})/(2*PI))"
    if kind == "pulse":         # dos respiraciones
        return f"({u}-{w * 0.8:.3f}*sin(4*PI*{u})/(4*PI))"
    return u


def ease(kind: str, w: float, u: float) -> float:
    w = max(0.0, min(0.92, w))
    if kind == "impact":
        return (1 - w) * u + w * (1 - (1 - u) ** 2.6)
    if kind == "rampup":
        return (1 - w) * u + w * u ** 2.6
    if kind == "bullet":
        return u - w * math.sin(2 * math.pi * u) / (2 * math.pi)
    if kind == "pulse":
        return u - w * 0.8 * math.sin(4 * math.pi * u) / (4 * math.pi)
    return u


def profile(kind: str, w: float, avg: float = 1.0, n: int = 80):
    """Velocidad relativa a lo largo del segmento (para dibujar en la UI)."""
    out = []
    for i in range(n):
        u0, u1 = i / n, (i + 1) / n
        d = ease(kind, w, u1) - ease(kind, w, u0)
        out.append(avg / max(d * n, 1e-3))
    return out


def setpts_filter(kind: str, w: float, L: float, S: float) -> str:
    """Filtro setpts que mapea S segundos de origen a L segundos de salida."""
    u = f"(((PTS-STARTPTS)*TB)/{S:.5f})"
    if kind == "none" or w <= 0:
        return f"setpts='(PTS-STARTPTS)*{L / S:.6f}'"
    return f"setpts='{L:.5f}*{_ease_expr(kind, w, u)}/TB'"
