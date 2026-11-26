"""Autotest: genera video y audio sintéticos con FFmpeg y renderiza un reel de vista previa."""
import math, os, struct, sys, tempfile, wave
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from reelforge import ffutil, engine
from reelforge.config import Settings, apply_preset, PRESETS


def make_wav(path, dur=20, bpm=120, sr=22050):
    n = sr * dur
    data = [0.0] * n
    per = 60.0 / bpm
    k = 0
    while k * per < dur - 0.3:
        s0 = int(k * per * sr)
        for i in range(int(0.12 * sr)):
            t = i / sr
            if s0 + i < n:
                data[s0 + i] += math.sin(2 * math.pi * (110 * math.exp(-t * 16) + 45) * t) * math.exp(-t * 14)
        k += 1
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 30000)) for v in data))


def main():
    tmp = tempfile.mkdtemp(prefix="rf_selftest_")
    wav, v1, v2, out = (os.path.join(tmp, x) for x in ("m.wav", "a.mp4", "b.mp4", "out.mp4"))
    make_wav(wav)
    ffutil.run_ffmpeg(["-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=8", "-c:v", "libx264", "-pix_fmt", "yuv420p", v1])
    ffutil.run_ffmpeg(["-f", "lavfi", "-i", "mandelbrot=s=1280x720:r=30", "-t", "8", "-c:v", "libx264", "-pix_fmt", "yuv420p", v2])
    cap = ffutil.capabilities()
    print("filtros:", len(cap["filters"]), "· xfade:", len(cap["xfade"]), "· nvenc:", "h264_nvenc" in cap["encoders"])
    for name in ("Hype / Phonk", "Cyber Glitch"):
        s = apply_preset(Settings(), name)
        s.duration, s.preview, s.auto_window = 6, True, False
        s.text_enabled, s.text = True, "TEST REEL"
        engine.render(s, [v1, v2], wav, out, log=print)
        assert os.path.getsize(out) > 20000, "salida vacía"
        print("OK", name)


if __name__ == "__main__":
    main()
