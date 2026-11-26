"""Efectos de cámara virtuales: zoom punch, zoom lento, sacudida, giro y paneo.
Todos se componen en una sola cadena rotate -> scale(eval=frame) -> crop."""
from __future__ import annotations


def camera_chain(kinds, L: float, hit: float, W: int, H: int, power: float, rng) -> str:
    kinds = [k for k in kinds if k]
    if not kinds:
        return ""
    zterms, dx, dy, rot = [], [], [], []
    margin = 1.03   # nunca 1.0 exacto: evita un bug de FFmpeg con scale eval=frame
    for k in kinds:
        if k == "punch":
            A = 0.10 + 0.17 * power
            zterms.append(f"if(gte(t,{hit:.3f}),{A:.3f}*exp(-6.5*(t-{hit:.3f})),0)")
        elif k == "zoom_in":
            Z = 0.09 + 0.12 * power
            zterms.append(f"{Z:.3f}*pow(t/{L:.3f},1.35)")
        elif k == "zoom_out":
            Z = 0.09 + 0.12 * power
            zterms.append(f"{Z:.3f}*(1-t/{L:.3f})")
        elif k == "shake":
            amp = W * (0.005 + 0.011 * power)
            env = f"(0.25+0.75*exp(-3.5*abs(t-{hit:.3f})))"
            ph = rng.uniform(0, 6)
            dx.append(f"{amp:.2f}*{env}*(sin(43*t+{ph:.2f})+0.6*sin(71*t+1.3))")
            dy.append(f"{amp:.2f}*{env}*(cos(39*t+{ph:.2f})+0.6*sin(67*t+0.4))")
            margin = max(margin, 1 + 3.2 * amp / W)
        elif k == "roll":
            ang = 0.022 + 0.032 * power
            sgn = rng.choice([-1, 1])
            rot.append(f"{sgn * ang:.4f}*sin(9*t)*(0.3+0.7*exp(-3*abs(t-{hit:.3f})))")
            margin = max(margin, 1 + 2.0 * ang + 0.03)
        elif k == "pan":
            sgn = rng.choice([-1, 1])
            rng_px = W * 0.05
            dx.append(f"{sgn * rng_px:.1f}*(2*t/{L:.3f}-1)")
            margin = max(margin, 1.11)
    z = f"{margin:.3f}" + "".join(f"+{t}" for t in zterms)
    parts = []
    if rot:
        parts.append(f"rotate=a='{'+'.join(rot)}':ow={W}:oh={H}:c=black:bilinear=1")
    parts.append(f"scale=w='2*trunc({W}*({z})/2)':h='2*trunc({H}*({z})/2)':eval=frame:flags=bilinear")
    X = "(iw-ow)/2" + ("+" + "+".join(dx) if dx else "")
    Y = "(ih-oh)/2" + ("+" + "+".join(dy) if dy else "")
    parts.append(f"crop={W}:{H}:x='{X}':y='{Y}'")
    parts.append("format=yuv420p")
    return ",".join(parts)
