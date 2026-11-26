"""Análisis de audio (solo numpy): tempo, beats, onsets y energía. Planificación de cortes."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from . import ffutil

SR = 22050
N_FFT = 1024
HOP = 512
LAT = N_FFT / 2 / SR   # latencia del centro de ventana


@dataclass
class AudioAnalysis:
    duration: float
    tempo: float
    beats: np.ndarray            # segundos
    onsets: np.ndarray           # segundos
    onset_strength: np.ndarray   # fuerza de cada onset (0..1)
    energy_t: np.ndarray         # tiempos del contorno de energía (10 Hz)
    energy: np.ndarray           # 0..1
    peaks: np.ndarray            # picos de forma de onda para dibujar (0..1)

    def energy_at(self, t: float) -> float:
        if len(self.energy) == 0:
            return 0.5
        i = int(np.clip(round(t * 10), 0, len(self.energy) - 1))
        return float(self.energy[i])

    def mean_energy(self, t0: float, t1: float) -> float:
        i0 = int(np.clip(t0 * 10, 0, len(self.energy) - 1))
        i1 = int(np.clip(max(t1 * 10, i0 + 1), i0 + 1, len(self.energy)))
        return float(np.mean(self.energy[i0:i1]))


def decode_mono(path: str, sr: int = SR) -> np.ndarray:
    raw = ffutil.read_pipe(["-i", path, "-vn", "-ac", "1", "-ar", sr, "-f", "f32le", "-"])
    return np.frombuffer(raw, dtype=np.float32).copy()


def _stft_mag(y: np.ndarray) -> np.ndarray:
    if len(y) < N_FFT * 2:
        y = np.pad(y, (0, N_FFT * 2 - len(y)))
    win = np.hanning(N_FFT).astype(np.float32)
    n = 1 + (len(y) - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    frames = y[idx] * win
    return np.abs(np.fft.rfft(frames, axis=1)).astype(np.float32)


def _smooth(x, k):
    k = max(1, int(k))
    return np.convolve(x, np.ones(k) / k, mode="same")


def analyze(path: str, progress=None) -> AudioAnalysis:
    y = decode_mono(path)
    if len(y) < SR:
        raise RuntimeError("El audio es demasiado corto o no se pudo decodificar.")
    duration = len(y) / SR
    fps_env = SR / HOP

    mag = _stft_mag(y)
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)
    logm = np.log1p(12.0 * mag)
    diff = np.maximum(0, np.diff(logm, axis=0, prepend=logm[:1]))
    w = np.where(freqs < 250, 1.6, np.where(freqs < 2500, 1.0, 0.6))   # prioriza bajos/kick
    env = (diff * w).sum(axis=1)
    env = env - _smooth(env, int(0.5 * fps_env))
    env = np.maximum(env, 0)
    env /= (np.percentile(env, 98) + 1e-9)
    env = np.clip(env, 0, 1.5)

    # ---- onsets ----
    onsets, strength = [], []
    min_gap = int(0.09 * fps_env)
    thr = max(0.18, float(np.percentile(env, 70)))
    last = -min_gap
    for i in range(1, len(env) - 1):
        if env[i] >= thr and env[i] >= env[i - 1] and env[i] > env[i + 1] and i - last >= min_gap:
            onsets.append(i / fps_env + LAT)
            strength.append(env[i])
            last = i
    onsets = np.array(onsets)
    strength = np.clip(np.array(strength) / 1.2, 0, 1) if len(strength) else np.array([])

    # ---- tempo (autocorrelación) ----
    e = env - env.mean()
    ac = np.correlate(e, e, mode="full")[len(e) - 1:]
    lo, hi = int(fps_env * 60 / 175), int(fps_env * 60 / 78)
    lags = np.arange(lo, hi + 1)
    bpms = 60 * fps_env / lags
    prior = np.exp(-0.5 * (np.log2(bpms / 125.0) / 0.55) ** 2)
    score = ac[lo:hi + 1] * prior
    k = int(np.argmax(score))
    lag = float(lags[k])
    if 0 < k < len(score) - 1:      # refinamiento parabólico
        a, b, c = score[k - 1], score[k], score[k + 1]
        den = a - 2 * b + c
        if abs(den) > 1e-9:
            lag += 0.5 * (a - c) / den
    tempo = 60 * fps_env / lag

    # ---- rejilla de beats con fase óptima y corrección suave ----
    best_ph, best_val = 0.0, -1
    for ph in np.arange(0, lag, 0.5):
        pos = np.arange(ph, len(env), lag).astype(int)
        v = env[pos[pos < len(env)]].sum()
        if v > best_val:
            best_val, best_ph = v, ph
    beats, pos = [], best_ph
    tol = int(0.12 * lag) + 1
    while pos < len(env):
        c = int(round(pos))
        a0, a1 = max(0, c - tol), min(len(env), c + tol + 1)
        if a1 > a0 and env[a0:a1].max() > 0.25:
            peak = a0 + int(np.argmax(env[a0:a1]))
            pos = pos + 0.35 * (peak - pos)
        beats.append(pos / fps_env + LAT)
        pos += lag
    beats = np.array(beats)

    # ---- energía ----
    hop10 = int(SR / 10)
    n10 = len(y) // hop10
    rms = np.sqrt(np.mean(y[:n10 * hop10].reshape(n10, hop10) ** 2, axis=1))
    rms = _smooth(rms, 5)
    lo_p, hi_p = np.percentile(rms, 5), np.percentile(rms, 95)
    energy = np.clip((rms - lo_p) / (hi_p - lo_p + 1e-9), 0, 1)
    onset_density = np.zeros(n10)
    for t in onsets:
        j = int(t * 10)
        if j < n10:
            onset_density[j] += 1
    onset_density = _smooth(onset_density, 15)
    if onset_density.max() > 0:
        onset_density /= onset_density.max()
    energy = np.clip(0.65 * energy + 0.35 * onset_density, 0, 1)

    # ---- picos de forma de onda (para la UI) ----
    n_pk = 1400
    chunk = max(1, len(y) // n_pk)
    m = len(y) // chunk
    peaks = np.abs(y[:m * chunk]).reshape(m, chunk).max(axis=1)
    peaks = peaks / (peaks.max() + 1e-9)

    return AudioAnalysis(duration, float(tempo), beats, onsets, strength,
                         np.arange(n10) / 10.0, energy, peaks)


def best_window(an: AudioAnalysis, dur: float) -> float:
    """Inicio de la ventana de `dur` s con mayor energía (el drop) alineada a un beat."""
    if dur >= an.duration - 0.5:
        return 0.0
    n = int(dur * 10)
    e = an.energy
    if len(e) <= n:
        return 0.0
    cs = np.concatenate([[0], np.cumsum(e)])
    means = (cs[n:] - cs[:-n]) / n
    # favorece ventanas cuyo comienzo es un subidón de energía
    rise = np.zeros_like(means)
    for i in range(len(means)):
        a = e[max(0, i - 20):i].mean() if i > 0 else e[0]
        b = e[i:i + 20].mean()
        rise[i] = max(0, b - a)
    score = means + 0.6 * rise
    i = int(np.argmax(score))
    t = i / 10.0
    if len(an.beats):
        t = float(an.beats[int(np.argmin(np.abs(an.beats - t)))])
    return float(np.clip(t, 0, max(0, an.duration - dur)))


def plan_cuts(an: AudioAnalysis, start: float, end: float, mode: str, min_len: float):
    """Devuelve la lista de límites [B0=start, B1, ..., Bn=end]."""
    beats = an.beats[(an.beats > start + 1e-3) & (an.beats < end - 1e-3)]
    period = 60.0 / an.tempo
    bounds = [start]

    def push(t):
        if t - bounds[-1] >= min_len and end - t >= min_len * 0.6:
            bounds.append(float(t))

    if mode == "onsets" and len(an.onsets):
        sel = an.onsets[(an.onsets > start) & (an.onsets < end)]
        st = an.onset_strength[(an.onsets > start) & (an.onsets < end)]
        if len(st):
            thr = np.percentile(st, 55)
            for t, s in zip(sel, st):
                if s >= thr:
                    push(t)
    elif mode in ("beat1", "beat2", "beat4"):
        step = {"beat1": 1, "beat2": 2, "beat4": 4}[mode]
        while step * period < min_len and step < 16:
            step *= 2
        # alinea con el primer beat y avanza de a `step`
        for i, t in enumerate(beats):
            if i % step == 0:
                push(t)
    else:  # auto
        i = 0
        while i < len(beats):
            t = beats[i]
            e = an.energy_at(t)
            step = 1 if e > 0.68 else (2 if e > 0.38 else 4)
            while step * period < min_len and step < 16:
                step *= 2
            push(t)
            i += step
    if end - bounds[-1] < min_len * 0.6 and len(bounds) > 1:
        bounds.pop()
    bounds.append(float(end))
    return bounds
