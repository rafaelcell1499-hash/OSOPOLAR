"""Ajustes del proyecto, catálogos de efectos y presets de estilo."""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict, fields

# (id, etiqueta)
SYNC_MODES = [
    ("auto", "Auto (según energía de la canción)"),
    ("beat1", "Cada beat"),
    ("beat2", "Cada 2 beats"),
    ("beat4", "Cada compás (4 beats)"),
    ("onsets", "En golpes fuertes (onsets)"),
]

SPEED_KINDS = [
    ("impact", "Impacto: lento en el golpe → acelera"),
    ("rampup", "Rampa: rápido → cámara lenta antes del corte"),
    ("bullet", "Bullet time: rápido-lento-rápido"),
    ("pulse", "Pulso: doble respiración"),
    ("none", "Velocidad constante"),
]

CAMERA_FX = [
    ("punch", "Zoom punch (golpe en el beat)"),
    ("zoom_in", "Zoom in progresivo"),
    ("zoom_out", "Zoom out progresivo"),
    ("shake", "Sacudida de cámara"),
    ("roll", "Giro / roll"),
    ("pan", "Paneo lateral"),
]

LOOKS = [
    ("natural", "Natural (contraste suave)"),
    ("contrast", "Contraste punch"),
    ("bw", "Blanco y negro duro"),
    ("teal_orange", "Cine teal y orange"),
    ("fire_grade", "Grade fuego"),
    ("ice", "Grade hielo"),
    ("neon", "Neón brillante"),
    ("cyber", "Cyberpunk"),
    ("vaporwave", "Vaporwave"),
    ("dream", "Dreamy glow"),
    ("vintage", "Vintage película"),
    ("vhs", "VHS retro"),
    ("sepia", "Sepia"),
    ("comic", "Cómic / póster"),
    ("neon_edges", "Arte: bordes de neón"),
    ("posterize", "Arte: posterizado"),
]

TRANSITIONS = [
    ("cut", "Corte seco"),
    ("fade", "Fundido"),
    ("flash", "Flash blanco"),
    ("fire", "Transición de fuego"),
    ("whip", "Whip pan (deslizar)"),
    ("zoomin", "Zoom in"),
    ("circle", "Círculo"),
    ("radial", "Radial / reloj"),
    ("pixel", "Pixelar"),
    ("slice", "Cortes horizontales"),
    ("blur", "Desenfoque horizontal"),
    ("wipe", "Barrido"),
    ("dissolve", "Disolución"),
    ("squeeze", "Aplastar"),
    ("glitchcut", "Glitch cut"),
]

# transición -> posibles nombres de xfade (se elige uno soportado)
TRANSITION_XFADE = {
    "fade": ["fade"], "flash": ["fadewhite"], "fire": ["fade"],
    "whip": ["slideleft", "slideright", "smoothleft", "smoothright", "slideup"],
    "zoomin": ["zoomin"], "circle": ["circleopen", "circleclose", "circlecrop"],
    "radial": ["radial"], "pixel": ["pixelize"], "slice": ["hlslice", "hrslice"],
    "blur": ["hblur"], "wipe": ["wipeleft", "wiperight", "wipeup", "wipedown", "diagtl"],
    "dissolve": ["dissolve"], "squeeze": ["squeezeh", "squeezev"],
}

ACCENTS = [
    ("flash", "Flash de luz en el beat"),
    ("glitch", "Glitch RGB / invertido"),
    ("fire", "Fuego sobre el video"),
    ("vignette", "Viñeta"),
    ("grain", "Grano de película"),
]

TEXT_MODES = [
    ("words", "Palabras en cada beat (kinetic)"),
    ("lines", "Frases en los drops"),
    ("static", "Título fijo"),
    ("intro_outro", "Intro + cierre"),
]

TEXT_STYLES = [("pop", "Pop (rebote)"), ("fade", "Fundido"), ("glitch", "Glitch"), ("slide", "Deslizar")]
TEXT_POS = [("center", "Centro"), ("top", "Arriba"), ("bottom", "Abajo")]

RESOLUTIONS = [("1080x1920", "1080×1920 (Full HD vertical)"),
               ("720x1280", "720×1280 (rápido)"),
               ("1440x2560", "1440×2560 (2K)")]


@dataclass
class Settings:
    # Audio / ritmo
    start: float = 0.0
    duration: float = 30.0
    auto_window: bool = True          # buscar la mejor parte (drop) de la canción
    sync_mode: str = "auto"
    min_cut: float = 0.30
    # Estilo
    preset: str = "Hype / Phonk"
    intensity: float = 0.75
    # Velocidad
    speed_curves: bool = True
    speed_kinds: list = field(default_factory=lambda: ["impact", "rampup", "bullet", "pulse"])
    speed_amount: float = 0.6
    smooth_slowmo: bool = False
    # Cámara
    camera_fx: list = field(default_factory=lambda: ["punch", "zoom_in", "shake", "roll"])
    # Looks
    looks: list = field(default_factory=lambda: ["contrast", "bw", "neon", "cyber"])
    look_mode: str = "energy"         # mix | fixed | energy
    # Transiciones
    transitions: list = field(default_factory=lambda: ["cut", "flash", "whip", "zoomin", "glitchcut", "fire"])
    # Acentos
    accents: list = field(default_factory=lambda: ["flash", "glitch", "fire", "vignette", "grain"])
    fire_amount: float = 0.55
    # Texto
    text_enabled: bool = False
    text: str = "NEVER STOP\nKEEP GOING\nNO LIMITS"
    text_mode: str = "words"
    text_style: str = "pop"
    text_pos: str = "center"
    text_size: int = 150
    text_color: str = "white"
    text_font: str = ""               # ruta .ttf; vacío = automática
    text_uppercase: bool = True
    # Salida
    resolution: str = "1080x1920"
    fps: int = 30
    crf: int = 17
    encoder: str = "libx264"          # libx264 | h264_nvenc
    keep_clip_audio: bool = False
    audio_fade: float = 1.2
    seed: int = 7
    preview: bool = False

    @property
    def size(self):
        w, h = self.resolution.lower().split("x")
        return int(w), int(h)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @staticmethod
    def from_dict(d: dict) -> "Settings":
        names = {f.name for f in fields(Settings)}
        return Settings(**{k: v for k, v in d.items() if k in names})


PRESETS: dict[str, dict] = {
    "Hype / Phonk": dict(
        intensity=0.85, sync_mode="auto", min_cut=0.28, speed_curves=True, speed_amount=0.75,
        speed_kinds=["impact", "rampup", "bullet", "pulse"],
        camera_fx=["punch", "shake", "zoom_in", "roll"], looks=["contrast", "bw", "neon", "cyber"],
        look_mode="energy", transitions=["cut", "flash", "whip", "zoomin", "glitchcut", "fire"],
        accents=["flash", "glitch", "fire", "vignette", "grain"], fire_amount=0.55),
    "Fire Edit": dict(
        intensity=0.9, sync_mode="beat1", min_cut=0.25, speed_curves=True, speed_amount=0.8,
        speed_kinds=["impact", "bullet", "rampup"], camera_fx=["punch", "shake", "zoom_in"],
        looks=["fire_grade", "contrast", "fire_grade"], look_mode="fixed",
        transitions=["fire", "flash", "cut", "zoomin"], accents=["flash", "fire", "vignette", "grain"],
        fire_amount=0.95),
    "Cinematic": dict(
        intensity=0.5, sync_mode="beat2", min_cut=0.5, speed_curves=True, speed_amount=0.45,
        speed_kinds=["rampup", "bullet", "none"], camera_fx=["zoom_in", "zoom_out", "pan"],
        looks=["teal_orange", "vintage"], look_mode="fixed",
        transitions=["fade", "dissolve", "wipe", "blur", "circle"],
        accents=["vignette", "grain"], fire_amount=0.0),
    "Dreamy / Aesthetic": dict(
        intensity=0.45, sync_mode="beat2", min_cut=0.5, speed_curves=True, speed_amount=0.5,
        speed_kinds=["rampup", "pulse", "bullet"], camera_fx=["zoom_in", "zoom_out", "pan", "roll"],
        looks=["dream", "vaporwave", "vintage"], look_mode="mix",
        transitions=["dissolve", "flash", "circle", "fade", "radial"],
        accents=["flash", "vignette", "grain"], fire_amount=0.0),
    "Cyber Glitch": dict(
        intensity=0.9, sync_mode="auto", min_cut=0.25, speed_curves=True, speed_amount=0.7,
        speed_kinds=["impact", "pulse", "bullet"], camera_fx=["shake", "punch", "roll"],
        looks=["cyber", "neon", "vhs", "bw"], look_mode="mix",
        transitions=["glitchcut", "pixel", "slice", "blur", "cut", "whip"],
        accents=["flash", "glitch", "vignette", "grain"], fire_amount=0.0),
    "Arte / Cómic": dict(
        intensity=0.7, sync_mode="beat2", min_cut=0.35, speed_curves=True, speed_amount=0.55,
        speed_kinds=["impact", "pulse", "rampup"], camera_fx=["punch", "zoom_in", "roll", "pan"],
        looks=["comic", "neon_edges", "posterize", "vaporwave"], look_mode="mix",
        transitions=["pixel", "circle", "slice", "squeeze", "wipe", "flash"],
        accents=["flash", "vignette"], fire_amount=0.0),
    "Retro VHS": dict(
        intensity=0.6, sync_mode="beat2", min_cut=0.4, speed_curves=True, speed_amount=0.5,
        speed_kinds=["rampup", "pulse", "none"], camera_fx=["shake", "zoom_in", "pan"],
        looks=["vhs", "vintage", "sepia"], look_mode="mix",
        transitions=["glitchcut", "fade", "blur", "cut", "wipe"],
        accents=["glitch", "vignette", "grain"], fire_amount=0.0),
}


def apply_preset(s: Settings, name: str) -> Settings:
    p = PRESETS.get(name)
    if p:
        for k, v in p.items():
            setattr(s, k, list(v) if isinstance(v, list) else v)
        s.preset = name
    return s
