"""Utilidades de FFmpeg: localizar binarios, ejecutar con progreso, sondear capacidades."""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys, threading
from collections import deque
from functools import lru_cache

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class Cancelled(Exception):
    pass


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_tool(name: str) -> str:
    exe = name + (".exe" if os.name == "nt" else "")
    base = app_dir()
    for cand in (os.path.join(base, "bin", exe), os.path.join(base, "_internal", "bin", exe),
                 os.path.join(base, exe)):
        if os.path.isfile(cand):
            return cand
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(f"No se encontró {name}. Colócalo en la carpeta 'bin' junto al programa.")


def ffmpeg() -> str:
    return find_tool("ffmpeg")


def ffprobe() -> str:
    return find_tool("ffprobe")


def _popen(cmd, **kw):
    return subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW, **kw)


def run_ffmpeg(args, duration=None, on_progress=None, cancel=None, cwd=None, log=None):
    """Ejecuta ffmpeg. `duration` (s) permite calcular el % con -progress."""
    cmd = [ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-nostats",
           "-progress", "pipe:1"] + [str(a) for a in args]
    p = _popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, text=True,
               encoding="utf-8", errors="replace")
    err = deque(maxlen=60)

    def drain():
        for line in p.stderr:
            err.append(line.rstrip())
    th = threading.Thread(target=drain, daemon=True)
    th.start()
    try:
        for line in p.stdout:
            if cancel is not None and cancel.is_set():
                p.kill()
                raise Cancelled()
            if on_progress and duration and line.startswith("out_time_us="):
                try:
                    sec = int(line.split("=")[1]) / 1e6
                    on_progress(max(0.0, min(1.0, sec / duration)))
                except ValueError:
                    pass
        p.wait()
    finally:
        if p.poll() is None:
            p.kill()
    th.join(timeout=2)
    if cancel is not None and cancel.is_set():
        raise Cancelled()
    if p.returncode != 0:
        msg = "\n".join(err)
        if log:
            log("FFmpeg error:\n" + msg)
        raise RuntimeError("FFmpeg falló:\n" + msg[-1800:])


def read_pipe(args) -> bytes:
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error"] + [str(a) for a in args]
    p = _popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise RuntimeError("FFmpeg falló: " + err.decode("utf-8", "replace")[-800:])
    return out


@lru_cache(maxsize=256)
def probe(path: str) -> dict:
    cmd = [ffprobe(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path]
    p = _popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise RuntimeError(f"No se pudo leer {path}: {err.decode('utf-8','replace')[-300:]}")
    j = json.loads(out.decode("utf-8", "replace"))
    info = {"duration": float(j.get("format", {}).get("duration") or 0), "w": 0, "h": 0,
            "fps": 30.0, "has_video": False, "has_audio": False}
    for s in j.get("streams", []):
        if s.get("codec_type") == "video" and not info["has_video"]:
            info.update(has_video=True, w=int(s.get("width", 0)), h=int(s.get("height", 0)))
            try:
                n, d = s.get("r_frame_rate", "30/1").split("/")
                info["fps"] = float(n) / float(d) if float(d) else 30.0
            except Exception:
                pass
            if not info["duration"]:
                info["duration"] = float(s.get("duration") or 0)
        elif s.get("codec_type") == "audio":
            info["has_audio"] = True
    return info


@lru_cache(maxsize=1)
def capabilities() -> dict:
    """Filtros, transiciones xfade y encoders disponibles en el FFmpeg instalado."""
    cap = {"filters": set(), "xfade": set(), "encoders": set()}

    def out_of(*a):
        return subprocess.run([ffmpeg(), "-hide_banner", *a], capture_output=True, text=True,
                              creationflags=CREATE_NO_WINDOW, encoding="utf-8",
                              errors="replace").stdout
    try:
        for line in out_of("-filters").splitlines():
            m = re.match(r"^\s*[TSC.]{3}\s+(\S+)\s", line)
            if m:
                cap["filters"].add(m.group(1))
        for line in out_of("-h", "filter=xfade").splitlines():
            m = re.match(r"^\s+([a-z0-9]+)\s+-?\d+\s", line)
            if m:
                cap["xfade"].add(m.group(1))
        for line in out_of("-encoders").splitlines():
            m = re.match(r"^\s*V\S+\s+(\S+)", line)
            if m:
                cap["encoders"].add(m.group(1))
    except Exception:
        pass
    return cap


def has_filter(name: str) -> bool:
    return name in capabilities()["filters"]


class Graph:
    """Constructor mínimo de filter_complex con etiquetas únicas."""

    def __init__(self, prefix="g"):
        self.parts: list[str] = []
        self.n = 0
        self.prefix = prefix

    def new(self) -> str:
        self.n += 1
        return f"{self.prefix}{self.n}"

    def f(self, src: str, expr: str) -> str:
        """Aplica `expr` (cadena de filtros) a la etiqueta src y devuelve la etiqueta nueva."""
        if not expr:
            return src
        out = self.new()
        self.parts.append(f"[{src}]{expr}[{out}]")
        return out

    def raw(self, text: str):
        self.parts.append(text)

    def build(self) -> str:
        return ";".join(self.parts)
