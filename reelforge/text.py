"""Texto en pantalla (drawtext) sincronizado con los cortes."""
from __future__ import annotations
import glob, os, shutil

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\impact.ttf", r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf", "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def default_font() -> str:
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    found = glob.glob("/usr/share/fonts/**/*Bold*.ttf", recursive=True)
    return found[0] if found else ""


def _color(c: str) -> str:
    c = (c or "white").strip()
    return "0x" + c[1:] if c.startswith("#") else c


def build_events(s, seg_starts, seg_energy, total):
    """Devuelve [(texto, t0, t1)] según el modo elegido."""
    raw = s.text.strip()
    if not raw:
        return []
    if s.text_uppercase:
        raw = raw.upper()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    ev = []
    n = len(seg_starts)
    if s.text_mode == "static":
        ev.append(("\n".join(lines), 0.3, total - 0.3))
    elif s.text_mode == "intro_outro":
        ev.append((lines[0], 0.25, min(2.4, total / 2)))
        ev.append((lines[-1], max(total - 2.5, total / 2), total - 0.2))
    elif s.text_mode == "lines":
        picks, last = [], -9
        for i in range(n):
            if seg_energy[i] > 0.55 and seg_starts[i] - last >= 2.6 and seg_starts[i] < total - 1:
                picks.append(seg_starts[i])
                last = seg_starts[i]
        if not picks:
            k = max(1, len(lines))
            picks = [total * (i + 0.5) / k for i in range(k)]
        for i, t in enumerate(picks):
            ev.append((lines[i % len(lines)], t, min(t + 2.2, total)))
    else:  # words
        words = " ".join(lines).split()
        step = 1
        j = 0
        for i in range(n):
            if i % step:
                continue
            t0 = seg_starts[i]
            t1 = seg_starts[i + 1] if i + 1 < n else total
            if t1 - t0 < 0.45:
                step = 2
            ev.append((words[j % len(words)], t0, min(t1 + 0.02, t0 + 1.4)))
            j += 1
    return [e for e in ev if e[2] - e[1] > 0.1]


def build_filters(s, events, W, H, workdir):
    if not events:
        return []
    font = s.text_font if s.text_font and os.path.isfile(s.text_font) else default_font()
    ff = ""
    if font:
        shutil.copyfile(font, os.path.join(workdir, "font.ttf"))
        ff = "fontfile=font.ttf:"
    k = W / 1080.0
    size = max(24, int(s.text_size * k))
    col = _color(s.text_color)
    ypos = {"center": "(h-text_h)/2", "top": "h*0.14", "bottom": "h*0.68"}.get(s.text_pos, "(h-text_h)/2")
    out = []
    for i, (txt, t0, t1) in enumerate(events):
        fn = f"txt_{i}.txt"
        with open(os.path.join(workdir, fn), "w", encoding="utf-8") as f:
            f.write(txt)
        base = (f"drawtext={ff}textfile={fn}:reload=0:line_spacing={int(10 * k)}:"
                f"borderw={max(2, int(7 * k))}:bordercolor=black@0.9:shadowx={int(4 * k)}:shadowy={int(5 * k)}:"
                f"shadowcolor=black@0.6:enable='between(t,{t0:.3f},{t1:.3f})'")
        x = "x=(w-text_w)/2"
        dt = f"(t-{t0:.3f})"
        if s.text_style == "pop":
            # fontsize no admite expresiones con t: se anima con escalones de tamaño
            steps = [(0.0, 0.04, 1.45), (0.04, 0.08, 1.25), (0.08, 0.13, 1.1), (0.13, None, 1.0)]
            for a, b, m in steps:
                u0 = t0 + a
                u1 = t1 if b is None else min(t1, t0 + b)
                if u1 - u0 <= 0.005:
                    continue
                en = f"enable='between(t,{u0:.3f},{u1:.3f})'"
                out.append(base.replace(f"enable='between(t,{t0:.3f},{t1:.3f})'", en) +
                           f":fontsize={int(size * m)}:fontcolor={col}:{x}:y={ypos}")
        elif s.text_style == "fade":
            al = f"alpha='min(1,{dt}/0.2)*min(1,({t1:.3f}-t)/0.2)'"
            out.append(f"{base}:fontsize={size}:fontcolor={col}:{al}:{x}:y={ypos}")
        elif s.text_style == "slide":
            out.append(f"{base}:fontsize={size}:fontcolor={col}:x=(w-text_w)/2+{int(300 * k)}*exp(-9*{dt}):"
                       f"y={ypos}:alpha='min(1,{dt}/0.1)'")
        else:  # glitch: copias cian/magenta desplazadas al inicio + texto principal
            gl = int(10 * k)
            win = f"enable='between(t,{t0:.3f},{t0 + 0.22:.3f})'"
            for c, dx in (("0x00FFFF", -gl), ("0xFF00AA", gl)):
                out.append(base.replace(f"enable='between(t,{t0:.3f},{t1:.3f})'", win) +
                           f":fontsize={size}:fontcolor={c}:x=(w-text_w)/2+{dx}:y={ypos}")
            out.append(f"{base}:fontsize={size}:fontcolor={col}:{x}:y={ypos}")
    return out
