"""Motor de render: planifica, renderiza cada segmento con sus efectos y ensambla con transiciones + audio."""
from __future__ import annotations
import os, random, shutil, tempfile, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import audio as A, analysis, camera, director, fire, looks, speed, text, ffutil
from .config import Settings
from .ffutil import Graph, Cancelled


def cache_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".reelforge", "cache")
    os.makedirs(d, exist_ok=True)
    return d


def resolve_window(s: Settings, an: A.AudioAnalysis):
    dur = min(s.duration, an.duration)
    if s.preview:
        dur = min(dur, 8.0)
    if s.auto_window and dur < an.duration - 0.5:
        start = A.best_window(an, s.duration if not s.preview else dur)
    else:
        start = min(max(0.0, s.start), max(0.0, an.duration - dur))
    dur = min(dur, an.duration - start)
    return start, start + dur


def layout(plan: director.Plan, fps: int):
    """Calcula inicio/fin en fotogramas de cada segmento para que los cortes caigan en el beat."""
    segs = plan.segs
    B0 = plan.start
    for k, sg in enumerate(segs):
        if sg.td > 0:
            sg.tdf = max(2, round(sg.td * fps))
            sg.start_f = round((sg.B0 - sg.td / 2 - B0) * fps)
        else:
            sg.tdf = 0
            sg.start_f = round((sg.B0 - B0) * fps)
    total_f = round((plan.end - plan.start) * fps)
    for k, sg in enumerate(segs):
        if k + 1 < len(segs):
            nx = segs[k + 1]
            sg.end_f = nx.start_f + nx.tdf
        else:
            sg.end_f = total_f
        if k == 0:
            sg.start_f = 0
        sg.nf = max(3, sg.end_f - sg.start_f)
        sg.L = sg.nf / fps
        sg.S = sg.L * sg.avg
        sg.hit = max(0.0, (sg.B0 - B0) - sg.start_f / fps)
    return total_f


def _encode_args(s: Settings, final: bool):
    if s.preview:
        return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "27", "-pix_fmt", "yuv420p"]
    if s.encoder == "h264_nvenc" and "h264_nvenc" in ffutil.capabilities()["encoders"]:
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", str(s.crf if final else 15),
                "-b:v", "0", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "veryfast" if not final else "medium",
            "-crf", str(s.crf if final else 15), "-pix_fmt", "yuv420p"]


def build_segment_cmd(sg, s: Settings, W, H, fps, rng, fire_path, out_path):
    args = []
    if sg.loop:
        args += ["-stream_loop", "-1"]
    args += ["-ss", f"{sg.src_start:.3f}", "-t", f"{sg.S + 0.05:.3f}", "-i", sg.clip]
    if sg.fire and fire_path:
        args += ["-stream_loop", "-1", "-ss", f"{rng.uniform(0, 1.2):.2f}", "-t", f"{sg.L + 0.3:.2f}",
                 "-i", fire_path]
    g = Graph(f"s{sg.idx}_")
    x = g.f("0:v", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                   + speed.setpts_filter(sg.speed_kind, sg.speed_w, sg.L, sg.S))
    if s.smooth_slowmo and sg.speed_kind != "none":
        x = g.f(x, f"minterpolate=fps={fps}:mi_mode=blend")
    x = g.f(x, f"fps={fps}")
    cam = camera.camera_chain(sg.cams, sg.L, sg.hit, W, H, sg.power, rng)
    x = g.f(x, cam)
    x = looks.apply_look(g, x, sg.look)
    x = looks.apply_accents(g, x, sg.hit, sg.accents)
    if sg.fire and fire_path:
        x = fire.overlay(g, x, "1:v", sg.fire_strength, hold=0.22 if sg.fire == "full" else 0.35)
    x = looks.finishing(g, x, "vignette" in s.accents, "grain" in s.accents)
    g.raw(f"[{x}]setsar=1,format=yuv420p[v]")
    args += ["-filter_complex", g.build(), "-map", "[v]", "-an", "-r", fps, "-frames:v", sg.nf]
    args += _encode_args(s, False) + [out_path]
    return args


def render(s: Settings, videos, audio_path, out_path, progress=None, log=None, cancel=None,
           analysis_cache: A.AudioAnalysis | None = None, keep_temp=False):
    log = log or (lambda m: None)
    progress = progress or (lambda f, m="": None)
    cancel = cancel or threading.Event()
    if not videos:
        raise RuntimeError("Agrega al menos un video.")
    if not audio_path:
        raise RuntimeError("Selecciona un audio.")

    videos = [os.path.abspath(v) for v in videos]
    audio_path, out_path = os.path.abspath(audio_path), os.path.abspath(out_path)
    W, H = s.size
    if s.preview:
        W, H = (540, 960) if W <= 1080 else (720, 1280)
    fps = s.fps

    progress(0.01, "Analizando audio…")
    an = analysis_cache or A.analyze(audio_path)
    log(f"Audio: {an.duration:.1f}s · {an.tempo:.1f} BPM · {len(an.beats)} beats")
    start, end = resolve_window(s, an)
    log(f"Ventana: {start:.2f}s → {end:.2f}s")

    plan = director.make_plan(s, an, start, end)
    total_f = layout(plan, fps)
    log(f"Cortes: {len(plan.segs)} segmentos")

    progress(0.04, "Analizando videos…")
    pool = analysis.ClipPool(videos, log=log, cancel=cancel)
    rng = random.Random(s.seed + 101)
    for sg in plan.segs:
        clip, t0, loop = pool.pick(sg.S, sg.power, rng)
        sg.clip, sg.src_start, sg.loop = clip.path, t0, loop
        if not loop and t0 + sg.S > clip.duration:     # seguridad
            sg.avg = max(0.3, (clip.duration - t0) / sg.L)
            sg.S = sg.L * sg.avg

    work = tempfile.mkdtemp(prefix="reelforge_")
    try:
        fire_assets = {}
        if any(sg.fire for sg in plan.segs):
            kinds = sorted({sg.fire for sg in plan.segs if sg.fire})
            cdir = os.path.join(cache_dir(), f"{W}x{H}_{fps}")
            os.makedirs(cdir, exist_ok=True)
            fire_assets = fire.ensure_assets(cdir, W, H, fps, kinds, log=log, cancel=cancel)

        # ---- render de segmentos ----
        n = len(plan.segs)
        frac = [0.0] * n
        lock = threading.Lock()

        def report():
            progress(0.06 + 0.78 * sum(frac) / n, f"Renderizando segmentos… {sum(1 for f in frac if f >= 1)}/{n}")

        def job(sg):
            out = os.path.join(work, f"seg_{sg.idx:04d}.mp4")
            r = random.Random(s.seed * 1000 + sg.idx)
            args = build_segment_cmd(sg, s, W, H, fps, r, fire_assets.get(sg.fire), out)

            def cb(f):
                with lock:
                    frac[sg.idx] = min(0.99, f)
                    report()
            ffutil.run_ffmpeg(args, duration=sg.L, on_progress=cb, cancel=cancel, log=log)
            with lock:
                frac[sg.idx] = 1.0
                report()
            return out

        workers = 1 if s.encoder == "h264_nvenc" else max(1, min(3, (os.cpu_count() or 4) // 4))
        seg_files = [None] * n
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(job, sg): sg.idx for sg in plan.segs}
            try:
                for fu in as_completed(futs):
                    seg_files[futs[fu]] = fu.result()
            except BaseException:
                cancel.set()
                raise

        # ---- ensamblado final ----
        progress(0.85, "Ensamblando con transiciones y audio…")
        total_t = total_f / fps
        g = Graph("f")
        args = []
        for p in seg_files:
            args += ["-i", p]
        args += ["-ss", f"{start:.3f}", "-t", f"{total_t + 0.05:.3f}", "-i", audio_path]
        labels = []
        for i in range(n):
            labels.append(g.f(f"{i}:v", f"setpts=PTS-STARTPTS,fps={fps},settb=AVTB,setsar=1,format=yuv420p"))
        acc = labels[0]
        for k in range(1, n):
            sg = plan.segs[k]
            out = g.new()
            if sg.tdf > 0 and sg.trans != "cut":
                g.raw(f"[{acc}][{labels[k]}]xfade=transition={sg.trans}:duration={sg.tdf / fps:.4f}:"
                      f"offset={sg.start_f / fps:.4f},settb=AVTB,setsar=1[{out}]")
            else:
                g.raw(f"[{acc}][{labels[k]}]concat=n=2:v=1:a=0,settb=AVTB,setsar=1[{out}]")
            acc = out
        if s.text_enabled and s.text.strip():
            seg_starts = [sg.B0 - start for sg in plan.segs]
            ev = text.build_events(s, seg_starts, [sg.energy for sg in plan.segs], total_t)
            tf = text.build_filters(s, ev, W, H, work)
            if tf:
                acc = g.f(acc, ",".join(tf))
        g.raw(f"[{acc}]format=yuv420p[vout]")
        af = (f"afade=t=in:st=0:d=0.03,afade=t=out:st={max(0.0, total_t - s.audio_fade):.2f}:d={s.audio_fade:.2f}")
        args += ["-filter_complex", g.build(), "-map", "[vout]", "-map", f"{n}:a:0", "-af", af,
                 "-t", f"{total_t:.3f}", "-r", fps]
        args += _encode_args(s, True) + ["-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", out_path]
        ffutil.run_ffmpeg(args, duration=total_t,
                          on_progress=lambda f: progress(0.85 + 0.14 * f, "Ensamblando…"),
                          cancel=cancel, cwd=work, log=log)
        progress(1.0, "Listo")
        log(f"✔ Exportado: {out_path}")
        return out_path
    finally:
        if not keep_temp:
            shutil.rmtree(work, ignore_errors=True)
