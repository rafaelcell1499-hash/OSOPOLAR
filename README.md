# 🔥 ReelForge 2.0 — Editor automático de Reels verticales

Programa de Windows con interfaz gráfica que, a partir de **uno o varios videos** y **una canción**, genera
automáticamente un reel vertical (9:16) con cortes al ritmo, **curvas de velocidad**, transiciones de cámara,
**fuego**, looks artísticos y **texto** opcional.

## Qué hace

| Módulo | Detalle |
|---|---|
| **Audio** | Detecta BPM, beats, golpes (onsets) y energía de la canción. Puede elegir sola la mejor parte (el *drop*). |
| **Cortes** | Cada beat, cada 2, cada compás, automático según la energía, o en golpes fuertes. |
| **Curvas de velocidad** | Impacto (lento→rápido), Rampa (rápido→cámara lenta), Bullet time, Pulso. Curva visible en la interfaz. |
| **Cámara** | Zoom punch en el beat, zoom in/out, sacudida, giro (roll), paneo. Se combinan solos. |
| **Transiciones** | Corte seco, fundido, flash, **fuego**, whip pan, zoom, círculo, radial, pixelar, cortes, desenfoque, barrido, disolución, glitch… (usa las transiciones `xfade` de tu FFmpeg). |
| **Fuego** | Generado de forma procedural (sin archivos externos): llamas desde abajo o a pantalla completa, en los golpes fuertes y en transiciones. |
| **Looks** | Contraste, B/N, teal & orange, grade fuego/hielo, neón, cyberpunk, vaporwave, dreamy glow, vintage, VHS, sepia, cómic, bordes de neón, posterizado. |
| **Acentos** | Flash de luz, glitch RGB, invertido, viñeta, grano de película. |
| **Texto** | Palabras en cada beat (kinetic), frases en los drops, título fijo o intro+cierre. Animación pop / fundido / glitch / deslizar. |
| **Selección de clips** | Analiza el movimiento de tus videos: en momentos intensos elige tramos con acción; en calma, planos tranquilos. Evita repetir tramos. |
| **Presets** | Hype/Phonk, Fire Edit, Cinematic, Dreamy, Cyber Glitch, Arte/Cómic, Retro VHS. |

## Compilar con GitHub Actions (sin instalar nada)

1. Crea un repositorio en GitHub y sube **todo el contenido** de esta carpeta (incluida `.github/`).
2. Ve a la pestaña **Actions** → workflow **Build ReelForge (Windows)** → se ejecuta solo al hacer *push*
   (o pulsa **Run workflow**).
3. Al terminar (~5-8 min), abre la ejecución y descarga el artefacto **ReelForge-win64** (un `.zip`).
4. Descomprime y ejecuta `ReelForge\ReelForge.exe`. **FFmpeg ya va incluido** en `ReelForge\bin\`.

Para publicar una *Release* con el zip adjunto, crea un tag: `git tag v2.0.0 && git push --tags`.

El workflow descarga FFmpeg (build GPL completo de BtbN), ejecuta un **autotest** que renderiza reels de prueba,
compila con PyInstaller y empaqueta.

## Compilar en tu PC (opcional)

1. Instala Python 3.10+ y coloca `ffmpeg.exe` y `ffprobe.exe` en la carpeta `bin\`.
2. Ejecuta `build_local.bat` → `dist\ReelForge\ReelForge.exe`.
   (`run_dev.bat` lo ejecuta sin compilar.)

## Cómo se usa

1. **Proyecto**: arrastra tus videos y tu canción a la ventana (o usa los botones). El audio se analiza solo.
2. Elige un **Estilo** arriba a la derecha (cambia todos los ajustes de una vez).
3. Pulsa **📐 Planificar cortes** para ver en la forma de onda dónde cortará y con qué curva (colores = tipo de curva).
4. **▶ Vista previa 8 s** renderiza rápido en baja resolución y la reproduce dentro del programa.
5. Ajusta lo que quieras en *Ritmo*, *Efectos* y *Texto*; **🎲 Nuevo edit** cambia la semilla para obtener otro montaje.
6. **🔥 EXPORTAR REEL** genera el MP4 final (1080×1920, H.264 + AAC).

Haz clic en la forma de onda para fijar el inicio manualmente (desactiva «Buscar la mejor parte»).

### Uso por línea de comandos
```
python -m reelforge.cli --videos a.mp4 b.mp4 --audio musica.mp3 --out reel.mp4 --preset "Fire Edit" --duration 30 --auto-window --text "NO LIMITS"
```

## Consejos

- **Más videos = más variedad.** Con un solo video largo también funciona (elige tramos distintos).
- Render lento: usa 720×1280, o el codificador **NVENC** si tienes GPU NVIDIA (pestaña Exportar).
- Cámara lenta suave (mezcla de fotogramas) es más lenta pero más fluida con videos de 30 fps.
- El texto usa `Impact`/`Arial Bold` de Windows por defecto; puedes elegir cualquier `.ttf`.
- Mismos ajustes + misma semilla = mismo resultado.

## Estructura

```
main.py                  # arranque de la GUI
reelforge/
  audio.py               # BPM, beats, onsets, energía, plan de cortes (solo numpy)
  analysis.py            # movimiento de los videos y selección de tramos
  director.py            # decide efectos por segmento según la energía
  speed.py               # curvas de velocidad (setpts)
  camera.py              # zoom/shake/roll/pan
  looks.py               # looks y acentos
  fire.py                # fuego procedural
  text.py                # texto en pantalla
  engine.py              # render por segmentos + ensamblado xfade + audio
  gui/                   # interfaz PySide6 (tema oscuro)
.github/workflows/build.yml
tests/selftest.py
```

## Solución de problemas

- **«No se encontró ffmpeg»**: debe existir `bin\ffmpeg.exe` junto a `ReelForge.exe` (el zip de Actions ya lo incluye).
- **Texto no aparece**: activa *Texto* en su pestaña y revisa que haya una frase escrita.
- **SmartScreen avisa**: el exe no está firmado; pulsa *Más información → Ejecutar de todas formas*.
